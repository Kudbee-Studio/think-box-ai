/**
 * KUDBEE Dashboard Server
 * Serves the dashboard and provides API endpoints
 */

import express from 'express';
import { spawn } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();
const PORT = 3000;

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

function runCli(args) {
    return new Promise((resolve) => {
        const proc = spawn('python3', ['-m', 'think_box_ai.cli', ...args], {
            cwd: path.join(__dirname, '..', '..'),
            env: { ...process.env, THINKBOX_DB_PATH: process.env.THINKBOX_DB_PATH || path.join(process.env.HOME || '/root', '.local/share/thinkbox/thinkbox.db') },
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

// API Routes
app.get('/api/health', async (req, res) => {
    res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

app.get('/api/boxes', async (req, res) => {
    const result = await runCli(['list']);
    res.json({ boxes: result.stdout.split('\n').filter(Boolean) });
});

app.post('/api/boxes', async (req, res) => {
    const { goal } = req.body;
    const result = await runCli(['create', '--goal', goal || '']);
    res.json({ id: result.stdout, status: result.code === 0 ? 'created' : 'error' });
});

app.get('/api/boxes/:id', async (req, res) => {
    const result = await runCli(['status', req.params.id]);
    res.json({ id: req.params.id, status: result.stdout });
});

app.post('/api/boxes/:id/exec', async (req, res) => {
    const { command } = req.body;
    const result = await runCli(['exec', req.params.id, '--', ...command.split(' ')]);
    res.json({ output: result.stdout, code: result.code });
});

app.get('/api/boxes/:id/tokens', async (req, res) => {
    const result = await runCli(['tokens', req.params.id]);
    res.json({ tokens: result.stdout.split('\n').filter(Boolean) });
});

app.get('/api/upcloud', async (req, res) => {
    const result = await runCli(['upcloud']);
    res.json({ raw: result.stdout });
});

app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'dashboard.html'));
});

app.listen(PORT, () => {
    console.log(`KUDBEE Dashboard running at http://localhost:${PORT}`);
});
