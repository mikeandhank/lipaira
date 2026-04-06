#!/usr/bin/env node
/**
 * NexusOS Memory Server
 * 
 * Three-tier memory management:
 * - Working: Current session context (RAM)
 * - Episodic: Vector storage (LanceDB)
 * - Semantic: Knowledge graph (SQLite)
 * 
 * Provides MCP-compatible interface for memory operations
 */

import express from 'express';
import bodyParser from 'body-parser';
import lancedbLib from '@lancedb/lancedb';
import sqlite3 from 'sqlite3';
import crypto from 'crypto';

const app = express();
app.use(bodyParser.json());

// Configuration
const config = {
  episodic: {
    path: process.env.LANCEDB_PATH || '/nexus/memory/episodic',
    embeddingModel: 'text-embedding-3-small'
  },
  semantic: {
    path: process.env.SQLITE_PATH || '/nexus/memory/semantic/knowledge.db'
  },
  llm: {
    provider: process.env.NEXUS_LLM_PROVIDER || 'openrouter',
    primaryModel: process.env.NEXUS_LLM_MODEL || 'openrouter/minimax/minimax-m2.5',
    fallbackModel: process.env.NEXUS_LLM_FALLBACK || 'openrouter/anthropic/claude-3-haiku',
    maxRetries: 3,
    retryDelayMs: 1000
  }
};

// Model failover system
const modelFailover = {
  currentModel: config.llm.primaryModel,
  failures: 0,
  maxFailures: 3,
  
  getModel() {
    return this.currentModel;
  },
  
  async withFailover(fn) {
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        const result = await fn(this.currentModel);
        this.failures = 0; // Reset on success
        return result;
      } catch (error) {
        console.error(`[LLM] Error with ${this.currentModel}:`, error.message);
        this.failures++;
        
        if (attempt === 0 && this.currentModel !== config.llm.fallbackModel) {
          console.log(`[LLM] Failing over to fallback model: ${config.llm.fallbackModel}`);
          this.currentModel = config.llm.fallbackModel;
        } else {
          throw error;
        }
      }
    }
  },
  
  reset() {
    this.currentModel = config.llm.primaryModel;
    this.failures = 0;
  }
};

// In-memory working memory
let workingMemory = {
  sessionId: null,
  messages: [],
  context: {},
  entities: new Map()
};

// Initialize databases
let lancedb;
let sqlite;

async function init() {
  console.log('[Memory] Initializing NexusOS Memory System...');
  
  // Initialize LanceDB for episodic memory
  try {
    lancedb = await lancedbLib.connect(config.episodic.path);
    console.log('[Memory] LanceDB connected');
  } catch (e) {
    console.warn('[Memory] LanceDB not available, using fallback:', e.message);
  }
  
  // Initialize SQLite for semantic memory
  sqlite = new sqlite3.Database(config.semantic.path);
  
  // Create tables if they don't exist
  sqlite.serialize(() => {
    sqlite.run(`
      CREATE TABLE IF NOT EXISTS entities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        properties TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `);
    
    sqlite.run(`
      CREATE TABLE IF NOT EXISTS relationships (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_entity INTEGER,
        to_entity INTEGER,
        relation_type TEXT NOT NULL,
        properties TEXT,
        FOREIGN KEY (from_entity) REFERENCES entities(id),
        FOREIGN KEY (to_entity) REFERENCES entities(id)
      )
    `);
    
    sqlite.run(`
      CREATE TABLE IF NOT EXISTS facts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_id INTEGER,
        fact TEXT NOT NULL,
        source TEXT,
        confidence REAL DEFAULT 1.0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `);
  });
  
  console.log('[Memory] Initialization complete');
}

// ============ WORKING MEMORY (RAM) ============

app.post('/memory/working/start', (req, res) => {
  const { sessionId, systemPrompt } = req.body;
  
  workingMemory = {
    sessionId: sessionId || crypto.randomUUID(),
    messages: [],
    context: { systemPrompt },
    entities: new Map()
  };
  
  console.log(`[Memory] Started working memory session: ${workingMemory.sessionId}`);
  
  res.json({ sessionId: workingMemory.sessionId });
});

app.post('/memory/working/message', (req, res) => {
  const { role, content, name } = req.body;
  
  if (!workingMemory.sessionId) {
    return res.status(400).json({ error: 'No active session' });
  }
  
  workingMemory.messages.push({ role, content, name, timestamp: Date.now() });
  
  res.json({ success: true, messageCount: workingMemory.messages.length });
});

app.get('/memory/working/context', (req, res) => {
  const limit = parseInt(req.query.limit) || 10;
  
  const recent = workingMemory.messages.slice(-limit);
  const context = workingMemory.context;
  
  res.json({ 
    sessionId: workingMemory.sessionId,
    messages: recent,
    context,
    messageCount: workingMemory.messages.length
  });
});

app.post('/memory/working/context', (req, res) => {
  const { key, value } = req.body;
  
  workingMemory.context[key] = value;
  
  res.json({ success: true });
});

app.post('/memory/working/summarize', async (req, res) => {
  // Extract key information from working memory for persistence
  const summary = {
    sessionId: workingMemory.sessionId,
    messageCount: workingMemory.messages.length,
    keyEntities: Array.from(workingMemory.entities.entries()),
    timestamp: Date.now()
  };
  
  res.json({ summary });
});

app.post('/memory/working/end', async (req, res) => {
  if (!workingMemory.sessionId) {
    return res.status(400).json({ error: 'No active session' });
  }
  
  const sessionId = workingMemory.sessionId;
  
  // Auto-persist to episodic memory
  if (lancedb && workingMemory.messages.length > 0) {
    await persistToEpisodic(workingMemory.messages, sessionId);
  }
  
  workingMemory = {
    sessionId: null,
    messages: [],
    context: {},
    entities: new Map()
  };
  
  console.log(`[Memory] Ended session: ${sessionId}`);
  
  res.json({ success: true, sessionId });
});

// ============ EPISODIC MEMORY (Vector) ============

async function persistToEpisodic(messages, sessionId) {
  if (!lancedb) return;
  
  try {
    // Remove old table and recreate fresh
    try {
      await lancedb.dropTable('episodes');
    } catch (e) {
      // Table doesn't exist, ignore
    }
    
    // Create table with initial data to establish schema
    // Schema is inferred from first batch of data
    const initialData = messages.map((m) => ({
      session_id: String(sessionId),
      content: String(m.content),
      role: String(m.role),
      timestamp: Number(m.timestamp || Date.now())
    }));
    
    const table = await lancedb.createTable('episodes', initialData);
    console.log(`[Memory] Persisted ${initialData.length} messages to episodic`);
  } catch (e) {
    console.error('[Memory] Episodic persist error:', e);
  }
}

app.post('/memory/episodic/search', async (req, res) => {
  const { query, topK = 5 } = req.body;
  
  if (!lancedb) {
    // Fallback: search in working memory
    const results = workingMemory.messages
      .filter(m => m.content.toLowerCase().includes(query.toLowerCase()))
      .slice(-topK);
    
    return res.json({ results, source: 'working' });
  }
  
  try {
    // Query LanceDB for episodic memory
    // Note: Full vector search requires embeddings - this is a text filter for now
    const table = await lancedb.openTable('episodes');
    const arrowResult = await table.toArrow();
    const allData = arrowResult ? arrowResult.toArray() : [];
    
    // Simple text search (not vector search)
    const results = allData
      .filter(m => m.content && m.content.toLowerCase().includes(query.toLowerCase()))
      .slice(-topK);
    
    res.json({ results, source: 'episodic' });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.get('/memory/episodic/recent', async (req, res) => {
  const limit = parseInt(req.query.limit) || 10;
  
  if (!lancedb) {
    return res.json({ episodes: workingMemory.messages.slice(-limit) });
  }
  
  try {
    const table = await lancedb.openTable('episodes');
    // Use toArrow() to get all data, then convert
    const arrowResult = await table.toArrow();
    const result = arrowResult ? arrowResult.toArray() : [];
    const episodes = result.slice(-limit);
    res.json({ episodes, source: 'episodic' });
  } catch (e) {
    console.error('[Memory] Episodic recent error:', e);
    res.json({ episodes: [], source: 'episodic', error: e.message });
  }
});

// ============ SEMANTIC MEMORY (Knowledge Graph) ============

app.post('/memory/semantic/entity', (req, res) => {
  const { name, type, properties } = req.body;
  
  sqlite.run(
    'INSERT INTO entities (name, type, properties) VALUES (?, ?, ?)',
    [name, type, JSON.stringify(properties || {})],
    function(err) {
      if (err) {
        return res.status(500).json({ error: err.message });
      }
      
      res.json({ id: this.lastID, name, type });
    }
  );
});

app.get('/memory/semantic/entity', (req, res) => {
  const { name } = req.query;
  
  sqlite.all(
    'SELECT * FROM entities WHERE name LIKE ?',
    [`%${name}%`],
    (err, rows) => {
      if (err) {
        return res.status(500).json({ error: err.message });
      }
      
      res.json({ entities: rows });
    }
  );
});

app.get('/memory/semantic/entity/:id', (req, res) => {
  const { id } = req.params;
  
  sqlite.get(
    'SELECT * FROM entities WHERE id = ?',
    [id],
    (err, row) => {
      if (err) {
        return res.status(500).json({ error: err.message });
      }
      
      // Get related facts
      sqlite.all(
        'SELECT * FROM facts WHERE entity_id = ?',
        [id],
        (err2, facts) => {
          res.json({ entity: row, facts });
        }
      );
    }
  );
});

app.post('/memory/semantic/relationship', (req, res) => {
  const { fromEntity, toEntity, relationType, properties } = req.body;
  
  sqlite.run(
    'INSERT INTO relationships (from_entity, to_entity, relation_type, properties) VALUES (?, ?, ?, ?)',
    [fromEntity, toEntity, relationType, JSON.stringify(properties || {})],
    function(err) {
      if (err) {
        return res.status(500).json({ error: err.message });
      }
      
      res.json({ id: this.lastID, relationType });
    }
  );
});

app.get('/memory/semantic/relationships', (req, res) => {
  const { entityId } = req.query;
  
  let query = 'SELECT * FROM relationships';
  let params = [];
  
  if (entityId) {
    query += ' WHERE from_entity = ? OR to_entity = ?';
    params = [entityId, entityId];
  }
  
  sqlite.all(query, params, (err, rows) => {
    if (err) {
      return res.status(500).json({ error: err.message });
    }
    
    res.json({ relationships: rows });
  });
});

app.post('/memory/semantic/fact', (req, res) => {
  const { entityId, fact, source, confidence = 1.0 } = req.body;
  
  sqlite.run(
    'INSERT INTO facts (entity_id, fact, source, confidence) VALUES (?, ?, ?, ?)',
    [entityId, fact, source, confidence],
    function(err) {
      if (err) {
        return res.status(500).json({ error: err.message });
      }
      
      res.json({ id: this.lastID, fact });
    }
  );
});

// ============ SYSTEM ============

app.get('/status', (req, res) => {
  res.json({
    status: 'running',
    workingMemory: {
      sessionId: workingMemory.sessionId,
      messageCount: workingMemory.messages.length
    },
    llm: {
      currentModel: modelFailover.getModel(),
      fallbackModel: config.llm.fallbackModel,
      failureCount: modelFailover.failures
    },
    config: {
      episodic: config.episodic.path,
      semantic: config.semantic.path
    }
  });
});

app.get('/health', (req, res) => {
  res.json({ 
    status: 'healthy', 
    timestamp: Date.now(),
    uptime: process.uptime()
  });
});

// Start server
const PORT = process.env.PORT || 4893;

init().then(() => {
  app.listen(PORT, () => {
    console.log(`[Memory] NexusOS Memory Server running on port ${PORT}`);
  });
}).catch(console.error);