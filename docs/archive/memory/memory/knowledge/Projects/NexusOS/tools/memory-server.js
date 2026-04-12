# feel free to ignore this comment
     1|#!/usr/bin/env node
     2|/**
     3| * NexusOS Memory Server
     4| * 
     5| * Three-tier memory management:
     6| * - Working: Current session context (RAM)
     7| * - Episodic: Vector storage (LanceDB)
     8| * - Semantic: Knowledge graph (SQLite)
     9| * 
    10| * Provides MCP-compatible interface for memory operations
    11| */
    12|
    13|import express from 'express';
    14|import bodyParser from 'body-parser';
    15|import lancedbLib from '@lancedb/lancedb';
    16|import sqlite3 from 'sqlite3';
    17|import crypto from 'crypto';
    18|
    19|const app = express();
    20|app.use(bodyParser.json());
    21|
    22|// Configuration
    23|const config = {
    24|  episodic: {
    25|    path: process.env.LANCEDB_PATH || '/nexus/memory/episodic',
    26|    embeddingModel: 'text-embedding-3-small'
    27|  },
    28|  semantic: {
    29|    path: process.env.SQLITE_PATH || '/nexus/memory/semantic/knowledge.db'
    30|  },
    31|  llm: {
    32|    provider: process.env.NEXUS_LLM_PROVIDER || 'openrouter',
    33|    primaryModel: process.env.NEXUS_LLM_MODEL || 'openrouter/minimax/minimax-m2.5',
    34|    fallbackModel: process.env.NEXUS_LLM_FALLBACK || 'openrouter/anthropic/claude-3-haiku',
    35|    maxRetries: 3,
    36|    retryDelayMs: 1000
    37|  }
    38|};
    39|
    40|// Model failover system
    41|const modelFailover = {
    42|  currentModel: config.llm.primaryModel,
    43|  failures: 0,
    44|  maxFailures: 3,
    45|  
    46|  getModel() {
    47|    return this.currentModel;
    48|  },
    49|  
    50|  async withFailover(fn) {
    51|    for (let attempt = 0; attempt < 2; attempt++) {
    52|      try {
    53|        const result = await fn(this.currentModel);
    54|        this.failures = 0; // Reset on success
    55|        return result;
    56|      } catch (error) {
    57|        console.error(`[LLM] Error with ${this.currentModel}:`, error.message);
    58|        this.failures++;
    59|        
    60|        if (attempt === 0 && this.currentModel !== config.llm.fallbackModel) {
    61|          console.log(`[LLM] Failing over to fallback model: ${config.llm.fallbackModel}`);
    62|          this.currentModel = config.llm.fallbackModel;
    63|        } else {
    64|          throw error;
    65|        }
    66|      }
    67|    }
    68|  },
    69|  
    70|  reset() {
    71|    this.currentModel = config.llm.primaryModel;
    72|    this.failures = 0;
    73|  }
    74|};
    75|
    76|// In-memory working memory
    77|let workingMemory = {
    78|  sessionId: null,
    79|  messages: [],
    80|  context: {},
    81|  entities: new Map()
    82|};
    83|
    84|// Initialize databases
    85|let lancedb;
    86|let sqlite;
    87|
    88|async function init() {
    89|  console.log('[Memory] Initializing NexusOS Memory System...');
    90|  
    91|  // Initialize LanceDB for episodic memory
    92|  try {
    93|    lancedb = await lancedbLib.connect(config.episodic.path);
    94|    console.log('[Memory] LanceDB connected');
    95|  } catch (e) {
    96|    console.warn('[Memory] LanceDB not available, using fallback:', e.message);
    97|  }
    98|  
    99|  // Initialize SQLite for semantic memory
   100|  sqlite = new sqlite3.Database(config.semantic.path);
   101|  
   102|  // Create tables if they don't exist
   103|  sqlite.serialize(() => {
   104|    sqlite.run(`
   105|      CREATE TABLE IF NOT EXISTS entities (
   106|        id INTEGER PRIMARY KEY AUTOINCREMENT,
   107|        name TEXT NOT NULL,
   108|        type TEXT NOT NULL,
   109|        properties TEXT,
   110|        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
   111|        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
   112|      )
   113|    `);
   114|    
   115|    sqlite.run(`
   116|      CREATE TABLE IF NOT EXISTS relationships (
   117|        id INTEGER PRIMARY KEY AUTOINCREMENT,
   118|        from_entity INTEGER,
   119|        to_entity INTEGER,
   120|        relation_type TEXT NOT NULL,
   121|        properties TEXT,
   122|        FOREIGN KEY (from_entity) REFERENCES entities(id),
   123|        FOREIGN KEY (to_entity) REFERENCES entities(id)
   124|      )
   125|    `);
   126|    
   127|    sqlite.run(`
   128|      CREATE TABLE IF NOT EXISTS facts (
   129|        id INTEGER PRIMARY KEY AUTOINCREMENT,
   130|        entity_id INTEGER,
   131|        fact TEXT NOT NULL,
   132|        source TEXT,
   133|        confidence REAL DEFAULT 1.0,
   134|        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
   135|      )
   136|    `);
   137|  });
   138|  
   139|  console.log('[Memory] Initialization complete');
   140|}
   141|
   142|// ============ WORKING MEMORY (RAM) ============
   143|
   144|app.post('/memory/working/start', (req, res) => {
   145|  const { sessionId, systemPrompt } = req.body;
   146|  
   147|  workingMemory = {
   148|    sessionId: sessionId || crypto.randomUUID(),
   149|    messages: [],
   150|    context: { systemPrompt },
   151|    entities: new Map()
   152|  };
   153|  
   154|  console.log(`[Memory] Started working memory session: ${workingMemory.sessionId}`);
   155|  
   156|  res.json({ sessionId: workingMemory.sessionId });
   157|});
   158|
   159|app.post('/memory/working/message', (req, res) => {
   160|  const { role, content, name } = req.body;
   161|  
   162|  if (!workingMemory.sessionId) {
   163|    return res.status(400).json({ error: 'No active session' });
   164|  }
   165|  
   166|  workingMemory.messages.push({ role, content, name, timestamp: Date.now() });
   167|  
   168|  res.json({ success: true, messageCount: workingMemory.messages.length });
   169|});
   170|
   171|app.get('/memory/working/context', (req, res) => {
   172|  const limit = parseInt(req.query.limit) || 10;
   173|  
   174|  const recent = workingMemory.messages.slice(-limit);
   175|  const context = workingMemory.context;
   176|  
   177|  res.json({ 
   178|    sessionId: workingMemory.sessionId,
   179|    messages: recent,
   180|    context,
   181|    messageCount: workingMemory.messages.length
   182|  });
   183|});
   184|
   185|app.post('/memory/working/context', (req, res) => {
   186|  const { key, value } = req.body;
   187|  
   188|  workingMemory.context[key] = value;
   189|  
   190|  res.json({ success: true });
   191|});
   192|
   193|app.post('/memory/working/summarize', async (req, res) => {
   194|  // Extract key information from working memory for persistence
   195|  const summary = {
   196|    sessionId: workingMemory.sessionId,
   197|    messageCount: workingMemory.messages.length,
   198|    keyEntities: Array.from(workingMemory.entities.entries()),
   199|    timestamp: Date.now()
   200|  };
   201|  
   202|  res.json({ summary });
   203|});
   204|
   205|app.post('/memory/working/end', async (req, res) => {
   206|  if (!workingMemory.sessionId) {
   207|    return res.status(400).json({ error: 'No active session' });
   208|  }
   209|  
   210|  const sessionId = workingMemory.sessionId;
   211|  
   212|  // Auto-persist to episodic memory
   213|  if (lancedb && workingMemory.messages.length > 0) {
   214|    await persistToEpisodic(workingMemory.messages, sessionId);
   215|  }
   216|  
   217|  workingMemory = {
   218|    sessionId: null,
   219|    messages: [],
   220|    context: {},
   221|    entities: new Map()
   222|  };
   223|  
   224|  console.log(`[Memory] Ended session: ${sessionId}`);
   225|  
   226|  res.json({ success: true, sessionId });
   227|});
   228|
   229|// ============ EPISODIC MEMORY (Vector) ============
   230|
   231|async function persistToEpisodic(messages, sessionId) {
   232|  if (!lancedb) return;
   233|  
   234|  try {
   235|    // Remove old table and recreate fresh
   236|    try {
   237|      await lancedb.dropTable('episodes');
   238|    } catch (e) {
   239|      // Table doesn't exist, ignore
   240|    }
   241|    
   242|    // Create table with initial data to establish schema
   243|    // Schema is inferred from first batch of data
   244|    const initialData = messages.map((m) => ({
   245|      session_id: String(sessionId),
   246|      content: String(m.content),
   247|      role: String(m.role),
   248|      timestamp: Number(m.timestamp || Date.now())
   249|    }));
   250|    
   251|    const table = await lancedb.createTable('episodes', initialData);
   252|    console.log(`[Memory] Persisted ${initialData.length} messages to episodic`);
   253|  } catch (e) {
   254|    console.error('[Memory] Episodic persist error:', e);
   255|  }
   256|}
   257|
   258|app.post('/memory/episodic/search', async (req, res) => {
   259|  const { query, topK = 5 } = req.body;
   260|  
   261|  if (!lancedb) {
   262|    // Fallback: search in working memory
   263|    const results = workingMemory.messages
   264|      .filter(m => m.content.toLowerCase().includes(query.toLowerCase()))
   265|      .slice(-topK);
   266|    
   267|    return res.json({ results, source: 'working' });
   268|  }
   269|  
   270|  try {
   271|    // Query LanceDB for episodic memory
   272|    // Note: Full vector search requires embeddings - this is a text filter for now
   273|    const table = await lancedb.openTable('episodes');
   274|    const arrowResult = await table.toArrow();
   275|    const allData = arrowResult ? arrowResult.toArray() : [];
   276|    
   277|    // Simple text search (not vector search)
   278|    const results = allData
   279|      .filter(m => m.content && m.content.toLowerCase().includes(query.toLowerCase()))
   280|      .slice(-topK);
   281|    
   282|    res.json({ results, source: 'episodic' });
   283|  } catch (e) {
   284|    res.status(500).json({ error: e.message });
   285|  }
   286|});
   287|
   288|app.get('/memory/episodic/recent', async (req, res) => {
   289|  const limit = parseInt(req.query.limit) || 10;
   290|  
   291|  if (!lancedb) {
   292|    return res.json({ episodes: workingMemory.messages.slice(-limit) });
   293|  }
   294|  
   295|  try {
   296|    const table = await lancedb.openTable('episodes');
   297|    // Use toArrow() to get all data, then convert
   298|    const arrowResult = await table.toArrow();
   299|    const result = arrowResult ? arrowResult.toArray() : [];
   300|    const episodes = result.slice(-limit);
   301|    res.json({ episodes, source: 'episodic' });
   302|  } catch (e) {
   303|    console.error('[Memory] Episodic recent error:', e);
   304|    res.json({ episodes: [], source: 'episodic', error: e.message });
   305|  }
   306|});
   307|
   308|// ============ SEMANTIC MEMORY (Knowledge Graph) ============
   309|
   310|app.post('/memory/semantic/entity', (req, res) => {
   311|  const { name, type, properties } = req.body;
   312|  
   313|  sqlite.run(
   314|    'INSERT INTO entities (name, type, properties) VALUES (?, ?, ?)',
   315|    [name, type, JSON.stringify(properties || {})],
   316|    function(err) {
   317|      if (err) {
   318|        return res.status(500).json({ error: err.message });
   319|      }
   320|      
   321|      res.json({ id: this.lastID, name, type });
   322|    }
   323|  );
   324|});
   325|
   326|app.get('/memory/semantic/entity', (req, res) => {
   327|  const { name } = req.query;
   328|  
   329|  sqlite.all(
   330|    'SELECT * FROM entities WHERE name LIKE ?',
   331|    [`%${name}%`],
   332|    (err, rows) => {
   333|      if (err) {
   334|        return res.status(500).json({ error: err.message });
   335|      }
   336|      
   337|      res.json({ entities: rows });
   338|    }
   339|  );
   340|});
   341|
   342|app.get('/memory/semantic/entity/:id', (req, res) => {
   343|  const { id } = req.params;
   344|  
   345|  sqlite.get(
   346|    'SELECT * FROM entities WHERE id = ?',
   347|    [id],
   348|    (err, row) => {
   349|      if (err) {
   350|        return res.status(500).json({ error: err.message });
   351|      }
   352|      
   353|      // Get related facts
   354|      sqlite.all(
   355|        'SELECT * FROM facts WHERE entity_id = ?',
   356|        [id],
   357|        (err2, facts) => {
   358|          res.json({ entity: row, facts });
   359|        }
   360|      );
   361|    }
   362|  );
   363|});
   364|
   365|app.post('/memory/semantic/relationship', (req, res) => {
   366|  const { fromEntity, toEntity, relationType, properties } = req.body;
   367|  
   368|  sqlite.run(
   369|    'INSERT INTO relationships (from_entity, to_entity, relation_type, properties) VALUES (?, ?, ?, ?)',
   370|    [fromEntity, toEntity, relationType, JSON.stringify(properties || {})],
   371|    function(err) {
   372|      if (err) {
   373|        return res.status(500).json({ error: err.message });
   374|      }
   375|      
   376|      res.json({ id: this.lastID, relationType });
   377|    }
   378|  );
   379|});
   380|
   381|app.get('/memory/semantic/relationships', (req, res) => {
   382|  const { entityId } = req.query;
   383|  
   384|  let query = 'SELECT * FROM relationships';
   385|  let params = [];
   386|  
   387|  if (entityId) {
   388|    query += ' WHERE from_entity = ? OR to_entity = ?';
   389|    params = [entityId, entityId];
   390|  }
   391|  
   392|  sqlite.all(query, params, (err, rows) => {
   393|    if (err) {
   394|      return res.status(500).json({ error: err.message });
   395|    }
   396|    
   397|    res.json({ relationships: rows });
   398|  });
   399|});
   400|
   401|app.post('/memory/semantic/fact', (req, res) => {
   402|  const { entityId, fact, source, confidence = 1.0 } = req.body;
   403|  
   404|  sqlite.run(
   405|    'INSERT INTO facts (entity_id, fact, source, confidence) VALUES (?, ?, ?, ?)',
   406|    [entityId, fact, source, confidence],
   407|    function(err) {
   408|      if (err) {
   409|        return res.status(500).json({ error: err.message });
   410|      }
   411|      
   412|      res.json({ id: this.lastID, fact });
   413|    }
   414|  );
   415|});
   416|
   417|// ============ SYSTEM ============
   418|
   419|app.get('/status', (req, res) => {
   420|  res.json({
   421|    status: 'running',
   422|    workingMemory: {
   423|      sessionId: workingMemory.sessionId,
   424|      messageCount: workingMemory.messages.length
   425|    },
   426|    llm: {
   427|      currentModel: modelFailover.getModel(),
   428|      fallbackModel: config.llm.fallbackModel,
   429|      failureCount: modelFailover.failures
   430|    },
   431|    config: {
   432|      episodic: config.episodic.path,
   433|      semantic: config.semantic.path
   434|    }
   435|  });
   436|});
   437|
   438|app.get('/health', (req, res) => {
   439|  res.json({ 
   440|    status: 'healthy', 
   441|    timestamp: Date.now(),
   442|    uptime: process.uptime()
   443|  });
   444|});
   445|
   446|// Start server
   447|const PORT = process.env.PORT || 4893;
   448|
   449|init().then(() => {
   450|  app.listen(PORT, () => {
   451|    console.log(`[Memory] NexusOS Memory Server running on port ${PORT}`);
   452|  });
   453|}).catch(console.error);