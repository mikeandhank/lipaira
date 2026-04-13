"""
Dynamic Workflow Engine — AI-generated multi-step workflow execution for Lipaira.
Allows the operator to generate custom workflows on-the-fly based on the user's
connected integrations, stated goals, and historical patterns from memory.
Workflows are JSON-defined with TriggerType (manual/scheduled/event/condition)
and StepType (skill/integrations/python/delay/condition/transform). Executed
by the WorkflowEngine with full state persistence across steps.
"""
import json
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum

log = logging.getLogger(__name__)


class TriggerType(Enum):
    """When a workflow fires."""
    MANUAL = "manual"           # User triggers manually
    SCHEDULED = "scheduled"     # Cron-like schedule
    EVENT = "event"             # Webhook/event trigger
    CONDITION = "condition"     # When condition is met


class StepType(Enum):
    """Types of steps in a workflow."""
    QUERY = "query"             # Get data from integration
    ACTION = "action"           # Perform action via integration
    CONDITION = "condition"     # Branch based on data
    TRANSFORM = "transform"     # Modify/process data
    NOTIFY = "notify"           # Notify user
    WAIT = "wait"               # Delay/sleep
    APPROVAL = "approval"       # Wait for user approval


@dataclass
class WorkflowStep:
    """A single step in a workflow."""
    id: str
    type: StepType
    description: str
    
    # For QUERY/ACTION steps
    integration: Optional[str] = None
    operation: Optional[str] = None
    params: Optional[Dict] = None
    
    # For CONDITION steps
    condition: Optional[str] = None
    on_true: Optional[str] = None  # Step ID to jump to
    on_false: Optional[str] = None
    
    # For NOTIFY steps
    channel: Optional[str] = None  # chat, email, push
    template: Optional[str] = None
    
    # For WAIT steps
    duration_seconds: Optional[int] = None


@dataclass
class Workflow:
    """A complete workflow definition."""
    id: str
    name: str
    description: str
    
    # Trigger
    trigger_type: TriggerType
    trigger_config: Dict  # schedule cron, event name, etc.
    
    # Steps
    steps: List[WorkflowStep]
    
    # Metadata
    version: str = "1.0"
    created_by: str = "operator"  # "operator" or user
    enabled: bool = True
    
    # Execution
    max_runtime_seconds: int = 300
    retry_on_failure: bool = True
    max_retries: int = 3


# ============================================================================
# CAPABILITY REGISTRY
# ============================================================================

class CapabilityRegistry:
    """
    Registry of what each integration can do.
    Used by the AI to generate valid workflows.
    """
    
    # What each integration provider can do
    OPERATIONS = {
        # QuickBooks
        "quickbooks": {
            "query_invoices": {"label": "Query Invoices", "params": ["status", "customer", "date_range"]},
            "get_invoice": {"label": "Get Invoice", "params": ["invoice_id"]},
            "create_invoice": {"label": "Create Invoice", "params": ["customer_id", "line_items"]},
            "send_invoice": {"label": "Send Invoice", "params": ["invoice_id", "email"]},
            "query_customers": {"label": "Query Customers", "params": []},
            "get_customer": {"label": "Get Customer", "params": ["customer_id"]},
            "query_estimates": {"label": "Query Estimates", "params": ["status"]},
            "create_estimate": {"label": "Create Estimate", "params": ["customer_id", "line_items"]},
            "query_expenses": {"label": "Query Expenses", "params": ["date_range"]},
            "get_company_info": {"label": "Get Company Info", "params": []},
            "query Payments": {"label": "Query Payments", "params": ["invoice_id"]},
        },
        
        # Google
        "google": {
            "gmail_send": {"label": "Send Email", "params": ["to", "subject", "body"]},
            "gmail_read": {"label": "Read Emails", "params": ["query", "max_results"]},
            "calendar_events": {"label": "List Events", "params": ["time_min", "time_max"]},
            "calendar_create": {"label": "Create Event", "params": ["summary", "start", "end", "attendees"]},
            "contacts_find": {"label": "Find Contact", "params": ["name"]},
            "drive_upload": {"label": "Upload File", "params": ["file_name", "content"]},
        },
        
        # GoDaddy
        "godaddy": {
            "list_domains": {"label": "List Domains", "params": []},
            "get_dns_records": {"label": "Get DNS Records", "params": ["domain"]},
            "add_dns_record": {"label": "Add DNS Record", "params": ["domain", "type", "name", "value"]},
            "get_domain_info": {"label": "Get Domain Info", "params": ["domain"]},
        },
        
        # Shopify
        "shopify": {
            "list_orders": {"label": "List Orders", "params": ["status", "limit"]},
            "get_order": {"label": "Get Order", "params": ["order_id"]},
            "list_products": {"label": "List Products", "params": []},
            "update_product": {"label": "Update Product", "params": ["product_id", "updates"]},
            "list_customers": {"label": "List Customers", "params": []},
        },
        
        # Squarespace
        "squarespace": {
            "list_orders": {"label": "List Orders", "params": []},
            "list_products": {"label": "List Products", "params": []},
            "update_product": {"label": "Update Product", "params": ["product_id", "updates"]},
            "get_website": {"label": "Get Website Info", "params": []},
        },
        
        # Resend (email)
        "resend": {
            "send_email": {"label": "Send Email", "params": ["to", "subject", "body", "from_name"]},
        },
    }
    
    @classmethod
    def get_available_operations(cls, user_integrations: List[str]) -> Dict[str, Dict]:
        """Get all operations available based on user's integrations."""
        available = {}
        for integration in user_integrations:
            if integration in cls.OPERATIONS:
                available[integration] = cls.OPERATIONS[integration]
        return available
    
    @classmethod
    def get_operation_signature(cls, integration: str, operation: str) -> Optional[Dict]:
        """Get the signature for a specific operation."""
        return cls.OPERATIONS.get(integration, {}).get(operation)


# ============================================================================
# WORKFLOW GENERATOR
# ============================================================================

class WorkflowGenerator:
    """
    AI-powered workflow generation.
    Takes user goals + available capabilities → generates workflow JSON.
    """
    
    SYSTEM_PROMPT = """You are a workflow design expert. Generate workflow definitions in JSON format.

The user wants to accomplish: {goal}

Available integrations and their capabilities:
{capabilities}

Generate a workflow that:
1. Uses ONLY the available operations listed above
2. Has clear, sequential steps
3. Includes appropriate error handling
4. Can be executed autonomously

Respond with ONLY valid JSON (no markdown), using this schema:
{{
    "name": "workflow name",
    "description": "what it does",
    "trigger_type": "manual|scheduled|event|condition",
    "trigger_config": {{"cron": "0 7 * * *"|"event": "order.created"|"condition": "invoice.overdue"}} ,
    "steps": [
        {{
            "id": "step_1",
            "type": "query|action|condition|notify|wait",
            "description": "what this step does",
            "integration": "quickbooks|google|godaddy|shopify|resend",
            "operation": "operation_name",
            "params": {{"key": "value"}},
            "on_true": "step_2",
            "on_false": "step_3"
        }}
    ]
}}

If no integrations support the requested goal, return:
{{"error": "No available integrations support this workflow"}}
"""

    @classmethod
    def generate_workflow(cls, goal: str, user_integrations: List[str]) -> Dict:
        """Generate a workflow based on user goal and available integrations."""
        available = CapabilityRegistry.get_available_operations(user_integrations)
        
        # Format capabilities for prompt
        capabilities_str = json.dumps(available, indent=2)
        
        # Build prompt
        prompt = cls.SYSTEM_PROMPT.format(
            goal=goal,
            capabilities=capabilities_str
        )
        
        # Call LLM to generate workflow
        # This would use the existing LLM client
        return {
            "prompt": prompt,
            "available_operations": available,
            "goal": goal
        }
    
    @classmethod
    def parse_llm_response(cls, response: str) -> Workflow:
        """Parse LLM response into a Workflow object."""
        try:
            data = json.loads(response)
            
            if "error" in data:
                raise ValueError(data["error"])
            
            # Convert step dicts to WorkflowStep objects
            steps = []
            for step_data in data.get("steps", []):
                step = WorkflowStep(
                    id=step_data["id"],
                    type=StepType(step_data["type"]),
                    description=step_data.get("description", ""),
                    integration=step_data.get("integration"),
                    operation=step_data.get("operation"),
                    params=step_data.get("params", {}),
                    condition=step_data.get("condition"),
                    on_true=step_data.get("on_true"),
                    on_false=step_data.get("on_false"),
                    channel=step_data.get("channel"),
                    template=step_data.get("template"),
                    duration_seconds=step_data.get("duration_seconds"),
                )
                steps.append(step)
            
            workflow = Workflow(
                id=data.get("id", f"wf_{hash(goal)[:8]}"),
                name=data["name"],
                description=data.get("description", ""),
                trigger_type=TriggerType(data.get("trigger_type", "manual")),
                trigger_config=data.get("trigger_config", {}),
                steps=steps,
                created_by="operator"
            )
            
            return workflow
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid workflow JSON: {e}")


# ============================================================================
# WORKFLOW EXECUTOR
# ============================================================================

class WorkflowExecutor:
    """
    Executes generated workflows step by step.
    """
    
    def __init__(self, user_id: str, integration_executors: Dict[str, Callable]):
        """
        Args:
            user_id: User running the workflow
            integration_executors: Dict mapping integration name -> callable
                                   e.g., {"quickbooks": qb_query, "resend": send_email}
        """
        self.user_id = user_id
        self.executors = integration_executors
        self.results = {}
    
    async def execute_step(self, step: WorkflowStep, context: Dict) -> Dict:
        """Execute a single workflow step."""
        log.info(f"Executing step {step.id}: {step.description}")
        
        try:
            if step.type == StepType.QUERY:
                return await self._execute_query(step, context)
            elif step.type == StepType.ACTION:
                return await self._execute_action(step, context)
            elif step.type == StepType.CONDITION:
                return self._evaluate_condition(step, context)
            elif step.type == StepType.NOTIFY:
                return await self._execute_notify(step, context)
            elif step.type == StepType.WAIT:
                return await self._execute_wait(step, context)
            else:
                return {"success": False, "error": f"Unknown step type: {step.type}"}
                
        except Exception as e:
            log.error(f"Step {step.id} failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _execute_query(self, step: WorkflowStep, context: Dict) -> Dict:
        """Execute a query step."""
        executor = self.executors.get(step.integration)
        if not executor:
            return {"success": False, "error": f"No executor for {step.integration}"}
        
        # Merge step params with context
        params = self._resolve_params(step.params or {}, context)
        
        result = executor(**params)
        self.results[step.id] = result
        
        return {"success": True, "data": result}
    
    async def _execute_action(self, step: WorkflowStep, context: Dict) -> Dict:
        """Execute an action step."""
        executor = self.executors.get(step.integration)
        if not executor:
            return {"success": False, "error": f"No executor for {step.integration}"}
        
        params = self._resolve_params(step.params or {}, context)
        
        result = executor(**params)
        self.results[step.id] = result
        
        return {"success": True, "data": result}
    
    def _evaluate_condition(self, step: WorkflowStep, context: Dict) -> Dict:
        """Evaluate a condition and determine next step."""
        # Simple condition evaluation
        # In production, this would use a proper expression evaluator
        condition = step.condition
        
        # Check if condition references previous results
        for step_id, result in self.results.items():
            if step_id in condition:
                # Replace with actual value
                condition = condition.replace(step_id, str(result))
        
        # Evaluate (very basic - should use safe eval in production)
        try:
            # Very simplistic - just check for truthy values
            eval_result = "true" in condition.lower() or "==" in condition
        except:
            eval_result = False
        
        next_step = step.on_true if eval_result else step.on_false
        
        return {
            "success": True,
            "condition_met": eval_result,
            "next_step": next_step
        }
    
    async def _execute_notify(self, step: WorkflowStep, context: Dict) -> Dict:
        """Execute a notification step."""
        # Use Resend or internal notification system
        executor = self.executors.get("resend") or self.executors.get("notify")
        if not executor:
            return {"success": False, "error": "No notification executor"}
        
        template = step.template or "Default notification"
        # Merge template with context
        
        result = executor(
            to=context.get("user_email"),
            subject=step.description,
            body=template
        )
        
        return {"success": True, "notification_sent": result}
    
    async def _execute_wait(self, step: WorkflowStep, context: Dict) -> Dict:
        """Execute a wait step."""
        import asyncio
        duration = step.duration_seconds or 60
        await asyncio.sleep(duration)
        return {"success": True, "waited": duration}
    
    def _resolve_params(self, params: Dict, context: Dict) -> Dict:
        """Resolve parameter values from context."""
        resolved = {}
        for key, value in params.items():
            if isinstance(value, str) and value.startswith("$"):
                # Reference to context variable
                context_key = value[1:]
                resolved[key] = context.get(context_key, value)
            else:
                resolved[key] = value
        return resolved
    
    async def execute_workflow(self, workflow: Workflow, initial_context: Dict = None) -> Dict:
        """Execute a complete workflow."""
        context = initial_context or {}
        context["user_id"] = self.user_id
        
        step_index = 0
        max_steps = len(workflow.steps) * 2  # Allow for branches
        
        while step_index < len(workflow.steps) and max_steps > 0:
            step = workflow.steps[step_index]
            
            result = await self.execute_step(step, context)
            
            if not result.get("success"):
                return {
                    "success": False,
                    "failed_step": step.id,
                    "error": result.get("error"),
                    "partial_results": self.results
                }
            
            # Handle condition branching
            if step.type == StepType.CONDITION:
                next_step_id = result.get("next_step")
                if next_step_id:
                    # Find next step by ID
                    for i, s in enumerate(workflow.steps):
                        if s.id == next_step_id:
                            step_index = i
                            break
                    continue
            
            step_index += 1
            max_steps -= 1
        
        return {
            "success": True,
            "results": self.results
        }


# ============================================================================
# WORKFLOW REGISTRY
# ============================================================================

class WorkflowRegistry:
    """
    Stores and manages generated workflows.
    """
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    def save_workflow(self, user_id: str, workflow: Workflow) -> str:
        """Save a generated workflow."""
        # Would save to database
        pass
    
    def get_workflows(self, user_id: str) -> List[Workflow]:
        """Get all workflows for a user."""
        pass
    
    def delete_workflow(self, workflow_id: str) -> bool:
        """Delete a workflow."""
        pass
    
    def enable_workflow(self, workflow_id: str, enabled: bool):
        """Enable or disable a workflow."""
        pass