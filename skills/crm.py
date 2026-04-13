"""CRM skills for Lipaira.

Provides skills for interacting with an internal CRM system via lipaira-client.
These skills manage contacts, deals, pipeline, and tasks without requiring
external OAuth integration.

Key functions/classes:
    CRMContactLookupSkill: Search for contacts in the CRM
    CRMContactCreateSkill: Create new CRM contacts
    CRMDealCreateSkill: Create new deals in the CRM
    CRMPipelineSummarySkill: Get pipeline overview and deal summaries
"""
from skills.registry import BaseSkill
from lipaira_client.skills.crm_skills import (
    CRMContactLookupSkill as _CRMContactLookupSkill,
    CRMContactCreateSkill as _CRMContactCreateSkill,
    CRMDealCreateSkill as _CRMDealCreateSkill,
    CRMDealUpdateSkill as _CRMDealUpdateSkill,
    CRMNoteLogSkill as _CRMNoteLogSkill,
    CRMTaskCreateSkill as _CRMTaskCreateSkill,
    CRMDealListSkill as _CRMDealListSkill,
    CRMPipelineSummarySkill as _CRMPipelineSummarySkill
)


class CRMContactLookupSkill(BaseSkill):
    name = "crm_contact_lookup"
    description = "Look up a contact in CRM"
    required_integrations = []  # Uses internal CRM
    
    def get_input_schema(self):
        return {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
    
    def can_execute(self, user_id: str, business_id: str = None) -> dict:
        return {"can_run": True, "missing": [], "message": "Ready"}
    
    def execute(self, input: dict, user_id: str, business_id: str = None) -> dict:
        skill = _CRMContactLookupSkill()
        result = skill.execute(input)
        return {"success": result.success, "output": result.output, "error": result.error}


class CRMContactCreateSkill(BaseSkill):
    name = "crm_contact_create"
    description = "Create a new contact in CRM"
    required_integrations = []
    
    def get_input_schema(self):
        return {"type": "object", "properties": {"name": {"type": "string"}, "email": {"type": "string"}, "phone": {"type": "string"}}, "required": ["name"]}
    
    def can_execute(self, user_id: str, business_id: str = None) -> dict:
        return {"can_run": True, "missing": [], "message": "Ready"}
    
    def execute(self, input: dict, user_id: str, business_id: str = None) -> dict:
        skill = _CRMContactCreateSkill()
        result = skill.execute(input)
        return {"success": result.success, "output": result.output, "error": result.error}


class CRMDealCreateSkill(BaseSkill):
    name = "crm_deal_create"
    description = "Create a new deal in CRM"
    required_integrations = []
    
    def get_input_schema(self):
        return {"type": "object", "properties": {"name": {"type": "string"}, "value": {"type": "number"}, "stage": {"type": "string"}}, "required": ["name"]}
    
    def can_execute(self, user_id: str, business_id: str = None) -> dict:
        return {"can_run": True, "missing": [], "message": "Ready"}
    
    def execute(self, input: dict, user_id: str, business_id: str = None) -> dict:
        skill = _CRMDealCreateSkill()
        result = skill.execute(input)
        return {"success": result.success, "output": result.output, "error": result.error}


class CRMPipelineSummarySkill(BaseSkill):
    name = "crm_pipeline_summary"
    description = "Get pipeline summary from CRM"
    required_integrations = []
    
    def get_input_schema(self):
        return {"type": "object", "properties": {}}
    
    def can_execute(self, user_id: str, business_id: str = None) -> dict:
        return {"can_run": True, "missing": [], "message": "Ready"}
    
    def execute(self, input: dict, user_id: str, business_id: str = None) -> dict:
        skill = _CRMPipelineSummarySkill()
        result = skill.execute(input)
        return {"success": result.success, "output": result.output, "error": result.error}


__all__ = ['CRMContactLookupSkill', 'CRMContactCreateSkill', 'CRMDealCreateSkill', 'CRMPipelineSummarySkill']