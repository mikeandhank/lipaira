"""Slack integration skills for Lipaira.

Provides skills for interacting with Slack:
- SlackPostSkill: Post messages to channels
- SlackReadChannelSkill: Read recent messages from channels
- SlackDMSendSkill: Send direct messages to users

Key functions/classes:
    SlackPostSkill: Posts message to a specified Slack channel
    SlackReadChannelSkill: Reads recent messages from a channel
    SlackDMSendSkill: Sends direct message to a Slack user
"""
from skills.registry import BaseSkill
from lipaira_client.skills.slack_skills import (
    SlackPostSkill as _SlackPostSkill,
    SlackReadChannelSkill as _SlackReadChannelSkill,
    SlackDMSendSkill as _SlackDMSendSkill
)


class SlackPostSkill(BaseSkill):
    """Post a message to a Slack channel."""
    name = "slack_post"
    description = "Post a message to a Slack channel"
    required_integrations = ["slack"]
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "channel": {"type": "string", "description": "Channel name (e.g., #general)"},
                "message": {"type": "string", "description": "Message to post"}
            },
            "required": ["channel", "message"]
        }
    
    def can_execute(self, user_id: str, business_id: str = None) -> dict:
        from skills.base import get_integration_tokens
        try:
            get_integration_tokens(user_id, business_id, 'slack')
            return {"can_run": True, "missing": [], "message": "Ready"}
        except ValueError as e:
            return {"can_run": False, "missing": ["slack"], "message": str(e)}
    
    def execute(self, input: dict, user_id: str, business_id: str = None) -> dict:
        skill = _SlackPostSkill()
        result = skill.execute(input)
        return {"success": result.success, "output": result.output, "error": result.error}


class SlackReadChannelSkill(BaseSkill):
    """Read messages from a Slack channel."""
    name = "slack_read_channel"
    description = "Read recent messages from a Slack channel"
    required_integrations = ["slack"]
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "channel": {"type": "string", "description": "Channel name"},
                "limit": {"type": "integer", "default": 10}
            },
            "required": ["channel"]
        }
    
    def can_execute(self, user_id: str, business_id: str = None) -> dict:
        from skills.base import get_integration_tokens
        try:
            get_integration_tokens(user_id, business_id, 'slack')
            return {"can_run": True, "missing": [], "message": "Ready"}
        except ValueError as e:
            return {"can_run": False, "missing": ["slack"], "message": str(e)}
    
    def execute(self, input: dict, user_id: str, business_id: str = None) -> dict:
        skill = _SlackReadChannelSkill()
        result = skill.execute(input)
        return {"success": result.success, "output": result.output, "error": result.error}


class SlackDMSendSkill(BaseSkill):
    """Send a direct message in Slack."""
    name = "slack_dm_send"
    description = "Send a direct message to a Slack user"
    required_integrations = ["slack"]
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "user": {"type": "string", "description": "User ID or email"},
                "message": {"type": "string", "description": "Message to send"}
            },
            "required": ["user", "message"]
        }
    
    def can_execute(self, user_id: str, business_id: str = None) -> dict:
        from skills.base import get_integration_tokens
        try:
            get_integration_tokens(user_id, business_id, 'slack')
            return {"can_run": True, "missing": [], "message": "Ready"}
        except ValueError as e:
            return {"can_run": False, "missing": ["slack"], "message": str(e)}
    
    def execute(self, input: dict, user_id: str, business_id: str = None) -> dict:
        skill = _SlackDMSendSkill()
        result = skill.execute(input)
        return {"success": result.success, "output": result.output, "error": result.error}


__all__ = ['SlackPostSkill', 'SlackReadChannelSkill', 'SlackDMSendSkill']