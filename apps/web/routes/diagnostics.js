// Health, monitoring and dashboard stats routes. Moved out of server.ts unchanged; the live objects they read come in as `deps`.
import os from 'node:os';
                                                 
import { inceptionConfigured } from '../agent.js';
import { SDK_VERSION, loadConfigFromEnv } from '../sdk/index.js';
import { errorMessage } from '../types.js';
                                                
                                           
                                          

                                     
                 
                   
                                     
                                         
                                                                                  
 

                                  
                                            
                            
                          
                                                              
                        
                        
                       
                              
                     
                           
                         
 

export function registerDiagnosticsRoutes(app         , deps                 )       {
  const { sessions, plugins, serverStartedAt, monitorAgent, port: PORT, ollamaBaseUrl, janusBaseUrl, janusEnabled, runStore, memoryStore, dailyBudgetUsd } = deps;
  async function monitorEndpoint(name        , url        , headers                         = {})                                   {
    const startedAt = Date.now();
    try {
      const response = await fetch(url, { headers, signal: AbortSignal.timeout(5000) });
      const body = await response.text();
      let details          = body.slice(0, 500);
      try {
        details = JSON.parse(body);
      } catch {
        // Keep non-JSON API responses as bounded text.
      }
      return {
        name,
        url,
        status: response.ok ? 'ok' : 'error',
        http_status: response.status,
        latency_ms: Date.now() - startedAt,
        details,
      };
    } catch (err) {
      return {
        name,
        url,
        status: 'offline',
        latency_ms: Date.now() - startedAt,
        error: errorMessage(err),
      };
    }
  }

  app.get('/api/health', (_req         , res          ) => {
    const sdkConfig = loadConfigFromEnv();
    const memory = process.memoryUsage();
    res.json({
      status: 'ok',
      ready: true,
      sessions: sessions.size,
      plugins: plugins.size,
      inception_configured: inceptionConfigured(),
      sdk_version: SDK_VERSION,
      dry_run: sdkConfig.dryRun,
      uptime_seconds: Math.floor((Date.now() - serverStartedAt) / 1000),
      memory_mb: Math.round(memory.rss / 1024 / 1024),
      node_version: process.version,
    });
  });

  app.get('/api/monitor', async (_req         , res          ) => {
    const baseUrl = `http://127.0.0.1:${PORT}`;
    const checks = await Promise.all([
      monitorEndpoint('Agent OS API', `${baseUrl}/api/health`),
      monitorEndpoint('SDK capabilities', `${baseUrl}/api/sdk/capabilities`),
      monitorEndpoint('Ollama models', `${ollamaBaseUrl}/api/tags`),
      ...(janusEnabled() ? [monitorEndpoint('Janus image service', `${janusBaseUrl}/health`)] : []),
      ...(process.env.KUDBEE_MEMORY_BACKEND === 'upstash' && process.env.UPSTASH_VECTOR_REST_URL && process.env.UPSTASH_VECTOR_REST_TOKEN
        ? [monitorEndpoint('Upstash Vector (memory)', `${process.env.UPSTASH_VECTOR_REST_URL.replace(/\/+$/, '')}/info`, { Authorization: `Bearer ${process.env.UPSTASH_VECTOR_REST_TOKEN}` })]
        : []),
      ...(inceptionConfigured()
        ? [monitorEndpoint('Inception Mercury 2', 'https://api.inceptionlabs.ai/v1/models', { Authorization: `Bearer ${process.env.INCEPTION_API_KEY}` })]
        : []),
    ]);
    monitorAgent.checks += 1;
    monitorAgent.last_check = new Date().toISOString();
    res.json({
      checked_at: new Date().toISOString(),
      agent: monitorAgent,
      websocket_sessions: sessions.size,
      checks,
    });
  });

  app.get('/api/middleware/test', async (_req         , res          ) => {
    const baseUrl = `http://127.0.0.1:${PORT}`;
    const checks = await Promise.all([
      monitorEndpoint('API middleware', `${baseUrl}/api/health`),
      monitorEndpoint('SDK middleware', `${baseUrl}/api/sdk/capabilities`),
      monitorEndpoint('Ollama middleware', `${ollamaBaseUrl}/api/tags`),
    ]);
    const passed = checks.every((check) => check.status === 'ok');
    const sessionId = typeof _req.query.session_id === 'string' ? _req.query.session_id : '';
    const session = sessions.get(sessionId);
    if (session) {
      const timestamp = Date.now();
      session.memory.push({ timestamp, type: 'middleware_test', passed, checks });
      session.addThought({
        type: 'middleware_test',
        content: `Middleware test ${passed ? 'passed' : 'failed'} (${checks.length} checks)`,
        status: passed ? 'success' : 'error',
      });
    }
    res.status(passed ? 200 : 503).json({
      passed,
      checked_at: new Date().toISOString(),
      websocket_sessions: sessions.size,
      checks,
    });
  });

  let lastCpu = { usage: process.cpuUsage(), at: Date.now() };
  let statsCache                                                       = { data: null, at: 0 };

  app.get('/api/stats', (_req         , res          ) => {
    // Cache stats for 500ms to reduce computation on rapid dashboard polls
    const now = Date.now();
    if (statsCache.data && now - statsCache.at < 500) {
      return res.json(statsCache.data);
    }

    const usage = process.cpuUsage(lastCpu.usage);
    const elapsedMs = Math.max(1, now - lastCpu.at);
    lastCpu = { usage: process.cpuUsage(), at: now };
    const memory = process.memoryUsage();
    const running = [...sessions.values()].filter((session) => session.status === 'running').length;
    const stats = {
      ...runStore.stats(),
      budget_usd: dailyBudgetUsd || null,
      memory: { counts: memoryStore.counts(), vector: memoryStore.vectorStatus },
      capacity: {
        running_agents: running,
        queued_goals: [...sessions.values()].reduce((sum, session) => sum + session.queue.length, 0),
        connected_sessions: sessions.size,
        pending_approvals: [...sessions.values()].reduce((sum, session) => sum + session.pendingApprovals.size, 0),
        server_cpu_pct: Math.round(((usage.user + usage.system) / 1000 / elapsedMs) * 1000) / 10,
        server_rss_mb: Math.round(memory.rss / 1024 / 1024),
        system_mem_used_pct: Math.round((1 - os.freemem() / os.totalmem()) * 100),
        system_mem_total_gb: Math.round((os.totalmem() / 1024 ** 3) * 10) / 10,
        load_avg: os.loadavg().map((load) => Math.round(load * 100) / 100),
        cores: os.cpus().length,
      },
    };
    statsCache = { data: stats, at: now };
    res.json(stats);
  });
}
