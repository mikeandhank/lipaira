"""YouTube transcript extraction skill for Lipaira."""

import re
import json

async def run(query, context):
    """Get YouTube video transcript."""
    
    url = query.strip()
    
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
        return {
            "success": False,
            "error": "Could not extract video ID from URL. Provide a valid YouTube URL or video ID.",
            "output": None
        }
    
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        
        api = YouTubeTranscriptApi()
        transcripts = api.list(video_id=video_id)
        
        try:
            transcript = transcripts.find_transcript(['en'])
        except:
            transcript = transcripts.find_transcript()
        
        fetched = transcript.fetch()
        
        # Access snippets - they're FetchedTranscriptSnippet objects
        snippets = fetched.snippets
        full_text = " ".join([s.text for s in snippets])
        
        truncated = len(full_text) > 20000
        text = full_text[:20000] + (" (truncated)" if truncated else "")
        
        return {
            "success": True,
            "output": {
                "video_id": video_id,
                "transcript": text,
                "truncated": truncated,
                "word_count": len(full_text.split())
            }
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "output": None
        }
