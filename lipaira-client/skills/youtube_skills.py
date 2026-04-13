"""
YouTube Skills
==============
Fetch YouTube video transcripts.
"""
import re
from .base import BaseSkill, SkillResult

class YouTubeTranscriptSkill(BaseSkill):
    name = "youtube_transcript"
    description = (
        "Get the transcript of a YouTube video. "
        "Use when asked to summarize, analyze, or extract information from a YouTube URL."
    )
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "YouTube URL or video ID"
                },
                "max_chars": {
                    "type": "integer",
                    "default": 20000,
                    "description": "Max characters to return"
                }
            },
            "required": ["url"]
        }

    def execute(self, input: dict) -> SkillResult:
        url = input.get("url", "")
        max_chars = min(input.get("max_chars", 20000), 25000)

        # Extract video ID from various URL formats
        patterns = [
            r"youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
            r"youtu\.be/([a-zA-Z0-9_-]{11})",
            r"youtube\.com/shorts/([a-zA-Z0-9_-]{11})",
            r"^([a-zA-Z0-9_-]{11})$"
        ]
        video_id = None
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                video_id = match.group(1)
                break

        if not video_id:
            return SkillResult(success=False, output=None,
                error="Could not extract video ID from URL")

        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            transcript = youtube_transcript_api.YouTubeTranscriptApi.get_transcript(video_id)
            full_text = " ".join([t['text'] for t in transcript])
            
            return SkillResult(success=True, output={
                "video_id": video_id,
                "transcript": full_text[:max_chars],
                "truncated": len(full_text) > max_chars,
                "word_count": len(full_text.split())
            })
        except Exception as e:
            return SkillResult(success=False, output=None, error=str(e))
