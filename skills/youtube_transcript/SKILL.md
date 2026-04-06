---
name: youtube_transcript
description: Get transcripts from YouTube videos for summarization and research
metadata:
  {
    "openclaw": { "emoji": "🎬", "requires": { "pip": ["youtube-transcript-api"] } }
  }
---

# youtube_transcript

Get the transcript of any YouTube video. Useful for researching content, summarizing videos, and extracting information without watching.

## Setup

```bash
pip install youtube-transcript-api
```

## Usage

Provide a YouTube URL or video ID:

- Full URL: `https://www.youtube.com/watch?v=dQw4w9WgXcQ`
- Short URL: `https://youtu.be/dQw4w9WgXcQ`
- Video ID only: `dQw4w9WgXcQ`

Returns the full transcript text. The agent will summarize key points.

## Limitations

- Videos without captions (disabled) will fail
- Age-restricted videos may fail
- Very new videos may need a few minutes for auto-captions to generate
