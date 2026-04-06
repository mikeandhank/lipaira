# Open Questions: Known Unknowns

These are questions I cannot answer confidently. They're the edges of what I understand about memory systems—where conventional answers don't exist.

---

## 1. How Do You Weight Contradictory Memories?

**The problem**: A user's preferences change over time. Last year they said they liked X, this year they prefer Y. Both are stored in memory. How does an AI resolve which to use?

**Why I can't answer**:
- No consensus exists on contradiction resolution
- Possible approaches: recency only (throw out old), confidence weighting (how sure are we?), explicit user confirmation
- Each has trade-offs: recency loses long-term patterns; explicit confirmation breaks flow
- The "right" answer depends on use case, user tolerance, domain

**What would help**: Empirical studies on user behavior with contradictory memory systems. Currently, this is a design choice, not a solved problem.

---

## 2. What's the Optimal Memory Compression Ratio?

**The problem**: Raw conversation data doesn't fit in context. We compress to summaries, entities, key facts. How much compression is too much? What's lost?

**Why I can't answer**:
- No established formula for "summarize to N tokens while preserving X utility"
- Compression is lossy by definition—but which details matter?
- Depends entirely on: domain, retrieval method, user expectations
- A 10K token conversation → 500 token summary might lose crucial nuance

**What would help**: Benchmarks measuring downstream task performance vs. compression ratio. We don't have standard datasets for this.

---

## 3. When Should Memory Be Forgotten?

**The problem**: Memory systems store everything. But at scale, old, irrelevant data degrades retrieval quality and increases cost. When should we delete?

**Why I can't answer**:
- No standard for "memory half-life"
- Approaches exist (recency decay, utility-based deletion) but no consensus on parameters
- GDPR says you must delete user data on request—but what about the extracted model of the user?
- Some domains require memory (legal, medical); others actively want forgetting

**What would help**: Industry standards or best practice guides. Right now, each product invents its own decay functions.

---

## Bonus: The Alignment Question

**The problem nobody's talking about**: Memory systems learn models of users. These models can be used to manipulate, persuade, or exploit. Who controls the memory? Who decides what's stored, retrieved, and how?

This isn't a technical question—it's a governance question. And there's no answer yet.

---

*Last updated: 2026-03-13*
