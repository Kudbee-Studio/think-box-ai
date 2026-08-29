/**
 * KUDBEE Dashboard Server (zero dependencies)
 */

import http from 'http';
import { spawn } from 'child_process';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = 3001;

function runCli(args) {
    return new Promise((resolve) => {
        const proc = spawn('python3', ['-m', 'think_box_ai.cli', ...args], {
            cwd: path.join(__dirname, '..', '..'),
            env: { ...process.env },
        });
        let stdout = '';
        let stderr = '';
        proc.stdout.on('data', (d) => { stdout += d; });
        proc.stderr.on('data', (d) => { stderr += d; });
        proc.on('close', (code) => {
            resolve({ code, stdout: stdout.trim(), stderr: stderr.trim() });
        });
    });
}

const server = http.createServer(async (req, res) => {
    res.setHeader('Content-Type', 'application/json');
    res.setHeader('Access-Control-Allow-Origin', '*');

    if (req.url === '/api/health') {
        res.end(JSON.stringify({ status: 'ok', timestamp: new Date().toISOString() }));
        return;
    }

    if (req.url === '/api/boxes' && req.method === 'GET') {
        const result = await runCli(['list']);
        res.end(JSON.stringify({ boxes: result.stdout.split('\n').filter(Boolean) }));
        return;
    }

    if (req.url === '/api/boxes' && req.method === 'POST') {
        let body = '';
        req.on('data', (d) => { body += d; });
        req.on('end', async () => {
            const { goal } = JSON.parse(body || '{}');
            const result = await runCli(['create', '--goal', goal || '']);
            res.end(JSON.stringify({ id: result.stdout, status: result.code === 0 ? 'created' : 'error' }));
        });
        return;
    }

    if (req.url === '/api/upcloud') {
        const result = await runCli(['upcloud']);
        res.end(JSON.stringify({ raw: result.stdout }));
        return;
    }

    if (req.url?.startsWith('/api/boxes/') && req.url.endsWith('/tokens')) {
        const boxId = req.url.split('/')[3];
        const result = await runCli(['tokens', boxId]);
        res.end(JSON.stringify({ tokens: result.stdout.split('\n').filter(Boolean) }));
        return;
    }

    if (req.url?.startsWith('/api/boxes/') && req.url.endsWith('/exec')) {
        const boxId = req.url.split('/')[3];
        let body = '';
        req.on('data', (d) => { body += d; });
        req.on('end', async () => {
            const { command } = JSON.parse(body || '{}');
            const result = await runCli(['exec', boxId, '--', ...command.split(' ')]);
            res.end(JSON.stringify({ output: result.stdout, code: result.code }));
        });
        return;
    }

    // Serve dashboard
    if (req.url === '/' || req.url === '/dashboard') {
        const html = fs.readFileSync(path.join(__dirname, 'public', 'dashboard.html'), 'utf-8');
        res.setHeader('Content-Type', 'text/html');
        res.end(html);
        return;
    }

    res.statusCode = 404;
    res.end(JSON.stringify({ error: 'not found' }));
});

server.listen(PORT, () => {
    console.log(`KUDBEE Dashboard running at http://localhost:${PORT}`);
});
