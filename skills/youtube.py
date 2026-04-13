"""YouTube integration skill for Lipaira.

Provides skills for interacting with YouTube:
- YouTubeTranscriptSkill: Get transcripts from YouTube videos

Key functions/classes:
    YouTubeTranscriptSkill: Fetches and parses transcripts from YouTube videos
"""
from skills.registry import BaseSkill
from lipaira_client.skills.youtube_skills import YouTubeTranscriptSkill as _YouTubeTranscriptSkill


class YouTubeTranscriptSkill(BaseSkill):
    """Get transcript from a YouTube video."""
    name = "youtube_transcript"
    description = "Get transcript from a YouTube video"
    required_integrations = []  # Uses YouTube API directly
    
    def get_input_schema(self):
        return {"type": "object", "properties": {"video_url": {"type": "string"}}, "required": ["video_url"]}
    
    def can_execute(self, user_id: str, business_id: str = None) -> dict:
        return {"can_run": True, "missing": [], "message": "Ready"}
    
    def execute(self, input: dict, user_id: str, business_id: str = None) -> dict:
        skill = _YouTubeTranscriptSkill()
        result = skill.execute(input)
        return {"success": result.success, "output": result.output, "error": result.error}


__all__ = ['YouTubeTranscriptSkill']