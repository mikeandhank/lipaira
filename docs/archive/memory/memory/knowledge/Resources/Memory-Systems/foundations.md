# Foundations: How AI Memory Systems Work

## Three-Tier Operatorure

AI memory systems borrow from human memory hierarchy but map to hardware tiers:

### Tier 1: Working Memory (GPU HBM)
- **What it is**: Ultra-fast memory on GPU (High Bandwidth Memory)
- **Latency**: ~75ns random access
- **Capacity**: Limited (~1MB random access efficiently)
- **Use case**: KV cache during inference, immediate context window
- **Token throughput**: 500-800 tokens/second

### Tier 2: Short-Term Memory (DRAM)
- **What it is**: Fast system memory for caching frequent data
- **Latency**: ~75ns (similar to HBM but higher capacity)
- **Use case**: Session summaries, entity caches, frequently accessed embeddings
- **Key insight**: Stores structured extractions (summaries, entities, patterns)

### Tier 3: Long-Term Memory (NVMe SSDs)
- **What it is**: Persistent storage for raw data and large sequential accesses
- **Latency**: ~60,000ns (800x slower than DRAM for random access)
- **Use case**: Archival storage, full conversation history, large knowledge bases
- **Warning**: Using SSD for random access kills performance (drops to 16 tokens/sec)

## Data Processing Framework (L0-L2)

- **L0 (Raw Data Layer)**: Ingests conversations, documents, events → stored on SSD
- **L1 (Structured Memory Layer)**: Processes into summaries, entities, patterns → DRAM/SSD
- **L2 (AI-Native Memory Layer)**: Integrates into model weights/behaviors → GPU/SSD

## RAG + Vector Databases

### How RAG Works
1. **Embed**: Convert text into vector embeddings using models like text-embedding-ada-002
2. **Store**: Save vectors in a database (vector DB or SQL with embeddings)
3. **Retrieve**: Query returns top-K most similar results (e.g., K=20)
4. **Generate**: Feed retrieved context to LLM for generation

### Vector Database Role
- Stores embeddings (numerical representations of text)
- Enables semantic similarity search (not just keyword matching)
- Powers retrieval-augmented generation (RAG)

### Recency Weighting
- Exponential decay (α=0.02) prioritizes recent information
- Resolves contradictions between old and new memories
- Enables long-term personalization within token limits

### Hybrid Approaches (2024-2025)
Modern systems combine:
- **Vector stores**: Semantic similarity
- **Knowledge graphs**: Relationships and structure
- **Temporal indexing**: Time-based retrieval

This outperforms unweighted systems in coherence and efficiency.

## Key Technologies

| Technology | Purpose |
|------------|---------|
| Pinecone | Managed vector database (SaaS) |
| Weaviate | Open-source vector DB (self-hosted option) |
| Chroma | Lightweight vector DB for embeddings |
| Mem0 | Multi-level memory for AI agents |
| LangChain | Memory components (ConversationBuffer, etc.) |
| GraphRAG | Knowledge graphs + RAG integration |

## The Memory Problem

LLMs are stateless by default—each request is a fresh start. Memory systems solve this by:
1. Capturing interactions
2. Extracting structured knowledge
3. Retrieving relevant context
4. Injecting into prompts

This enables persistent AI assistants that "remember" across sessions.

---

*Last updated: 2026-03-13*
