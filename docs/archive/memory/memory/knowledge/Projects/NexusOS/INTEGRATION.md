# Integration Guide

This guide shows how to connect your existing agent to NexusOS memory in 5 minutes.

## For OpenClaw

Add to your OpenClaw configuration:

```json
{
  "memory": {
    "url": "http://localhost:4893",
    "type": "nexusos"
  }
}
```

## For Claude Code

### Option A: HTTP Calls (No Code Changes)

Add this to your agent's system prompt or call these endpoints after each message:

```javascript
// After each user message, call:
await fetch('http://localhost:4893/memory/working/message', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    role: 'user',
    content: userMessage
  })
});

// After each assistant response:
await fetch('http://localhost:4893/memory/working/message', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    role: 'assistant', 
    content: assistantResponse
  })
});
```

### Option B: Node.js Wrapper

```javascript
import http from 'http';

const NEXUS_URL = 'http://localhost:4893';

const nexus = {
  async startSession(sessionId) {
    return this.request('/memory/working/start', { sessionId });
  },
  
  async addMessage(role, content) {
    return this.request('/memory/working/message', { role, content });
  },
  
  async endSession() {
    return this.request('/memory/working/end', {});
  },
  
  async searchMemory(query, limit = 5) {
    return this.request('/memory/episodic/search', { query, topK: limit });
  },
  
  async request(endpoint, data) {
    return new Promise((resolve, reject) => {
      const req = http.request(`${NEXUS_URL}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      }, (res) => {
        let body = '';
        res.on('data', chunk => body += chunk);
        res.on('end', () => resolve(JSON.parse(body)));
      });
      req.on('error', reject);
      req.write(JSON.stringify(data));
      req.end();
    });
  }
};

export default nexus;
```

## For LangChain / AutoGen

```python
import requests
import os

class NexusMemory:
    def __init__(self, base_url="http://localhost:4893"):
        self.base_url = base_url
        self.session_id = None
    
    def start_session(self, session_id=None):
        resp = requests.post(
            f"{self.base_url}/memory/working/start",
            json={"sessionId": session_id}
        )
        self.session_id = resp.json().get("sessionId")
        return self.session_id
    
    def add_message(self, role, content):
        requests.post(
            f"{self.base_url}/memory/working/message",
            json={"role": role, "content": content}
        )
    
    def end_session(self):
        requests.post(f"{self.base_url}/memory/working/end")
    
    def search(self, query, limit=5):
        resp = requests.post(
            f"{self.base_url}/memory/episodic/search",
            json={"query": query, "topK": limit}
        )
        return resp.json().get("results", [])

# Usage with LangChain
memory = NexusMemory()
memory.start_session("my-agent-session")

# In your agent loop:
memory.add_message("user", user_input)
# ... process with your agent ...
memory.add_message("assistant", response)
```

## For Custom Agents

### Session Lifecycle

```
1. START:   POST /memory/working/start  → {sessionId}
2. MESSAGE: POST /memory/working/message → {role, content}
3. ... repeat for each message ...
4. END:     POST /memory/working/end    → persists to episodic
```

### Retrieval

```
SEARCH:    POST /memory/episodic/search → {query, topK}
RECENT:    GET  /memory/episodic/recent → {limit}
CONTEXT:   GET  /memory/working/context → current session
```

## Environment Variables

Create a `.env` file:

```bash
# Server
PORT=4893

# Storage paths (Docker volumes)
LANCEDB_PATH=/nexus/memory/episodic
SQLITE_PATH=/nexus/memory/semantic/knowledge.db

# LLM (optional, for future features)
OPENROUTER_API_KEY=sk-or-...
```

## Testing Your Integration

```bash
# 1. Start NexusOS
docker compose up -d

# 2. Check health
curl http://localhost:4893/health

# 3. Start a session
curl -X POST http://localhost:4893/memory/working/start \
  -H "Content-Type: application/json" \
  -d '{"sessionId": "test-123"}'

# 4. Add a message
curl -X POST http://localhost:4893/memory/working/message \
  -H "Content-Type: application/json" \
  -d '{"role": "user", "content": "Remember: I prefer responses under 100 words"}'

# 5. End session (saves to persistent memory)
curl -X POST http://localhost:4893/memory/working/end

# 6. Search memory (new session)
curl -X POST http://localhost:4893/memory/working/start \
  -H "Content-Type: application/json" \
  -d '{"sessionId": "test-456"}'

curl -X POST http://localhost:4893/memory/episodic/search \
  -H "Content-Type: application/json" \
  -d '{"query": "prefer responses", "topK": 5}'
```

---

**Need help?** Open an issue on GitHub.