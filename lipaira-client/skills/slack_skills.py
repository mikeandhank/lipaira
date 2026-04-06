"""
Slack skills for posting messages, reading channels, and sending DMs.
"""
import os
import requests
from .base import BaseSkill, SkillResult

GATEWAY_URL = os.environ.get('GATEWAY_URL', 'http://lipaira-api:80')
USER_ID = os.environ.get('USER_ID', 'default')
SLACK_BASE = "https://slack.com/api"


def get_slack_token():
    import os
    return os.environ.get('SLACK_BOT_TOKEN')


def check_slack_permission(capability: str) -> bool:
    """Check if user has granted a specific Slack capability."""
    try:
        resp = requests.get(
            f'{GATEWAY_URL}/api/internal/check-permission',
            headers={'X-User-ID': USER_ID},
            params={'provider': 'slack', 'capability': capability},
            timeout=10
        )
        return resp.json().get('granted', False)
    except:
        return True  # Default to allowing if can't check


class SlackPostSkill:
    name = "slack_post"
    description = "Post a message to a Slack channel."
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "channel": {"type": "string", "description": "Channel name e.g. #general"},
                "message": {"type": "string"}
            },
            "required": ["channel", "message"]
        }
    
    def execute(self, input: dict):
        from .base import SkillResult
        try:
            token = get_slack_token()
            if not token:
                return SkillResult(success=False, output=None, error="Slack not connected")
            
            body = {
                "channel": input["channel"],
                "text": input["message"]
            }
            
            resp = requests.post(
                f"{SLACK_BASE}/chat.postMessage",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=body,
                timeout=30
            ).json()
            
            if not resp.get("ok"):
                return SkillResult(success=False, output=None, error=resp.get("error", "Failed to post"))
            
            return SkillResult(success=True, output={
                "ts": resp.get("ts"),
                "message": f"Posted to {input['channel']}"
            })
        except Exception as e:
            from .base import SkillResult
            return SkillResult(success=False, output=None, error=str(e))


class SlackReadChannelSkill:
    name = "slack_read_channel"
    description = "Read recent messages from a Slack channel."
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "channel": {"type": "string"},
                "max_results": {"type": "integer", "default": 20}
            },
            "required": ["channel"]
        }
    
    def execute(self, input: dict):
        from .base import SkillResult
        try:
            if not check_slack_permission('read.selected'):
                return SkillResult(success=False, output=None, 
                    error="Permission denied: 'Read selected channels' not granted")
            
            token = get_slack_token()
            if not token:
                return SkillResult(success=False, output=None, error="Slack not connected")
            
            # Get channel ID
            resp = requests.get(
                f"{SLACK_BASE}/conversations.list",
                headers={"Authorization": f"Bearer {token}"},
                params={"types": "public_channel,private_channel"},
                timeout=30
            ).json()
            
            channel_id = None
            channel_name = input["channel"].lstrip("#")
            for ch in resp.get("channels", []):
                if ch.get("name") == channel_name:
                    channel_id = ch["id"]
                    break
            
            if not channel_id:
                return SkillResult(success=False, output=None, error=f"Channel #{channel_name} not found")
            
            # Get history
            resp = requests.get(
                f"{SLACK_BASE}/conversations.history",
                headers={"Authorization": f"Bearer {token}"},
                params={"channel": channel_id, "limit": input.get("max_results", 20)},
                timeout=30
            ).json()
            
            messages = [{"user": m.get("user", ""), "text": m.get("text", ""), "ts": m.get("ts", "")} 
                       for m in resp.get("messages", [])]
            
            return SkillResult(success=True, output=messages)
        except Exception as e:
            from .base import SkillResult
            return SkillResult(success=False, output=None, error=str(e))


class SlackDMSendSkill:
    name = "slack_dm_send"
    description = "Send a direct message to a team member."
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Username or email"},
                "message": {"type": "string"}
            },
            "required": ["to", "message"]
        }
    
    def execute(self, input: dict):
        from .base import SkillResult
        try:
            if not check_slack_permission('dm.send'):
                return SkillResult(success=False, output=None,
                    error="Permission denied: 'Send direct messages' not granted")
            
            token = get_slack_token()
            if not token:
                return SkillResult(success=False, output=None, error="Slack not connected")
            
            # Get user ID
            resp = requests.get(
                f"{SLACK_BASE}/users.lookupByEmail",
                headers={"Authorization": f"Bearer {token}"},
                params={"email": input["to"]},
                timeout=30
            ).json()
            
            user_id = resp.get("user", {}).get("id")
            if not user_id:
                return SkillResult(success=False, output=None, error=f"User {input['to']} not found")
            
            # Send DM
            resp = requests.post(
                f"{SLACK_BASE}/chat.postMessage",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"channel": user_id, "text": input["message"]},
                timeout=30
            ).json()
            
            if not resp.get("ok"):
                return SkillResult(success=False, output=None, error=resp.get("error"))
            
            return SkillResult(success=True, output={"message": f"DM sent to {input['to']}"})
        except Exception as e:
            from .base import SkillResult
            return SkillResult(success=False, output=None, error=str(e))