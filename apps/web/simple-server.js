/**
 * KUDBEE Dashboard Server — Real-time WebSocket + REST API
 *
 * Features:
 * - REST API for box CRUD
 * - Server-Sent Events for live execution streaming
 * - API key authentication
 */

import http from 'http';
import { spawn } from 'child_process';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import crypto from 'crypto';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = 3001;

// ─── Auth ───────────────────────────────────────────────────────
const API_KEYS = new Map<string, { name: string; created: string }>();

function generateApiKey(name: string): string {
    const key = `kb_${crypto.randomBytes(24).toString('hex')}`;
    API_KEYS.set(key, { name, created: new Date().toISOString() });
    return key;
}

function authenticate(req: http.IncomingMessage): boolean {
    const key = req.headers['x-api-key'] as string | undefined;
    return key ? API_KEYS.has(key) : false;
}

// ─── CLI Runner ─────────────────────────────────────────────────
function runCli(args: string[], onOutput?: (data: string) => void): Promise<{ code: number; stdout: string; stderr: string }> {
    return new Promise((resolve) => {
        const proc = spawn('python3', ['-m', 'think_box_ai.cli', ...args], {
            cwd: path.join(__dirname, '..', '..'),
            env: { ...process.env, PYTHONUNBUFFERED: '1' },
        });
        let stdout = '';
        let stderr = '';
        proc.stdout.on('data', (d) => {
            const s = d.toString();
            stdout += s;
            onOutput?.(s);
        });
        proc.stderr.on('data', (d) => {
            const s = d.toString();
            stderr += s;
            onOutput?.(s);
        });
        proc.on('close', (code) => {
            resolve({ code: code ?? 0, stdout: stdout.trim(), stderr: stderr.trim() });
        });
    });
}

// ─── SSE Streaming ──────────────────────────────────────────────
const sseClients = new Set<http.ServerResponse>();

function broadcastSSE(event: string, data: unknown) {
    const payload = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
    for (const client of sseClients) {
        client.write(payload);
    }
}

// ─── HTTP Server ────────────────────────────────────────────────
const server = http.createServer(async (req, res) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, X-API-Key');
    if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }

    // Health check (public)
    if (req.url === '/api/health') {
        res.setHeader('Content-Type', 'application/json');
        res.end(JSON.stringify({ status: 'ok', timestamp: new Date().toISOString(), uptime: process.uptime() }));
        return;
    }

    // SSE stream (public for demo)
    if (req.url === '/api/stream') {
        res.writeHead(200, {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
        });
        res.write(`event: connected\ndata: {"ok": true}\n\n`);
        sseClients.add(res);
        req.on('close', () => sseClients.delete(res));
        return;
    }

    // API key generation (one-time setup)
    if (req.url === '/api/keys' && req.method === 'POST') {
        const key = generateApiKey('dashboard');
        res.setHeader('Content-Type', 'application/json');
        res.end(JSON.stringify({ api_key: key, note: 'Save this key - it will not be shown again' }));
        return;
    }

    // Protected endpoints require auth
    if (!authenticate(req)) {
        res.setHeader('Content-Type', 'application/json');
        res.writeHead(401);
        res.end(JSON.stringify({ error: 'Unauthorized - provide X-API-Key header' }));
        return;
    }

    // List boxes
    if (req.url === '/api/boxes' && req.method === 'GET') {
        const result = await runCli(['list']);
        res.setHeader('Content-Type', 'application/json');
        res.end(JSON.stringify({ boxes: result.stdout.split('\n').filter(Boolean) }));
        return;
    }

    // Create box
    if (req.url === '/api/boxes' && req.method === 'POST') {
        let body = '';
        req.on('data', (d) => { body += d; });
        req.on('end', async () => {
            const { goal } = JSON.parse(body || '{}');
            const result = await runCli(['create', '--goal', goal || '']);
            res.setHeader('Content-Type', 'application/json');
            res.end(JSON.stringify({ id: result.stdout, status: result.code === 0 ? 'created' : 'error' }));
            broadcastSSE('box_created', { id: result.stdout });
        });
        return;
    }

    // Delete box
    if (req.url?.startsWith('/api/boxes/') && req.method === 'DELETE') {
        const boxId = req.url.split('/')[3];
        await runCli(['delete', boxId]);
        res.setHeader('Content-Type', 'application/json');
        res.end(JSON.stringify({ deleted: boxId }));
        return;
    }

    // Execute command with streaming
    if (req.url?.startsWith('/api/boxes/') && req.url.endsWith('/exec')) {
        const boxId = req.url.split('/')[3];
        let body = '';
        req.on('data', (d) => { body += d; });
        req.on('end', async () => {
            const { command } = JSON.parse(body || '{}');
            const result = await runCli(
                ['exec', boxId, '--', ...command.split(' ')],
                (chunk) => broadcastSSE('exec_output', { box_id: boxId, chunk })
            );
            res.setHeader('Content-Type', 'application/json');
            res.end(JSON.stringify({ output: result.stdout, code: result.code }));
            broadcastSSE('exec_complete', { box_id: boxId, code: result.code });
        });
        return;
    }

    // List tokens
    if (req.url?.startsWith('/api/boxes/') && req.url.endsWith('/tokens')) {
        const boxId = req.url.split('/')[3];
        const result = await runCli(['tokens', boxId]);
        res.setHeader('Content-Type', 'application/json');
        res.end(JSON.stringify({ tokens: result.stdout.split('\n').filter(Boolean) }));
        return;
    }

    // UpCloud
    if (req.url === '/api/upcloud') {
        const result = await runCli(['upcloud']);
        res.setHeader('Content-Type', 'application/json');
        res.end(JSON.stringify({ raw: result.stdout }));
        return;
    }

    // Serve dashboard
    if (req.url === '/' || req.url === '/dashboard') {
        const html = fs.readFileSync(path.join(__dirname, 'public', 'dashboard.html'), 'utf-8');
        res.setHeader('Content-Type', 'text/html');
        res.end(html);
        return;
    }

    res.setHeader('Content-Type', 'application/json');
    res.writeHead(404);
    res.end(JSON.stringify({ error: 'not found' }));
});

server.listen(PORT, () => {
    console.log(`KUDBEE Dashboard running at http://localhost:${PORT}`);
    console.log(`SSE stream: http://localhost:${PORT}/api/stream`);
});
