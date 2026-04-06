"""
Operator Routes
===============
REST API endpoints for the operator layer.
"""

import asyncio
import hashlib
import json
import logging
import time
from typing import Dict, Any

from flask import Blueprint, request, jsonify, g
from functools import wraps

logger = logging.getLogger(__name__)

operator_bp = Blueprint('operator', __name__, url_prefix='/api/operator')


def require_auth(f):
    """Decorator to ensure user is authenticated."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not hasattr(g, 'user_id') or not g.user_id:
            # Check for API key
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                # Inline API key validation (same as server_full.py)
                api_key = auth_header[7:]
                try:
                    import hashlib
                    import os
                    import psycopg2
                    from urllib.parse import urlparse
                    
                    db_url = os.environ.get('DATABASE_URL')
                    if not db_url:
                        return jsonify({'error': 'Invalid API key'}), 401
                    
                    result = urlparse(db_url)
                    conn = psycopg2.connect(
                        host=result.hostname,
                        port=result.port or 5432,
                        database=result.path.lstrip('/'),
                        user=result.username,
                        password=result.password
                    )
                    
                    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
                    key_part = api_key.replace('sk-nexus-', '').replace('lp-', '')
                    key_hash_part = hashlib.sha256(key_part.encode()).hexdigest()
                    
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT user_id FROM api_keys 
                        WHERE (key_hash = %s OR key_hash = %s OR key_hash = %s OR key_hash = %s) AND is_active = true
                    """, (key_hash, key_hash_part, api_key, key_part))
                    
                    row = cursor.fetchone()
                    conn.close()
                    
                    if row:
                        g.user_id = row[0]
                    else:
                        return jsonify({'error': 'Invalid API key'}), 401
                except Exception as e:
                    logger.error(f"Auth error: {e}")
                    return jsonify({'error': 'Authentication failed'}), 401
            else:
                return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated


# Import operator modules
from .intent import get_intent_parser, RiskLevel, ActionType
from .executor import get_executor, CapabilityResolver, PlatformAction
from .audit import get_audit_logger, compute_intent_hash


@operator_bp.route('/execute', methods=['POST'])
@require_auth
def execute_command():
    """
    Execute a natural language command across integrations.
    
    Request:
    {
        "command": "Update all my product prices to be 10% higher"
        // OR for approved preview:
        "intent_hash": "abc123",
        "plan": {...} 
    }
    
    Response:
    {
        "success": true,
        "intent": {...},
        "preview": {...},
        "result": {...}
    }
    """
    start_time = time.time()
    data = request.get_json() or {}
    command = data.get('command', '').strip()
    
    if not command:
        return jsonify({'error': 'command is required'}), 400
    
    user_id = g.user_id
    
    try:
        # Step 1: Parse intent (sync fallback)
        parser = get_intent_parser()
        intent = parser._parse_fallback(command)  # Use sync fallback
        
        # Step 2: Check risk level
        risk = parser.assess_risk(intent)
        
        # Step 3: Get user's connected integrations
        from integrations.credential_store import IntegrationCredentialStore
        store = IntegrationCredentialStore(user_id)
        integrations = store.list()
        
        connected_platforms = [i['provider'] for i in integrations if i.get('health') == 'green']
        
        # Step 4: Resolve which platforms can handle this
        capable_platforms = CapabilityResolver.resolve(intent.action.value, connected_platforms)
        
        if not capable_platforms:
            return jsonify({
                'success': False,
                'error': f'No connected platforms support "{intent.action.value}"',
                'hint': 'Connect a supported integration first'
            }), 400
        
        # Step 5: Build execution plan (preview)
        plan = _build_preview(intent, capable_platforms, user_id)
        
        # If high risk, require approval (return preview first)
        if risk == RiskLevel.HIGH and not data.get('approved'):
            intent_hash = compute_intent_hash(command, intent.to_dict())
            return jsonify({
                'success': False,
                'needs_approval': True,
                'preview': plan,
                'intent_hash': intent_hash,
                'risk': risk.value,
                'message': 'This action requires approval. Include "approved": true to execute.'
            })
        
        # Step 6: Execute (sync version)
        result = _execute_plan_sync(intent, capable_platforms, user_id, command)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        return jsonify({
            'success': result['success'],
            'intent': intent.to_dict(),
            'platforms': result['platforms'],
            'total_actions': result['total_actions'],
            'failed': result['failed'],
            'summary': result['summary'],
            'duration_ms': duration_ms
        })
        
    except Exception as e:
        logger.error(f"Operator execution error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@operator_bp.route('/preview', methods=['POST'])
@require_auth
def preview_command():
    """
    Preview what a command would do without executing.
    
    Request:
    {
        "command": "Update all my product prices to be 10% higher"
    }
    
    Response:
    {
        "intent": {...},
        "platforms": [...],
        "estimated_actions": 47,
        "risk": "high"
    }
    """
    data = request.get_json() or {}
    command = data.get('command', '').strip()
    
    if not command:
        return jsonify({'error': 'command is required'}), 400
    
    try:
        parser = get_intent_parser()
        intent = parser._parse_fallback(command)  # Use sync fallback
        risk = parser.assess_risk(intent)
        
        from integrations.credential_store import IntegrationCredentialStore
        store = IntegrationCredentialStore(g.user_id)
        integrations = store.list()
        
        connected_platforms = [i['provider'] for i in integrations if i.get('health') == 'green']
        capable_platforms = CapabilityResolver.resolve(intent.action.value, connected_platforms)
        
        plan = _build_preview(intent, capable_platforms, g.user_id)
        intent_hash = compute_intent_hash(command, intent.to_dict())
        
        return jsonify({
            'intent': intent.to_dict(),
            'intent_hash': intent_hash,
            'risk': risk.value,
            'requires_approval': risk == RiskLevel.HIGH,
            **plan
        })
        
    except Exception as e:
        logger.error(f"Preview error: {e}")
        return jsonify({'error': str(e)}), 500


@operator_bp.route('/capabilities', methods=['GET'])
@require_auth
def list_capabilities():
    """List all available capabilities and their platforms."""
    from .executor import CapabilityResolver
    
    capabilities = {}
    for action in ActionType:
        platforms = CapabilityResolver.resolve(action.value, 
            ['godaddy', 'squarespace', 'shopify'])
        capabilities[action.value] = platforms
    
    return jsonify({
        'capabilities': capabilities
    })


@operator_bp.route('/history', methods=['GET'])
@require_auth
def audit_history():
    """Get operator action history for user."""
    limit = int(request.args.get('limit', 50))
    
    audit = get_audit_logger()
    history = audit.get_history(g.user_id, limit)
    
    return jsonify({
        'history': history
    })


def _build_preview(intent, platforms: list, user_id: str) -> Dict[str, Any]:
    """Build a preview of what the intent would do."""
    from .intent import ActionType
    
    # Estimate actions based on intent type
    estimates = {
        ActionType.UPDATE_PRICES: "Updates prices across all products",
        ActionType.UPDATE_INVENTORY: "Updates inventory levels",
        ActionType.FULFILL_ORDERS: "Marks orders as fulfilled",
        ActionType.SYNC_PRODUCTS: "Syncs product data to local database",
        ActionType.CONFIGURE_DNS: "Configures DNS records",
        ActionType.CHECK_HEALTH: "Checks integration health status",
        ActionType.QUERY: "Queries data for display",
    }
    
    return {
        'platforms': [
            {
                'provider': p,
                'capabilities': CapabilityResolver.get_capabilities(p),
                'description': estimates.get(intent.action, "Unknown action")
            }
            for p in platforms
        ],
        'estimated_platforms': len(platforms),
        'action_description': estimates.get(intent.action, "Custom action")
    }


async def _execute_plan(intent, platforms: list, user_id: str, command: str) -> Dict[str, Any]:
    """Execute the plan across platforms."""
    from .intent import ActionType
    from .executor import get_executor, PlatformAction
    from .audit import get_audit_logger
    
    executor = get_executor()
    audit = get_audit_logger()
    intent_hash = compute_intent_hash(command, intent.to_dict())
    
    # Build actions based on intent
    actions = []
    
    for platform in platforms:
        adapter = _get_adapter(platform, user_id)
        if not adapter:
            continue
        
        # Map intent to adapter method
        method_map = {
            (ActionType.UPDATE_PRICES, 'squarespace'): 'get_products',
            (ActionType.UPDATE_PRICES, 'shopify'): 'list_products',
            (ActionType.UPDATE_INVENTORY, 'squarespace'): 'get_products',
            (ActionType.UPDATE_INVENTORY, 'shopify'): 'list_products',
            (ActionType.FULFILL_ORDERS, 'squarespace'): 'get_orders',
            (ActionType.FULFILL_ORDERS, 'shopify'): 'list_orders',
            (ActionType.SYNC_PRODUCTS, 'squarespace'): 'get_products',
            (ActionType.SYNC_PRODUCTS, 'shopify'): 'list_products',
            (ActionType.CHECK_HEALTH, 'squarespace'): 'verify_connection',
            (ActionType.CHECK_HEALTH, 'shopify'): 'verify_connection',
            (ActionType.CHECK_HEALTH, 'godaddy'): 'verify_connection',
        }
        
        method_name = method_map.get((intent.action, platform), 'list_products')
        
        actions.append(PlatformAction(
            platform=platform,
            adapter=adapter,
            method_name=method_name,
            args=(),
            kwargs={}
        ))
    
    # Execute in parallel (async)
    results = await executor.execute_parallel(actions)
    
    # Aggregate results
    success_count = sum(1 for r in results if r.success)
    failed = [r for r in results if not r.success]
    
    # Log to audit
    for result in results:
        audit.log_action(
            user_id=user_id,
            intent_hash=intent_hash,
            command=command,
            action=intent.action.value,
            platform=result.platform,
            status='success' if result.success else 'failed',
            error=result.error
        )
    
    summary = f"Completed on {success_count}/{len(results)} platforms"
    if failed:
        summary += f". Failed: {[f.platform for f in failed]}"
    
    return {
        'success': success_count == len(results),
        'platforms': [
            {'provider': r.platform, 'success': r.success, 'error': r.error}
            for r in results
        ],
        'total_actions': len(results),
        'failed': len(failed),
        'summary': summary
    }


def _execute_plan_sync(intent, platforms: list, user_id: str, command: str) -> Dict[str, Any]:
    """Execute the plan across platforms (synchronous version)."""
    from .intent import ActionType
    from .audit import get_audit_logger, compute_intent_hash
    
    audit = get_audit_logger()
    intent_hash = compute_intent_hash(command, intent.to_dict())
    
    # Build actions based on intent - execute directly without rate limiter
    results = []
    
    for platform in platforms:
        adapter = _get_adapter(platform, user_id)
        if not adapter:
            results.append(PlatformAction(
                platform=platform,
                adapter=None,
                method_name='',
                success=False,
                error='Adapter not available'
            ))
            continue
        
        # Map intent to adapter method
        method_map = {
            (ActionType.UPDATE_PRICES, 'squarespace'): 'get_products',
            (ActionType.UPDATE_PRICES, 'shopify'): 'list_products',
            (ActionType.UPDATE_INVENTORY, 'squarespace'): 'get_products',
            (ActionType.UPDATE_INVENTORY, 'shopify'): 'list_products',
            (ActionType.FULFILL_ORDERS, 'squarespace'): 'get_orders',
            (ActionType.FULFILL_ORDERS, 'shopify'): 'list_orders',
            (ActionType.SYNC_PRODUCTS, 'squarespace'): 'get_products',
            (ActionType.SYNC_PRODUCTS, 'shopify'): 'list_products',
            (ActionType.CHECK_HEALTH, 'squarespace'): 'verify_connection',
            (ActionType.CHECK_HEALTH, 'shopify'): 'verify_connection',
            (ActionType.CHECK_HEALTH, 'godaddy'): 'verify_connection',
        }
        
        method_name = method_map.get((intent.action.value, platform), 'list_products')
        
        try:
            method = getattr(adapter, method_name)
            result = method()  # Sync call
            
            results.append(PlatformAction(
                platform=platform,
                adapter=adapter,
                method_name=method_name,
                success=True,
                result=result
            ))
            
            # Log success
            audit.log_action(
                user_id=user_id,
                intent_hash=intent_hash,
                command=command,
                action=intent.action.value,
                platform=platform,
                status='success'
            )
        except Exception as e:
            logger.error(f"Action failed on {platform}: {e}")
            results.append(PlatformAction(
                platform=platform,
                adapter=adapter,
                method_name=method_name,
                success=False,
                error=str(e)
            ))
            
            # Log failure
            audit.log_action(
                user_id=user_id,
                intent_hash=intent_hash,
                command=command,
                action=intent.action.value,
                platform=platform,
                status='failed',
                error=str(e)
            )
    
    # Aggregate results
    success_count = sum(1 for r in results if r.success)
    failed = [r for r in results if not r.success]
    
    summary = f"Completed on {success_count}/{len(results)} platforms"
    if failed:
        summary += f". Failed: {[f.platform for f in failed]}"
    
    return {
        'success': success_count == len(results),
        'platforms': [
            {'provider': r.platform, 'success': r.success, 'error': r.error}
            for r in results
        ],
        'total_actions': len(results),
        'failed': len(failed),
        'summary': summary
    }


def _get_adapter(platform: str, user_id: str):
    """Get adapter instance for a platform."""
    adapter_map = {
        'godaddy': ('integrations.godaddy', 'GoDaddyAdapter'),
        'squarespace': ('integrations.squarespace', 'SquarespaceAdapter'),
        'shopify': ('integrations.shopify', 'ShopifyAdapter'),
    }
    
    if platform not in adapter_map:
        return None
    
    module_name, class_name = adapter_map[platform]
    
    try:
        module = __import__(module_name, fromlist=[class_name])
        adapter_class = getattr(module, class_name)
        return adapter_class(user_id)
    except Exception as e:
        logger.error(f"Failed to load {platform} adapter: {e}")
        return None

# ============================================================================
# DYNAMIC WORKFLOW GENERATION
# ============================================================================

@operator_bp.route('/workflow/generate', methods=['POST'])
@require_auth
def generate_workflow():
    """
    Generate a custom workflow based on user goal and available integrations.
    
    Request body:
    {
        "goal": "chase overdue invoices every week",
        "integrations": ["quickbooks", "resend"]  // Optional, inferred from DB
    }
    """
    from .workflow_engine import WorkflowGenerator, CapabilityRegistry, Workflow
    
    
    # Import llm_router from server_full
    try:
        from server_full import llm_router
    except ImportError:
        return jsonify({'error': 'LLM router not available'}), 500
    
    data = request.get_json() or {}
    goal = data.get('goal', '').strip()
    
    if not goal:
        return jsonify({'error': 'goal is required'}), 400
    
    # Get user's connected integrations (or use provided)
    user_integrations = data.get('integrations')
    if not user_integrations:
        # Query from database
        from db import get_user_conn
        with get_user_conn(g.user_id) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT provider FROM user_integrations
                    WHERE user_id = %s
                """, (g.user_id,))
                rows = cur.fetchall()
                user_integrations = [r[0] for r in rows]
    
    # Get available operations
    available_ops = CapabilityRegistry.get_available_operations(user_integrations)
    
    if not available_ops:
        return jsonify({
            'error': 'No integrations connected',
            'message': 'Connect an integration (QuickBooks, Google, etc.) to generate workflows'
        }), 400
    
    # Get existing workflows from memory to avoid duplicates
    existing_workflows_context = ""
    try:
        from server_full import get_memory_graph
        graph = get_memory_graph(g.user_id)
        memories = graph.recall_semantic("workflow", limit=10)
        if memories:
            existing_workflows_context = "\n\nEXISTING WORKFLOWS (don't recreate):\n"
            for mem in memories:
                existing_workflows_context += f"- {mem.get('content', '')}\n"
    except Exception as e:
        logger.warning(f"Failed to load workflow memories: {e}")
    
    # Build the prompt for LLM
    prompt = WorkflowGenerator.SYSTEM_PROMPT.format(
        goal=goal,
        capabilities=json.dumps(available_ops, indent=2)
    ) + existing_workflows_context
    
    # Call LLM to generate workflow
    try:
        response = llm_router.call_provider(
            provider='anthropic',
            model='claude-3-5-sonnet-20241022',
            messages=[{"role": "user", "content": prompt}],
            system="You are a workflow design expert. Generate valid JSON workflow definitions.",
            max_tokens=2000
        )
        
        # Extract the workflow JSON from response
        workflow_json = response.get('choices', [{}])[0].get('message', {}).get('content', '')
        
        # Parse into Workflow object
        try:
            workflow = WorkflowGenerator.parse_llm_response(workflow_json)
        except ValueError as e:
            return jsonify({
                'error': 'Failed to parse workflow',
                'details': str(e),
                'llm_response': workflow_json[:500]
            }), 400
        
        return jsonify({
            'success': True,
            'workflow': {
                'id': workflow.id,
                'name': workflow.name,
                'description': workflow.description,
                'trigger_type': workflow.trigger_type.value,
                'trigger_config': workflow.trigger_config,
                'steps': [
                    {
                        'id': s.id,
                        'type': s.type.value,
                        'description': s.description,
                        'integration': s.integration,
                        'operation': s.operation,
                        'params': s.params
                    }
                    for s in workflow.steps
                ]
            },
            'available_integrations': list(available_ops.keys())
        })
        
    except Exception as e:
        logger.error(f"Workflow generation failed: {e}")
        return jsonify({
            'error': 'Workflow generation failed',
            'details': str(e)
        }), 500


@operator_bp.route('/workflow/execute', methods=['POST'])
@require_auth
def execute_workflow():
    """
    Execute a generated workflow.
    
    Request body:
    {
        "workflow": { ... },  // Workflow JSON from generate
        "context": { ... }    // Initial context (optional)
    }
    """
    import asyncio
    from .workflow_engine import WorkflowExecutor, WorkflowGenerator, WorkflowStep, StepType, TriggerType
    
    data = request.get_json() or {}
    workflow_data = data.get('workflow')
    context = data.get('context', {})
    
    if not workflow_data:
        return jsonify({'error': 'workflow is required'}), 400
    
    # Parse workflow
    try:
        workflow = WorkflowGenerator.parse_llm_response(json.dumps(workflow_data))
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    
    # Set up executors
    executors = {
        'resend': _send_email_executor,
    }
    
    # Add integration executors
    for integration in ['quickbooks', 'google', 'godaddy', 'shopify', 'squarespace']:
        if integration in ['quickbooks']:
            from lipaira_client.skills.quickbooks_client import qb_query
            executors[integration] = qb_query
    
    executor = WorkflowExecutor(g.user_id, executors)
    
    # Execute
    try:
        loop = asyncio.get_event_loop()
    except:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    result = loop.run_until_complete(
        executor.execute_workflow(workflow, context)
    )
    
    return jsonify(result)


@operator_bp.route('/workflows', methods=['GET'])
@require_auth
def list_workflows():
    """List all saved workflows for the user."""
    from db import get_user_conn
    
    with get_user_conn(g.user_id) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, name, description, trigger_type, trigger_config, 
                       steps, enabled, last_run_at, run_count, created_at, updated_at
                FROM workflows
                WHERE user_id = %s
                ORDER BY updated_at DESC
            """, (g.user_id,))
            rows = cur.fetchall()
    
    workflows = []
    for row in rows:
        workflows.append({
            'id': str(row[0]),
            'name': row[1],
            'description': row[2],
            'trigger_type': row[3],
            'trigger_config': row[4] if isinstance(row[4], dict) else {},
            'steps': row[5] if isinstance(row[5], list) else [],
            'enabled': row[6],
            'last_run_at': row[7].isoformat() if row[7] else None,
            'run_count': row[8],
            'created_at': row[9].isoformat() if row[9] else None,
            'updated_at': row[10].isoformat() if row[10] else None
        })
    
    return jsonify({'workflows': workflows})


@operator_bp.route('/workflows', methods=['POST'])
@require_auth
def save_workflow():
    """Save a generated workflow to the database."""
    from db import get_user_conn
    
    data = request.get_json() or {}
    
    workflow_id = data.get('id')  # Optional - for updates
    name = data.get('name', '').strip()
    description = data.get('description', '')
    trigger_type = data.get('trigger_type', 'manual')
    trigger_config = data.get('trigger_config', {})
    steps = data.get('steps', [])
    
    if not name:
        return jsonify({'error': 'name is required'}), 400
    
    if not steps:
        return jsonify({'error': 'steps are required'}), 400
    
    # Calculate next_run_at for scheduled workflows
    next_run_at = None
    if trigger_type == 'scheduled':
        try:
            from croniter import croniter
            cron_expr = trigger_config.get('cron') if isinstance(trigger_config, dict) else None
            if cron_expr:
                now = datetime.now()
                cron = croniter(cron_expr, now)
                next_run_at = cron.get_next(datetime)
        except Exception as e:
            logger.warning(f"Failed to calculate next_run_at: {e}")
    
    with get_user_conn(g.user_id) as conn:
        with conn.cursor() as cur:
            if workflow_id:
                # Update existing
                cur.execute("""
                    UPDATE workflows 
                    SET name = %s, description = %s, trigger_type = %s,
                        trigger_config = %s, steps = %s, updated_at = NOW(),
                        next_run_at = %s
                    WHERE id = %s AND user_id = %s
                    RETURNING id
                """, (name, description, trigger_type, json.dumps(trigger_config),
                      json.dumps(steps), next_run_at, workflow_id, g.user_id))
            else:
                # Insert new
                cur.execute("""
                    INSERT INTO workflows (user_id, name, description, trigger_type, 
                                          trigger_config, steps, next_run_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (g.user_id, name, description, trigger_type, 
                      json.dumps(trigger_config), json.dumps(steps), next_run_at))
            
            row = cur.fetchone()
            conn.commit()
            saved_id = str(row[0]) if row else workflow_id
    
    # Add to memory graph for agent awareness
    try:
        from server_full import get_memory_graph
        graph = get_memory_graph(g.user_id)
        
        # Build a summary of what this workflow does
        step_summaries = []
        for step in steps:
            if isinstance(step, dict):
                integration = step.get('integration', 'unknown')
                operation = step.get('operation', 'unknown')
                step_summaries.append(f"{integration}:{operation}")
            else:
                step_summaries.append(str(step))
        
        workflow_summary = f"Workflow '{name}': {description}. Triggers {trigger_type}. Steps: {', '.join(step_summaries)}"
        
        graph.add_memory(
            content=workflow_summary,
            memory_type="workflow",
            importance=0.7
        )
    except Exception as e:
        logger.warning(f"Failed to add workflow to memory: {e}")
    
    return jsonify({
        'success': True,
        'id': saved_id,
        'message': 'Workflow saved'
    })


@operator_bp.route('/workflows/<workflow_id>', methods=['DELETE'])
@require_auth
def delete_workflow(workflow_id):
    """Delete a saved workflow."""
    from db import get_user_conn
    import uuid
    
    try:
        wf_uuid = uuid.UUID(workflow_id)
    except ValueError:
        return jsonify({'error': 'Invalid workflow ID'}), 400
    
    with get_user_conn(g.user_id) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM workflows 
                WHERE id = %s AND user_id = %s
                RETURNING id
            """, (wf_uuid, g.user_id))
            row = cur.fetchone()
            conn.commit()
    
    if row:
        return jsonify({'success': True, 'message': 'Workflow deleted'})
    else:
        return jsonify({'error': 'Workflow not found'}), 404


@operator_bp.route('/workflows/<workflow_id>/toggle', methods=['POST'])
@require_auth
def toggle_workflow(workflow_id):
    """Enable or disable a workflow."""
    from db import get_user_conn
    import uuid
    
    data = request.get_json() or {}
    enabled = data.get('enabled', True)
    
    try:
        wf_uuid = uuid.UUID(workflow_id)
    except ValueError:
        return jsonify({'error': 'Invalid workflow ID'}), 400
    
    with get_user_conn(g.user_id) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE workflows 
                SET enabled = %s, updated_at = NOW()
                WHERE id = %s AND user_id = %s
                RETURNING id
            """, (enabled, wf_uuid, g.user_id))
            row = cur.fetchone()
            conn.commit()
    
    if row:
        return jsonify({'success': True, 'enabled': enabled})
    else:
        return jsonify({'error': 'Workflow not found'}), 404


@operator_bp.route('/workflows/<workflow_id>/run', methods=['POST'])
@require_auth
def run_workflow(workflow_id):
    """Run a saved workflow immediately."""
    from db import get_user_conn
    import uuid
    from .workflow_engine import WorkflowExecutor, WorkflowStep, StepType, TriggerType
    
    try:
        wf_uuid = uuid.UUID(workflow_id)
    except ValueError:
        return jsonify({'error': 'Invalid workflow ID'}), 400
    
    # Load workflow from DB
    with get_user_conn(g.user_id) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, name, trigger_type, trigger_config, steps, enabled
                FROM workflows
                WHERE id = %s AND user_id = %s
            """, (wf_uuid, g.user_id))
            row = cur.fetchone()
    
    if not row:
        return jsonify({'error': 'Workflow not found'}), 404
    
    if not row[5]:  # enabled
        return jsonify({'error': 'Workflow is disabled'}), 400
    
    # Parse steps into WorkflowStep objects
    steps_data = row[4] if isinstance(row[4], list) else []
    steps = []
    for step_data in steps_data:
        step = WorkflowStep(
            id=step_data.get('id', f'step_{len(steps)}'),
            type=StepType(step_data.get('type', 'action')),
            description=step_data.get('description', ''),
            integration=step_data.get('integration'),
            operation=step_data.get('operation'),
            params=step_data.get('params', {}),
            condition=step_data.get('condition'),
            on_true=step_data.get('on_true'),
            on_false=step_data.get('on_false')
        )
        steps.append(step)
    
    # Set up executors
    executors = {
        'resend': _send_email_executor,
    }
    
    from lipaira_client.skills.quickbooks_client import qb_query
    executors['quickbooks'] = qb_query
    
    executor = WorkflowExecutor(g.user_id, executors)
    
    # Execute
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    result = loop.run_until_complete(
        executor.execute_workflow(steps, {})
    )
    
    # Update run count
    with get_user_conn(g.user_id) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE workflows 
                SET run_count = run_count + 1, last_run_at = NOW(), updated_at = NOW()
                WHERE id = %s
            """, (wf_uuid,))
            conn.commit()
    
    return jsonify({
        'success': True,
        'results': result
    })


def _send_email_executor(**params):
    """Executor for sending emails via Resend."""
    from lipaira_client.skills.email_send_skill import EmailSendSkill
    
    skill = EmailSendSkill()
    result = skill.execute({
        'to': params.get('to'),
        'subject': params.get('subject'),
        'body': params.get('body'),
        'from_name': params.get('from_name', 'Lipaira')
    })
    
    return result.output if result.output else {'success': result.success}
