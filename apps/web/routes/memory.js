// Memory layer routes (files + vector index) and the per-session memory notes routes. Moved out of server.ts unchanged.
import { randomUUID } from 'node:crypto';
                                                 
import { MEMORY_LAYERS,                                    } from '../memory.js';
                                                          
import { errorMessage } from '../types.js';
                                                               

                                  
                           
                                                                            
                                             
 

export function registerMemoryRoutes(app         , deps                 )       {
  const { memoryStore, persistence, sessions } = deps;
  // ─── Memory layers (files + vector index) ──────────────────────
  function memoryLayerParam(value         )                          {
    return MEMORY_LAYERS.includes(value               ) ? (value               ) : undefined;
  }

  app.get('/api/memory/status', (_req         , res          ) => {
    res.json({ root: memoryStore.root, namespace: memoryStore.namespace, counts: memoryStore.counts(), vector: memoryStore.vectorStatus });
  });

  app.get('/api/memory', async (req         , res          ) => {
    const layer = memoryLayerParam(req.query.layer);
    const limit = Math.min(Number(req.query.limit) || 50, 200);
    const query = typeof req.query.q === 'string' ? req.query.q.trim() : '';
    const preview = (item                     ) => item.content.replace(/\s+/g, ' ').slice(0, 240);
    if (query) {
      const { hits, backend } = await memoryStore.search(query, { layers: layer ? [layer] : undefined, topK: Math.min(limit, 25) });
      return res.json({ backend, items: hits.map(({ item, score }) => ({ ...item, content: preview(item), score })) });
    }
    res.json({ backend: 'list', items: memoryStore.list(layer, limit).map((item) => ({ ...item, content: preview(item) })) });
  });

  app.get('/api/memory/item', (req         , res          ) => {
    const item = memoryStore.get(String(req.query.id ?? ''));
    if (!item) return res.status(404).json({ error: 'Memory not found' });
    res.json(item);
  });

  app.post('/api/memory', async (req         , res          ) => {
    const layer = memoryLayerParam(req.body?.layer) ?? 'org';
    const title = String(req.body?.title ?? '').trim();
    const content = String(req.body?.content ?? '').trim();
    if (!title || !content) return res.status(400).json({ error: 'title and content are required' });
    if (layer === 'task') return res.status(400).json({ error: 'Task memory is written automatically by runs' });
    const tags = Array.isArray(req.body?.tags) ? req.body.tags.map(String) : String(req.body?.tags ?? '').split(',');
    const item = await memoryStore.write(layer, { title, content, tags, source: 'human' });
    for (const session of sessions.values()) session.broadcast({ type: 'memory_changed', data: { id: item.id } });
    res.status(201).json(item);
  });

  app.post('/api/memory/promote', async (req         , res          ) => {
    try {
      const item = await memoryStore.promote(String(req.body?.id ?? ''));
      for (const session of sessions.values()) session.broadcast({ type: 'memory_changed', data: { id: item.id } });
      res.json(item);
    } catch (err) {
      res.status(400).json({ error: errorMessage(err) });
    }
  });

  app.delete('/api/memory/item', async (req         , res          ) => {
    const removed = await memoryStore.remove(String(req.query.id ?? ''));
    if (!removed) return res.status(404).json({ error: 'Memory not found' });
    for (const session of sessions.values()) session.broadcast({ type: 'memory_changed', data: {} });
    res.json({ success: true });
  });

  // ─── Memory Notes (Persistent Storage) ────────────────────────
  app.get('/api/memory/notes', async (req         , res          ) => {
    try {
      const sessionId = req.query.sessionId          ;
      const layer = req.query.layer                      ;
      const limit = Math.min(parseInt(req.query.limit          , 10) || 20, 200);

      if (!sessionId) {
        return res.status(400).json({ error: 'sessionId required' });
      }

      const notes = await persistence.listMemoryNotes(sessionId, layer, limit);
      res.json({ notes });
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });

  app.post('/api/memory/notes', async (req         , res          ) => {
    try {
      const sessionId = req.query.sessionId          ;
      const body = req.body                           ;
      const title = body.title                      ;
      const content = body.content                      ;
      const layer = (body.layer                      ) ?? 'session';

      if (!sessionId || !title || !content) {
        return res.status(400).json({ error: 'sessionId, title, content required' });
      }

      const id = randomUUID();
      const now = Date.now();
      await persistence.saveMemoryNote({
        id,
        sessionId,
        layer: layer               ,
        title,
        content,
        createdAt: now,
        updatedAt: now
      });

      res.json({ id, title, layer, createdAt: now });
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });

  app.delete('/api/memory/notes/:id', async (req         , res          ) => {
    try {
      const id = req.params.id;
      // Phase 3: soft-delete tracking only; full DB delete in Phase 4
      res.json({ deleted: id });
    } catch (err) {
      res.status(500).json({ error: String(err) });
    }
  });
}
