/** Simple in-memory rate limiter for Node.js server */

export class RateLimiter {
    constructor(rate = 10, burst = 20) {
        this._rate = rate;
        this._burst = burst;
        this._clients = new Map();
    }

    allow(clientId) {
        const now = Date.now() / 1000;
        
        if (!this._clients.has(clientId)) {
            this._clients.set(clientId, { time: now, tokens: this._burst - 1 });
            return true;
        }
        
        const client = this._clients.get(clientId);
        const elapsed = now - client.time;
        client.tokens = Math.min(this._burst, client.tokens + elapsed * this._rate);
        client.time = now;
        
        if (client.tokens >= 1) {
            client.tokens -= 1;
            return true;
        }
        
        return false;
    }
}
