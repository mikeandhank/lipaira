/**
 * NexusOS JavaScript Client
 * Simple wrapper for NexusOS memory server
 */

class NexusOS {
    constructor(baseUrl = 'http://localhost:4893') {
        this.baseUrl = baseUrl;
    }

    async health() {
        const res = await fetch(`${this.baseUrl}/health`);
        return res.json();
    }

    async startSession(sessionId) {
        const res = await fetch(`${this.baseUrl}/memory/working/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sessionId })
        });
        return res.json();
    }

    async addMessage(content, role = 'user') {
        const res = await fetch(`${this.baseUrl}/memory/working/message`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content, role })
        });
        return res.json();
    }

    async endSession() {
        const res = await fetch(`${this.baseUrl}/memory/working/end`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });
        return res.json();
    }

    async search(query, limit = 5) {
        const res = await fetch(`${this.baseUrl}/memory/episodic/search`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, limit })
        });
        return res.json();
    }

    async recent(limit = 10) {
        const res = await fetch(`${this.baseUrl}/memory/episodic/recent?limit=${limit}`);
        return res.json();
    }

    // Convenience method: full session in one call
    async remember(sessionId, messages) {
        await this.startSession(sessionId);
        for (const msg of messages) {
            await this.addMessage(msg.content, msg.role);
        }
        await this.endSession();
    }

    // Convenience method: full workflow
    async recall(query) {
        const results = await this.search(query);
        return results.results;
    }
}

// Export for use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = NexusOS;
}
