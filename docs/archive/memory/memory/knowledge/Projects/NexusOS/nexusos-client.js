# feel free to ignore this comment
     1|# feel free to ignore this comment
     2|     1|/**
     3|     2| * NexusOS JavaScript Client
     4|     3| * Simple wrapper for NexusOS memory server
     5|     4| */
     6|     5|
     7|     6|class NexusOS {
     8|     7|    constructor(baseUrl = 'http://localhost:4893') {
     9|     8|        this.baseUrl = baseUrl;
    10|     9|    }
    11|    10|
    12|    11|    async health() {
    13|    12|        const res = await fetch(`${this.baseUrl}/health`);
    14|    13|        return res.json();
    15|    14|    }
    16|    15|
    17|    16|    async startSession(sessionId) {
    18|    17|        const res = await fetch(`${this.baseUrl}/memory/working/start`, {
    19|    18|            method: 'POST',
    20|    19|            headers: { 'Content-Type': 'application/json' },
    21|    20|            body: JSON.stringify({ sessionId })
    22|    21|        });
    23|    22|        return res.json();
    24|    23|    }
    25|    24|
    26|    25|    async addMessage(content, role = 'user') {
    27|    26|        const res = await fetch(`${this.baseUrl}/memory/working/message`, {
    28|    27|            method: 'POST',
    29|    28|            headers: { 'Content-Type': 'application/json' },
    30|    29|            body: JSON.stringify({ content, role })
    31|    30|        });
    32|    31|        return res.json();
    33|    32|    }
    34|    33|
    35|    34|    async endSession() {
    36|    35|        const res = await fetch(`${this.baseUrl}/memory/working/end`, {
    37|    36|            method: 'POST',
    38|    37|            headers: { 'Content-Type': 'application/json' },
    39|    38|            body: JSON.stringify({})
    40|    39|        });
    41|    40|        return res.json();
    42|    41|    }
    43|    42|
    44|    43|    async search(query, limit = 5) {
    45|    44|        const res = await fetch(`${this.baseUrl}/memory/episodic/search`, {
    46|    45|            method: 'POST',
    47|    46|            headers: { 'Content-Type': 'application/json' },
    48|    47|            body: JSON.stringify({ query, limit })
    49|    48|        });
    50|    49|        return res.json();
    51|    50|    }
    52|    51|
    53|    52|    async recent(limit = 10) {
    54|    53|        const res = await fetch(`${this.baseUrl}/memory/episodic/recent?limit=${limit}`);
    55|    54|        return res.json();
    56|    55|    }
    57|    56|
    58|    57|    // Convenience method: full session in one call
    59|    58|    async remember(sessionId, messages) {
    60|    59|        await this.startSession(sessionId);
    61|    60|        for (const msg of messages) {
    62|    61|            await this.addMessage(msg.content, msg.role);
    63|    62|        }
    64|    63|        await this.endSession();
    65|    64|    }
    66|    65|
    67|    66|    // Convenience method: full workflow
    68|    67|    async recall(query) {
    69|    68|        const results = await this.search(query);
    70|    69|        return results.results;
    71|    70|    }
    72|    71|}
    73|    72|
    74|    73|// Export for use
    75|    74|if (typeof module !== 'undefined' && module.exports) {
    76|    75|    module.exports = NexusOS;
    77|    76|}
    78|    77|