# Feature 1 Phase 2: Server Integration Plan

**Goal:** Wire PersistenceLayer into server.ts for state persistence

## Changes Required

### 1. Import & Initialize (top of server.ts)

```typescript
import PersistenceLayer from './persistence.ts';

// Global persistence
const persistence = new PersistenceLayer();
```

### 2. On WebSocket Connection (line 954)

**Add after line 958 (session created):**

```typescript
// Restore dashboard state from DB
const savedState = await persistence.restoreDashboardState(sessionId);
if (savedState?.settings) {
  Object.assign(session.config, savedState.settings);
}
```

**Add to init message (line 961):**

```typescript
data: {
  sessionId,
  config: session.config,
  models: await listModels(),
  plugins: getPlugins(),
  files: Array.from(session.files.entries()),
  tasks: session.tasks,
  thoughts: session.thoughts,
  restoredState: savedState,  // NEW: send restored state to client
},
```

### 3. Handle State Save Messages (in message handler, after line 1030)

```typescript
case 'state_save': {
  const state = {
    sessionId,
    panelState: msg.panelState,
    viewState: msg.viewState,
    settings: session.config,
    lastUpdate: Date.now(),
    createdAt: Date.now()
  };
  await persistence.saveDashboardState(state);
  ws.send(JSON.stringify({ type: 'state_saved', data: { success: true } }));
  break;
}
```

### 4. Persist Run on Completion

**Find where runs are saved (in runGoal method):**

```typescript
// After run completes and is saved to runs.json:
const runRecord = { /* existing run data */ };
await runs.add(runRecord);

// NEW: Also save to persistent DB
await persistence.saveRunMetadata({
  runId: runRecord.id,
  sessionId: this.id,
  goal: runRecord.goal,
  status: runRecord.status,
  startTime: runRecord.start_time,
  endTime: runRecord.end_time,
  metrics: {
    tokens: runRecord.prompt_tokens + runRecord.completion_tokens,
    cost: runRecord.cost_usd,
    duration: runRecord.duration_ms
  },
  files: runRecord.files ?? [],
  createdAt: runRecord.start_time
});
```

### 5. Add Run History Endpoint

**Add new route (after existing /api endpoints):**

```typescript
app.get('/api/runs/history', async (req, res) => {
  try {
    const sessionId = req.query.sessionId as string;
    const limit = Math.min(parseInt(req.query.limit as string, 10) || 50, 500);
    
    if (!sessionId) {
      return res.status(400).json({ error: 'sessionId required' });
    }
    
    // Try DB first, fallback to JSON file
    let runs = await persistence.listRuns(sessionId, limit);
    if (!runs.length) {
      // Fallback: load from JSON runs file
      const runStore = new RunStore();
      const allRuns = runStore.all().filter(r => r.sessionId === sessionId);
      runs = allRuns.slice(0, limit).map(r => ({
        runId: r.id,
        sessionId: r.sessionId,
        goal: r.goal,
        status: r.status,
        startTime: r.start_time,
        endTime: r.end_time,
        metrics: { tokens: r.prompt_tokens + r.completion_tokens, cost: r.cost_usd },
        files: r.files,
        createdAt: r.start_time
      }));
    }
    
    res.json({ runs });
  } catch (err) {
    res.status(500).json({ error: String(err) });
  }
});
```

### 6. Debounced State Save

**Add debounce utility (if not already present):**

```typescript
function debounce<T extends (...args: any[]) => Promise<void>>(
  fn: T,
  ms: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout | null = null;
  return (...args: Parameters<T>) => {
    if (timeout) clearTimeout(timeout);
    timeout = setTimeout(() => {
      void fn(...args);
      timeout = null;
    }, ms);
  };
}
```

**Wire into config changes (around line 1020-1022):**

```typescript
case 'update_config': {
  Object.assign(session.config, msg.config);
  
  // Debounce state save (500ms, only if data changed)
  const debouncedSave = debounce(async () => {
    await persistence.saveDashboardState({
      sessionId,
      settings: session.config,
      lastUpdate: Date.now(),
      createdAt: Date.now()
    });
  }, 500);
  
  debouncedSave();
  ws.send(JSON.stringify({ type: 'config_updated', data: session.config }));
  break;
}
```

## Testing Checklist

- [ ] Server starts with persistence layer initialized
- [ ] Dashboard state restores on reconnect
- [ ] Run metadata saved to DB after goal completion
- [ ] /api/runs/history returns runs from DB
- [ ] Fallback to JSON works if DB unavailable
- [ ] State save debounced (not firing on every keystroke)
- [ ] Server survives restart with state intact
- [ ] Old JSON run history still accessible

## Integration Order

1. Add import + global persistence instance
2. Wire restore on connection
3. Add state_save message handler
4. Wire into config changes (debounced)
5. Add /api/runs/history endpoint
6. Persist runs on completion
7. Test round-trip (kill server, restart, verify state)

## Files to Modify

- `apps/web/server.ts` — Main server file

## Files to Keep

- `apps/web/persistence.ts` — Core layer (no changes)
- `apps/web/tests/persistence.test.ts` — Tests (no changes)

## Success Criteria

✅ Dashboard KPIs persist across server restart  
✅ Run history available immediately after reconnect  
✅ /api/runs/history returns data from persistent DB  
✅ Fallback to JSON file if DB unavailable  
✅ No performance regression (caching + debounce)  

## Next: Phase 3

Once Phase 2 is integrated and tested:
- Wire CLI `/remember` to save memory_notes
- Add task episode auto-save
- Add memory layer UI integration
