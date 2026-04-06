"""
Background Tasks - Scheduled maintenance jobs
==============================================
Runs as daemon threads when the server starts.
"""

import os
import logging
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Dict

logger = logging.getLogger(__name__)

# Import billing for sweep function
try:
    import billing
except ImportError:
    billing = None


def _run_billing_sweep_loop():
    """Run billing sweep daily at midnight UTC."""
    while True:
        now = datetime.now(timezone.utc)
        next_midnight = now.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        if next_midnight <= now:
            next_midnight += timedelta(days=1)

        sleep_seconds = (next_midnight - now).total_seconds()
        logger.info(f"Next billing sweep in {sleep_seconds/3600:.1f} hours")
        time.sleep(sleep_seconds)

        try:
            # Call our own API endpoint
            # Container calls itself via internal network
            base_url = os.environ.get(
                'INTERNAL_API_URL', 'http://localhost:8080'
            )
            import requests
            resp = requests.post(
                f"{base_url}/api/billing/sweep",
                headers={
                    'X-Internal-Key': os.environ.get('INTERNAL_KEY', 'lipaira-internal'),
                    'Content-Type': 'application/json'
                },
                json={},
                timeout=60
            )
            if resp.ok:
                logger.info(f"Billing sweep complete: {resp.json()}")
            else:
                logger.error(f"Billing sweep failed: {resp.status_code}")
        except Exception as e:
            logger.error(f"Billing sweep error: {e}")


def _run_memory_sweep_loop():
    """Run memory sweep daily at 6am UTC."""
    while True:
        now = datetime.now(timezone.utc)
        next_6am = now.replace(hour=6, minute=0, second=0, microsecond=0)
        if next_6am <= now:
            next_6am += timedelta(days=1)

        sleep_seconds = (next_6am - now).total_seconds()
        logger.info(f"Next memory sweep in {sleep_seconds/3600:.1f} hours")
        time.sleep(sleep_seconds)

        try:
            base_url = os.environ.get(
                'INTERNAL_API_URL', 'http://localhost:8080'
            )
            import requests
            # Get all users and run memory sweep for each
            # For now, just log that we'd do this
            logger.info("Memory sweep: would process all users")
        except Exception as e:
            logger.error(f"Memory sweep error: {e}")


def _run_workflow_scheduler_loop():
    """Check for and run scheduled workflows - optimized version."""
    import requests
    
    # Import croniter for cron parsing
    try:
        from croniter import croniter
    except ImportError:
        logger.warning("croniter not installed, workflow scheduler disabled")
        return
    
    # Cache of workflow next_run times (refresh every 5 minutes)
    workflow_cache = []
    cache_refreshed = 0
    CACHE_TTL = 300  # 5 minutes
    
    while True:
        try:
            now = datetime.now()
            
            # Refresh cache periodically
            if not workflow_cache or (now.timestamp() - cache_refreshed) > CACHE_TTL:
                import psycopg2
                import os
                db_url = os.environ.get('DATABASE_URL', 'postgresql://nexusos:2c27dd080c0a8f7b02dace074bd4cb77ba48cfb5@postgres:5432/nexusos')
                conn = psycopg2.connect(db_url)
                
                with conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT w.id, w.user_id, w.name, w.trigger_config, 
                                   w.steps, w.next_run_at, w.enabled
                            FROM workflows w
                            WHERE w.trigger_type = 'scheduled' 
                            AND w.enabled = true
                            AND w.next_run_at IS NOT NULL
                        """)
                        workflow_cache = cur.fetchall()
                
                cache_refreshed = now.timestamp()
                logger.info(f"Workflow cache refreshed: {len(workflow_cache)} scheduled workflows")
            
            # Only check workflows due to run now
            for wf in workflow_cache:
                workflow_id, user_id, name, trigger_config, steps, next_run, enabled = wf
                
                if not enabled or not next_run:
                    continue
                
                # Check if it's time to run (within 60 seconds)
                if isinstance(next_run, str):
                    next_run = datetime.fromisoformat(next_run)
                
                time_diff = (next_run - now).total_seconds()
                
                if 0 <= time_diff <= 60:
                    logger.info(f"Running scheduled workflow: {name}")
                    
                    # Execute via DB (no API call needed)
                    try:
                        import psycopg2
                        import os
                        db_url = os.environ.get('DATABASE_URL', 'postgresql://nexusos:2c27dd080c0a8f7b02dace074bd4cb77ba48cfb5@postgres:5432/nexusos')
                        conn = psycopg2.connect(db_url)
                        
                        # Get user API key
                        with conn:
                            with conn.cursor() as cur:
                                cur.execute("""
                                    SELECT api_key FROM api_keys 
                                    WHERE user_id = %s AND active = true
                                    LIMIT 1
                                """, (user_id,))
                                key_row = cur.fetchone()
                        
                        if key_row:
                            api_key = key_row[0]
                            
                            # Execute workflow directly (inline, no API call)
                            result = _execute_workflow_inline(workflow_id, steps, user_id)
                            
                            # Update next_run and run_count
                            # Parse cron for next run time
                            cron_expr = trigger_config.get('cron') if isinstance(trigger_config, dict) else None
                            if cron_expr:
                                try:
                                    cron = croniter(cron_expr, now)
                                    new_next = cron.get_next(datetime)
                                    
                                    with get_user_conn() as conn:
                                        with conn.cursor() as cur:
                                            cur.execute("""
                                                UPDATE workflows 
                                                SET last_run_at = NOW(),
                                                    run_count = run_count + 1,
                                                    next_run_at = %s,
                                                    updated_at = NOW()
                                                WHERE id = %s
                                            """, (new_next, workflow_id))
                                            conn.commit()
                                except Exception as e:
                                    logger.error(f"Failed to update next_run for {name}: {e}")
                            
                            logger.info(f"Workflow {name} executed: {result.get('success', False)}")
                        else:
                            logger.warning(f"No API key for user {user_id}")
                    
                    except Exception as e:
                        logger.error(f"Error executing workflow {name}: {e}")
                    
                    # Remove from cache so we don't run again this cycle
                    workflow_cache = [w for w in workflow_cache if w[0] != workflow_id]
                    
        except Exception as e:
            logger.error(f"Workflow scheduler error: {e}")
        
        # Check every 30 seconds (not every minute)
        time.sleep(30)


def _execute_workflow_inline(workflow_id, steps, user_id):
    """Execute workflow directly without API call - saves tokens."""
    import asyncio
    
    from operator_layer.workflow_engine import WorkflowExecutor, WorkflowStep, StepType
    
    # Parse steps
    step_objects = []
    for step_data in (steps if isinstance(steps, list) else []):
        step = WorkflowStep(
            id=step_data.get('id', f'step_{len(step_objects)}'),
            type=StepType(step_data.get('type', 'action')),
            description=step_data.get('description', ''),
            integration=step_data.get('integration'),
            operation=step_data.get('operation'),
            params=step_data.get('params', {})
        )
        step_objects.append(step)
    
    # Set up executors
    executors = {}
    
    # Resend email
    def send_email(**params):
        from lipaira_client.skills.email_send_skill import EmailSendSkill
        skill = EmailSendSkill()
        result = skill.execute({
            'to': params.get('to'),
            'subject': params.get('subject'),
            'body': params.get('body'),
            'from_name': params.get('from_name', 'Lipaira')
        })
        return result.output if result.output else {'success': result.success}
    
    executors['resend'] = send_email
    
    # QuickBooks
    try:
        from lipaira_client.skills.quickbooks_client import qb_query
        executors['quickbooks'] = qb_query
    except:
        pass
    
    executor = WorkflowExecutor(user_id, executors)
    
    try:
        loop = asyncio.get_event_loop()
    except:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(
        executor.execute_workflow(step_objects, {})
    )


def start_background_tasks():
    """Start all background maintenance threads."""
    # Start billing sweep
    threading.Thread(
        target=_run_billing_sweep_loop,
        name="billing-sweep",
        daemon=True
    ).start()

    # Start memory sweep
    threading.Thread(
        target=_run_memory_sweep_loop,
        name="memory-sweep",
        daemon=True
    ).start()

    # Start workflow scheduler
    threading.Thread(
        target=_run_workflow_scheduler_loop,
        name="workflow-scheduler",
        daemon=True
    ).start()

    logger.info("Background tasks started")


if __name__ == "__main__":
    # For testing: run once
    logging.basicConfig(level=logging.INFO)
    _run_billing_sweep_loop()