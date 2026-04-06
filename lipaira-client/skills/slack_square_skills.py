"""Slack and Square skills."""
import os
import requests
from .base import BaseSkill, SkillResult

GATEWAY_URL = os.environ.get('GATEWAY_URL', 'http://lipaira-api:8080')
SLACK_BASE = "https://slack.com/api"
SQUARE_BASE = "https://connect.squareup.com/v2"

# Slack skills
class SlackPostSkill(BaseSkill):
    name = "slack_post"
    description = "Post a message to a Slack channel."

    def get_input_schema(self):
        return {"type": "object", "properties": {"channel": {"type": "string"}, "message": {"type": "string"}}, "required": ["channel", "message"]}

    def execute(self, input: dict) -> SkillResult:
        try:
            resp = requests.get(f"{GATEWAY_URL}/api/internal/slack-token", timeout=10)
            if resp.status_code == 404:
                return SkillResult(success=False, output=None, error="Slack not connected")
            token = resp.json().get('token')
            
            resp = requests.post(f"{SLACK_BASE}/chat.postMessage",
                                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                                json={"channel": input['channel'], "text": input['message']}).json()
            
            if not resp.get("ok"):
                return SkillResult(success=False, output=None, error=resp.get("error"))
            
            return SkillResult(success=True, output={"ts": resp.get("ts"), "message": f"Posted to {input['channel']}"})
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))


class SlackReadChannelSkill(BaseSkill):
    name = "slack_read_channel"
    description = "Read recent messages from a Slack channel."

    def get_input_schema(self):
        return {"type": "object", "properties": {"channel": {"type": "string"}, "max_results": {"type": "integer", "default": 20}}, "required": ["channel"]}

    def execute(self, input: dict) -> SkillResult:
        try:
            resp = requests.get(f"{GATEWAY_URL}/api/internal/slack-token", timeout=10)
            if resp.status_code == 404:
                return SkillResult(success=False, output=None, error="Slack not connected")
            token = resp.json().get('token')
            
            # Get channel ID
            channels = requests.get(f"{SLACK_BASE}/conversations.list",
                                   headers={"Authorization": f"Bearer {token}"},
                                   params={"types": "public_channel,private_channel"}).json()
            
            channel_id = None
            channel_name = input["channel"].lstrip("#")
            for ch in channels.get("channels", []):
                if ch.get("name") == channel_name:
                    channel_id = ch["id"]
                    break
            
            if not channel_id:
                return SkillResult(success=False, output=None, error=f"Channel #{channel_name} not found")
            
            history = requests.get(f"{SLACK_BASE}/conversations.history",
                                  headers={"Authorization": f"Bearer {token}"},
                                  params={"channel": channel_id, "limit": input.get("max_results", 20)}).json()
            
            messages = [{"user": msg.get("user", ""), "text": msg.get("text", ""), "ts": msg.get("ts", "")} 
