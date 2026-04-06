"""
Discord integration skill - wraps lipaira-client version.
"""
from skills.registry import BaseSkill
from lipaira_client.skills.discord_skill import DiscordSendSkill as _DiscordSendSkill


class DiscordSendSkill(BaseSkill):
    """Send a message to a Discord channel."""
    name = "discord_send"
    description = "Send a message to a Discord channel"
    required_integrations = ["discord"]
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "channel_id": {"type": "string", "description": "Discord channel ID"},
                "message": {"type": "string", "description": "Message to send"}
            },
            "required": ["channel_id", "message"]
        }
    
    def can_execute(self, user_id: str, business_id: str = None) -> dict:
        from skills.base import get_integration_tokens
        try:
            get_integration_tokens(user_id, business_id, 'discord')
            return {"can_run": True, "missing": [], "message": "Ready"}
        except ValueError as e:
            return {"can_run": False, "missing": ["discord"], "message": str(e)}
    
    def execute(self, input: dict, user_id: str, business_id: str = None) -> dict:
        skill = _DiscordSendSkill()
        result = skill.execute(input)
        return {"success": result.success, "output": result.output, "error": result.error}


__all__ = ['DiscordSendSkill']