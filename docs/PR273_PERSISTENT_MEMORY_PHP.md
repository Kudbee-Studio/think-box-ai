# PR 273 — Persistent Memory via PHP

**Status:** PLANNED  
**Priority:** CRITICAL  
**Scope:** Dashboard state persistence across logout/shutdown  
**Technology:** PHP backend + SQLite/PostgreSQL

---

## Problem Statement

Currently, the kudbEE Agent OS dashboard loses all state when:
- User logs out
- Browser closes
- Server restarts
- Connection drops

This breaks user experience for multi-session workflows and makes the system unsuitable for production.

---

## Solution Architecture

### Storage Layer (PHP Backend)

**File:** `backend/persistent_memory.php`

```php
<?php
class PersistentMemory {
    private $db;
    
    public function __construct($db_path = null) {
        // SQLite for simplicity (can upgrade to PostgreSQL)
        $db_path = $db_path ?? getenv('DB_PATH') ?? './data/memory.db';
        $this->db = new PDO("sqlite:" . $db_path);
        $this->initSchema();
    }
    
    // Schema for persistent dashboard state
    public function initSchema() {
        $this->db->exec("
            CREATE TABLE IF NOT EXISTS dashboard_state (
                id INTEGER PRIMARY KEY,
                session_id TEXT UNIQUE,
                user_id TEXT,
                panel_state JSON,           -- { 'left-sidebar': {open, scroll}, ... }
                view_state JSON,            -- { 'activeTab': 'metrics', ... }
                settings JSON,              -- { 'darkMode': true, ... }
                last_update DATETIME,
                created_at DATETIME,
                INDEX(session_id),
                INDEX(user_id)
            );
            
            CREATE TABLE IF NOT EXISTS run_metadata (
                id INTEGER PRIMARY KEY,
                run_id TEXT UNIQUE,
                session_id TEXT,
                goal TEXT,
                status TEXT,                -- running, completed, failed, stopped
                start_time DATETIME,
                end_time DATETIME,
                metrics JSON,               -- { p95, cost, tokens, ... }
                files JSON,                 -- array of file paths
                created_at DATETIME,
                FOREIGN KEY(session_id) REFERENCES dashboard_state(session_id)
            );
            
            CREATE TABLE IF NOT EXISTS memory_notes (
                id INTEGER PRIMARY KEY,
                session_id TEXT,
                layer TEXT,                 -- verified, org, task, session
                title TEXT,
                content TEXT,
                evidence JSON,              -- { source, timestamp }
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY(session_id) REFERENCES dashboard_state(session_id)
            );
        ");
    }
    
    // Save entire dashboard state
    public function saveState($session_id, $state) {
        $stmt = $this->db->prepare("
            INSERT OR REPLACE INTO dashboard_state 
            (session_id, panel_state, view_state, settings, last_update, created_at)
            VALUES (?, ?, ?, ?, NOW(), COALESCE(
                (SELECT created_at FROM dashboard_state WHERE session_id = ?), 
                NOW()
            ))
        ");
        return $stmt->execute([
            $session_id,
            json_encode($state['panels']),
            json_encode($state['views']),
            json_encode($state['settings']),
            $session_id
        ]);
    }
    
    // Restore dashboard state
    public function restoreState($session_id) {
        $stmt = $this->db->prepare(
            "SELECT panel_state, view_state, settings FROM dashboard_state WHERE session_id = ?"
        );
        $stmt->execute([$session_id]);
        $row = $stmt->fetch(PDO::FETCH_ASSOC);
        
        return $row ? [
            'panels' => json_decode($row['panel_state'], true),
            'views' => json_decode($row['view_state'], true),
            'settings' => json_decode($row['settings'], true)
        ] : null;
    }
    
    // Save run metadata
    public function saveRun($session_id, $run_id, $run_data) {
        $stmt = $this->db->prepare("
            INSERT OR REPLACE INTO run_metadata 
            (session_id, run_id, goal, status, start_time, end_time, metrics, files)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ");
        return $stmt->execute([
            $session_id,
            $run_id,
            $run_data['goal'],
            $run_data['status'],
            $run_data['start_time'],
            $run_data['end_time'] ?? null,
            json_encode($run_data['metrics'] ?? []),
            json_encode($run_data['files'] ?? [])
        ]);
    }
    
    // List runs for session
    public function listRuns($session_id, $limit = 50) {
        $stmt = $this->db->prepare("
            SELECT * FROM run_metadata 
            WHERE session_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        ");
        $stmt->execute([$session_id, $limit]);
        return $stmt->fetchAll(PDO::FETCH_ASSOC);
    }
}
?>
```

---

### API Endpoints (TypeScript/Node Bridge)

**Files:** `apps/web/server.ts`

```typescript
// Restore dashboard state on reconnect
POST /api/state/restore
  Input: { sessionId, userId }
  Output: { panels, views, settings }
  
// Save dashboard state (debounced, every 5s)
POST /api/state/save
  Input: { sessionId, state: { panels, views, settings } }
  Output: { success, lastUpdate }
  
// Get run history with metadata
GET /api/runs/history
  Query: { sessionId, limit=50 }
  Output: Array<{ runId, goal, status, metrics, files, timestamp }>
  
// Save run metadata
POST /api/runs/:runId/metadata
  Input: { sessionId, metrics, files, status }
  Output: { success }
```

---

### Frontend Integration

**File:** `apps/web/public/js/app.js`

```javascript
class DashboardPersistence {
  constructor(sessionId) {
    this.sessionId = sessionId;
    this.state = {};
    this.saveDebounce = debounce(() => this.saveState(), 5000);
  }

  // On page load
  async restore() {
    const response = await fetch('/api/state/restore', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sessionId: this.sessionId })
    });
    const state = await response.json();
    this.restorePanels(state.panels);
    this.restoreViews(state.views);
    this.restoreSettings(state.settings);
  }

  // On panel change (scroll, open/close, resize)
  onPanelChange(panelId, state) {
    this.state.panels = this.state.panels || {};
    this.state.panels[panelId] = state;
    this.saveDebounce();
  }

  // On view change (active tab, modal open, etc)
  onViewChange(viewId, state) {
    this.state.views = this.state.views || {};
    this.state.views[viewId] = state;
    this.saveDebounce();
  }

  // Save to backend
  async saveState() {
    await fetch('/api/state/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        sessionId: this.sessionId, 
        state: this.state 
      })
    });
  }
}
```

---

## Implementation Phases

### Phase 1: Core Persistence (Week 1)
- [ ] Create PHP backend with SQLite schema
- [ ] Implement restore/save endpoints
- [ ] Add state tracking to TypeScript frontend
- [ ] Test with manual refresh cycles

### Phase 2: Run History (Week 1)
- [ ] Save run metadata to database
- [ ] Restore run list on reconnect
- [ ] Display historical metrics
- [ ] Export run data as CSV/JSON

### Phase 3: Advanced Features (Week 2)
- [ ] Multi-device sync (if same user)
- [ ] Export/import session data
- [ ] Automated backups to S3/B2
- [ ] Encryption at rest (sensitive runs)

### Phase 4: Performance (Week 2)
- [ ] Index optimization (session_id, run_id)
- [ ] Connection pooling for concurrent saves
- [ ] Compress large JSON blobs
- [ ] Archive old runs (30+ days)

---

## Data Model

```
dashboard_state
├── session_id (PK)
├── panel_state: { 'file-tree': { scrollTop, open }, ... }
├── view_state: { 'activeTab': 'metrics', 'selectedRun': '123', ... }
├── settings: { 'theme': 'dark', 'notifications': true, ... }
├── created_at
└── last_update

run_metadata
├── run_id (PK)
├── session_id (FK)
├── goal
├── status: 'running' | 'completed' | 'failed' | 'stopped'
├── metrics: { p50, p95, cost, tokens, ... }
├── files: ['/path/to/file1', ...]
├── start_time
└── end_time

memory_notes
├── id (PK)
├── session_id (FK)
├── layer: 'verified' | 'org' | 'task' | 'session'
├── title
├── content
├── evidence: { source, timestamp }
└── created_at
```

---

## Benefits

✅ **User Experience:**
- Seamless reconnection after network drop
- Zero data loss on logout
- Cross-device continuity

✅ **Developers:**
- Easy to debug (query the database)
- Audit trail (all changes logged)
- Extensible (add new state types)

✅ **Operations:**
- Backup runs for compliance
- Analytics on usage patterns
- Performance monitoring (slow queries)

---

## Testing Strategy

```bash
# Test 1: State persistence
1. Open dashboard
2. Change panel sizes, scroll, open tabs
3. Refresh page
4. Verify all state restored

# Test 2: Run history
1. Run 5 goals
2. Close server
3. Restart server
4. Verify all 5 runs in history

# Test 3: Concurrent saves
1. Open dashboard in 2 tabs
2. Make changes in both
3. Verify no data loss

# Test 4: Large state
1. Open many panels, files, runs
2. Measure save/restore time
3. Verify < 200ms roundtrip
```

---

## Success Criteria

- [ ] Dashboard state persists across page refresh
- [ ] Run history available after server restart
- [ ] All saves complete in < 100ms
- [ ] No data loss in concurrent operations
- [ ] State restore time < 200ms on load
- [ ] SQLite file size stays < 50MB (with archival)

---

## Blockers/Risks

**Risk:** Large state objects (many runs, files)  
**Mitigation:** Implement archival (runs > 30 days to archive table)

**Risk:** Concurrent writes from multiple tabs  
**Mitigation:** Use SQLite transactions with SERIALIZABLE isolation

**Risk:** Query performance on large dataset  
**Mitigation:** Add indexes on session_id, run_id, created_at

---

## Related PRs

- **PR 272:** Dashboard CSS (in progress)
- **PR 271:** Security hardening (in progress)
- **PR 270:** Phase 3 optimization (merged)

---

**Next:** Start PR 273 after PR 272 merges. Expect 3-4 days for full implementation.
