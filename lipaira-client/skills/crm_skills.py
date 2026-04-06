"""
Universal CRM skills. Work across all connected CRMs.
"""
import os
import requests
from .base import BaseSkill, SkillResult

GATEWAY_URL = os.environ.get('GATEWAY_URL', 'http://lipaira-api:8080')
USER_ID = os.environ.get('USER_ID')


def crm_get(endpoint: str, params: dict = None) -> dict:
    resp = requests.get(
        f'{GATEWAY_URL}{endpoint}',
        headers={'X-User-ID': USER_ID},
        params=params, timeout=30
    )
    resp.raise_for_status()
    return resp.json()


def crm_post(endpoint: str, body: dict) -> dict:
    resp = requests.post(
        f'{GATEWAY_URL}{endpoint}',
        headers={'X-User-ID': USER_ID, 'Content-Type': 'application/json'},
        json=body, timeout=30
    )
    resp.raise_for_status()
    return resp.json()


class CRMContactLookupSkill(BaseSkill):
    name = "crm_contact_lookup"
    description = "Look up a contact across all connected CRMs by name or email."

    def get_input_schema(self):
        return {"type": "object", "properties": {"name": {"type": "string"}, "email": {"type": "string"}}}

    def execute(self, input: dict) -> SkillResult:
        try:
            data = crm_get('/api/crm/contacts/search', {"name": input.get("name", ""), "email": input.get("email", "")})
            return SkillResult(success=True, output=data)
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))


class CRMContactCreateSkill(BaseSkill):
    name = "crm_contact_create"
    description = "Create a new contact in all connected CRMs."

    def get_input_schema(self):
        return {"type": "object", "properties": {"name": {"type": "string"}, "email": {"type": "string"}, "phone": {"type": "string"}, "company": {"type": "string"}, "address": {"type": "string"}}, "required": ["name"]}

    def execute(self, input: dict) -> SkillResult:
        try:
            data = crm_post('/api/crm/contacts', input)
            return SkillResult(success=True, output={"contact_id": data.get("id"), "name": input["name"], "message": f"Contact '{input['name']}' created"})
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))


class CRMDealCreateSkill(BaseSkill):
    name = "crm_deal_create"
    description = "Create a new deal/opportunity in all connected CRMs."

    def get_input_schema(self):
        return {"type": "object", "properties": {"title": {"type": "string"}, "contact_name": {"type": "string"}, "value": {"type": "number"}, "stage": {"type": "string", "enum": ["new", "qualified", "proposal", "negotiation", "won", "lost"], "default": "new"}, "close_date": {"type": "string"}, "notes": {"type": "string"}}, "required": ["title"]}

    def execute(self, input: dict) -> SkillResult:
        try:
            data = crm_post('/api/crm/deals', input)
            return SkillResult(success=True, output={"deal_id": data.get("id"), "title": input["title"], "value": f"${float(input.get('value', 0)):,.2f}", "message": f"Deal '{input['title']}' created"})
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))


class CRMDealUpdateSkill(BaseSkill):
    name = "crm_deal_update"
    description = "Update a deal's stage, value, or close date."

    def get_input_schema(self):
        return {"type": "object", "properties": {"deal_title": {"type": "string"}, "stage": {"type": "string", "enum": ["new", "qualified", "proposal", "negotiation", "won", "lost"]}, "value": {"type": "number"}, "close_date": {"type": "string"}}, "required": ["deal_title"]}

    def execute(self, input: dict) -> SkillResult:
        try:
            data = crm_post('/api/crm/deals/update', input)
            return SkillResult(success=True, output={"message": f"Deal '{input['deal_title']}' updated"})
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))


class CRMNoteLogSkill(BaseSkill):
    name = "crm_note_log"
    description = "Log a note against a contact."

    def get_input_schema(self):
        return {"type": "object", "properties": {"contact_name": {"type": "string"}, "content": {"type": "string"}, "type": {"type": "string", "enum": ["note", "call", "email", "meeting"], "default": "note"}}, "required": ["contact_name", "content"]}

    def execute(self, input: dict) -> SkillResult:
        try:
            data = crm_post('/api/crm/notes', input)
            return SkillResult(success=True, output={"message": f"Note logged against {input['contact_name']}"})
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))


class CRMTaskCreateSkill(BaseSkill):
    name = "crm_task_create"
    description = "Create a follow-up task in all connected CRMs."

    def get_input_schema(self):
        return {"type": "object", "properties": {"contact_name": {"type": "string"}, "title": {"type": "string"}, "due_date": {"type": "string"}, "notes": {"type": "string"}}, "required": ["title"]}

    def execute(self, input: dict) -> SkillResult:
        try:
            data = crm_post('/api/crm/tasks', input)
            return SkillResult(success=True, output={"message": f"Task '{input['title']}' created" + (f" - due {input['due_date']}" if input.get("due_date") else "")})
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))


class CRMDealListSkill(BaseSkill):
    name = "crm_deal_list"
    description = "List open deals from all connected CRMs."

    def get_input_schema(self):
        return {"type": "object", "properties": {"stage": {"type": "string", "enum": ["new", "qualified", "proposal", "negotiation", "won", "lost", "all"], "default": "all"}, "max_results": {"type": "integer", "default": 20}}}

    def execute(self, input: dict) -> SkillResult:
        try:
            data = crm_get('/api/crm/deals', {"stage": input.get("stage", "all"), "max_results": input.get("max_results", 20)})
            return SkillResult(success=True, output=data)
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))


class CRMPipelineSummarySkill(BaseSkill):
    name = "crm_pipeline_summary"
    description = "Get a summary of the sales pipeline - deals by stage and total value."

    def get_input_schema(self):
        return {"type": "object", "properties": {}}

    def execute(self, input: dict) -> SkillResult:
        try:
            data = crm_get('/api/crm/pipeline/summary')
            return SkillResult(success=True, output=data)
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))