# PR 274 — Token-by-Token Streaming UI

**Status:** PLANNED  
**Priority:** HIGH  
**Scope:** Real-time thought/reasoning display in terminal  
**Technology:** WebSocket streaming, terminal buffer management

---

## Problem Statement

Currently, agent thoughts appear as complete blocks after generation completes. This creates:
- **Perception of lag:** User sees nothing, then wall of text
- **Lack of transparency:** User doesn't know agent is thinking
- **Poor parity with Claude Code:** Claude Code streams reasoning live

**Target:** Match Claude Code's streaming experience — see reasoning as it happens.

---

## Current Flow (Blocking)

```
Agent generates thought → Complete → Send to frontend → Display
                          (slow, no feedback)
```

**UX Impact:** Feels sluggish, non-interactive

---

## Desired Flow (Streaming)

```
Agent generates token → Send immediately → Display in buffer → Next token
                        (immediate feedback)
```

**UX Impact:** Responsive, transparent, engaging

---

## Implementation

### 1. Backend Changes (TypeScript/Node)

**File:** `apps/web/server.ts` (WebSocket event handling)

```typescript
// Current: Collect full thought, then send
thought_complete: "..." 

// New: Stream tokens individually
THOUGHT_TOKEN: "..."  // Sent for each token
THOUGHT_START: null   // Signal start of thought block
THOUGHT_END: null     // Signal end of thought block
```

**Changes:**
```typescript
// Agent loop modification
async function* runAgent(goal, model, tools) {
  // ... setup ...
  
  for await (const chunk of model.stream(prompt, tools)) {
    if (chunk.type === 'THOUGHT_TOKEN') {
      // NEW: Send immediately
      ws.send(JSON.stringify({
        type: 'THOUGHT_TOKEN',
        content: chunk.content,  // Single token: "The", "user", "wants", ...
        timestamp: Date.now(),
        thinking_id: thoughtId   // Link tokens to same thought block
      }));
    }
  }
}
```

### 2. Frontend Changes (TypeScript)

**File:** `apps/web/public/js/app.js` (Terminal rendering)

```javascript
class ThoughtBuffer {
  constructor(terminalElement) {
    this.terminal = terminalElement;
    this.current_thought = null;
    this.buffer = '';
    this.streaming = false;
  }

  // Start a new thought block
  startThought(id) {
    this.streaming = true;
    this.current_thought = id;
    this.buffer = '';
    
    // Create thought element with streaming indicator
    const msg = document.createElement('div');
    msg.className = 'terminal-message assistant';
    msg.id = `thought-${id}`;
    msg.innerHTML = `
      <div class="message-header">
        <span class="message-role">💭 THINKING</span>
        <span class="streaming-indicator">▌</span>
      </div>
      <div class="message-content streaming"></div>
    `;
    this.terminal.appendChild(msg);
  }

  // Add token to current thought
  addToken(token, id) {
    if (this.current_thought !== id) {
      // Different thought ID, close previous
      this.endThought();
      this.startThought(id);
    }

    this.buffer += token;
    
    const element = document.querySelector(`#thought-${id} .message-content`);
    if (element) {
      element.textContent = this.buffer;
      
      // Smooth scroll to latest
      element.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }

  // End thought block
  endThought() {
    if (!this.current_thought) return;
    
    const element = document.querySelector(`#thought-${this.current_thought}`);
    if (element) {
      // Remove streaming indicator
      element.querySelector('.streaming-indicator').remove();
      element.querySelector('.message-content').classList.remove('streaming');
      element.querySelector('.message-role').textContent = '💭 THOUGHT';
    }
    
    this.streaming = false;
    this.current_thought = null;
    this.buffer = '';
  }
}

// WebSocket handler
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  
  switch (msg.type) {
    case 'THOUGHT_START':
      thoughtBuffer.startThought(msg.id);
      break;
      
    case 'THOUGHT_TOKEN':
      thoughtBuffer.addToken(msg.content, msg.thinking_id);
      break;
      
    case 'THOUGHT_END':
      thoughtBuffer.endThought();
      break;
      
    // ... other message types ...
  }
};
```

### 3. CSS for Streaming Effect

**File:** `apps/web/public/css/main-pro.css`

```css
/* Streaming thought message */
.terminal-message.assistant .message-content.streaming {
  position: relative;
  border-right: 2px solid var(--accent-light);
  animation: blink 0.8s infinite;
}

.streaming-indicator {
  display: inline-block;
  font-size: 14px;
  color: var(--accent-light);
  animation: blink 0.6s infinite;
  margin-left: 4px;
}

@keyframes blink {
  0%, 49% { opacity: 1; }
  50%, 100% { opacity: 0.3; }
}

/* Completed thought (no animation) */
.terminal-message.assistant .message-content:not(.streaming) {
  border-right: none;
  animation: none;
}
```

---

## Event Flow Diagram

```
Agent            Backend              WebSocket            Frontend
  |                 |                      |                  |
  |-- generate ---→ |                      |                  |
  |  token: "The"   |-- THOUGHT_TOKEN --→ |                  |
  |                 |                      |-- render token →  |
  |                 |                      |  ▌ (cursor blink) |
  |                 |                      |                  |
  |-- generate ---→ |                      |                  |
  |  token: "user"  |-- THOUGHT_TOKEN --→ |                  |
  |                 |                      |-- add to buffer → |
  |                 |                      |  "The user" ▌    |
  |                 |                      |                  |
  |-- ... more ---→ |                      |                  |
  |                 |                      |                  |
  |-- complete ---→ |-- THOUGHT_END ----→ |                  |
  |                 |                      |-- finalize ----→ |
  |                 |                      |  "The user wants" |
```

---

## Performance Considerations

**Challenge:** Rendering hundreds of tokens per second  
**Solution:** Batch tokens (5-10ms) to reduce DOM updates

```javascript
class BatchedThoughtBuffer extends ThoughtBuffer {
  constructor(terminalElement, batchMs = 5) {
    super(terminalElement);
    this.batchMs = batchMs;
    this.tokenQueue = [];
    this.batchTimeout = null;
  }

  addToken(token, id) {
    this.tokenQueue.push({ token, id });
    
    // Batch tokens together
    if (this.batchTimeout) clearTimeout(this.batchTimeout);
    this.batchTimeout = setTimeout(() => {
      this.flushBatch();
    }, this.batchMs);
  }

  flushBatch() {
    for (const { token, id } of this.tokenQueue) {
      super.addToken(token, id);
    }
    this.tokenQueue = [];
  }
}
```

**Result:** 100 tokens = 1 DOM update (vs 100 updates), 60fps smooth

---

## Testing Strategy

### Unit Tests
```javascript
// Test token streaming
test('addToken accumulates buffer', () => {
  const buffer = new ThoughtBuffer(element);
  buffer.startThought('1');
  buffer.addToken('Hello', '1');
  buffer.addToken(' world', '1');
  expect(buffer.buffer).toBe('Hello world');
});

// Test thought boundaries
test('different thought ID closes previous', () => {
  const buffer = new ThoughtBuffer(element);
  buffer.startThought('1');
  buffer.addToken('Thought1', '1');
  buffer.startThought('2');
  buffer.addToken('Thought2', '2');
  
  const thought1 = document.querySelector('#thought-1');
  expect(thought1.querySelector('.streaming-indicator')).toBeNull();
});
```

### Integration Tests
```javascript
// Test WebSocket streaming
test('WebSocket THOUGHT_TOKEN events render to terminal', async () => {
  const ws = new MockWebSocket();
  const terminal = new Terminal(element, ws);
  
  ws.send({ type: 'THOUGHT_START', id: '1' });
  ws.send({ type: 'THOUGHT_TOKEN', content: 'Hello', thinking_id: '1' });
  ws.send({ type: 'THOUGHT_TOKEN', content: ' world', thinking_id: '1' });
  ws.send({ type: 'THOUGHT_END', id: '1' });
  
  await wait(100);
  
  const msg = document.querySelector('#thought-1');
  expect(msg.textContent).toContain('Hello world');
  expect(msg.querySelector('.streaming-indicator')).toBeNull();
});
```

---

## Success Criteria

- [ ] Thoughts display token-by-token in real-time
- [ ] Streaming indicator (▌) visible while thinking
- [ ] Smooth 60fps rendering (no jank)
- [ ] Support for 100+ tokens/sec throughput
- [ ] Batching reduces DOM updates by 90%+
- [ ] Works across all event types (THOUGHT, TOOL_CALL, TOKEN)
- [ ] User perceives agent as "live" and responsive

---

## Phased Rollout

### Phase 1: Thoughts Only (MVP)
- [ ] Stream THOUGHT_TOKEN events
- [ ] Basic buffer + render
- [ ] Simple blinking cursor

### Phase 2: All Events
- [ ] Stream TOKEN events (model output)
- [ ] Stream TOOL_CALL events
- [ ] Consistent streaming UI across all types

### Phase 3: Advanced
- [ ] Syntax highlighting for code in thoughts
- [ ] Collapse/expand thought blocks
- [ ] Search within thoughts
- [ ] Export thought transcripts

---

## Comparison: Before vs After

| Aspect | Before | After |
|--------|--------|-------|
| **Perception** | Blocked, waiting | Responsive, live |
| **Latency feeling** | High (wait for complete) | Low (instant feedback) |
| **User transparency** | "What's it doing?" | "I see it thinking" |
| **Parity with Claude** | Behind | On-par |

---

## Related PRs

- **PR 272:** Dashboard CSS (in progress)
- **PR 273:** Persistent memory (planned)
- **PR 274:** This one (streaming UI)

---

## Implementation Timeline

- **Day 1:** Backend WebSocket changes, event structure
- **Day 2:** Frontend buffer class, rendering logic
- **Day 3:** CSS animations, batching optimization
- **Day 4:** Testing, edge cases, performance tuning
- **Day 5:** Polish, documentation, merge

**Estimate:** 3-5 days (depends on existing streaming support)

---

**Success:** User opens dashboard, sees agent thinking in real-time. "Wow, it's smart!"
