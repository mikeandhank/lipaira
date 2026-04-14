import os
import requests
from .base import BaseSkill, SkillResult

class DiscordSendSkill(BaseSkill):
    name = "discord_send"
    description = "Send a message to a Discord channel via webhook."
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "webhook_url": {"type": "string"},
                "message": {"type": "string", "description": "Message content"},
                "embed": {"type": "object", "description": "Optional Discord embed"}
            },
            "required": ["message"]
        }
    
    def execute(self, input: dict) -> SkillResult:
        webhook_url = input.get("webhook_url") or os.environ.get("DISCORD_WEBHOOK_URL")
        
        if not webhook_url:
            return SkillResult(success=False, output=None,
                error="Discord webhook not configured")
        
        message = input.get("message", "")
        
        payload = {"content": message}
        
        if input.get("embed"):
            payload["embeds"] = [input["embed"]]
        
        try:
            response = requests.post(webhook_url, json=payload, timeout=10)
            if response.status_code in (200, 204):
                return SkillResult(success=True, output={"message": "Sent to Discord"})
            else:
                return SkillResult(success=False, output=None,
                    error=f"Discord error: {response.status_code}")
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))
