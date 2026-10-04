// THINK BOX AI — kudbEE Agent OS (Enterprise Edition)

// `Enterprise` is declared globally by enterprise.js (loaded first); redeclaring it here is a SyntaxError.

import { AnalyticsDashboardUI } from './analytics-ui.js';
import { TimelineUI } from './timeline-ui.js';
import { SharingUI } from './sharing-ui.js';
import { TemplateBrowserUI } from './template-browser-ui.js';

const state = {
  ws: null,
  sessionId: null,
  isRunning: false,
  models: [],
  plugins: [],
  tasks: [],
  taskFilters: { query: '', status: 'all', priority: 'all' },
  thoughts: [],
  thoughtFilter: 'all',
  pluginQuery: '',
  runs: [],
  runProgress: Object.create(null),
  approvals: [],
  openRunId: null,
  memoryLayer: '',
  memoryQuery: '',
  openMemoryId: null,
  config: {
    model: '',
    provider: '',
  }
};

// Session ids are server-made UUIDs. The id arrives over the WebSocket, so check its shape once and encode it into every URL it appears in.
const SESSION_ID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
function sessionApi() {
  return `/api/sessions/${encodeURIComponent(state.sessionId)}`;
}

function connectWebSocket() {
  const sdk = window.KudbeeSdkBrowser?.loadConfig?.() ?? null;
  const wsUrl = sdk?.wsUrl ?? `ws://${window.location.hostname}:${window.location.port || 3000}/ws`;
  const backendUrl = wsUrl.replace(/^ws/, 'http').replace(/\/ws$/, '');
  state.correlationId = sdk?.newCorrelationId?.() ?? null;
  state.ws = new WebSocket(wsUrl);

  state.ws.onopen = () => {
    console.log('kudbEE WebSocket connected');
    window.startupGuard?.ok('connection');
    document.getElementById('header-connection').innerHTML = '<span class="connection-dot"></span> Connected';
    appendTerminalMessage('system', '🐝 Connected to kudbEE backend');
    // Live link: also show goals run from the kudbee CLI (same engine and data) in this terminal.
    state.ws.send(JSON.stringify({ type: 'subscribe_runs' }));
    setStatus('idle', 'Ready');
    enableInput(true);
  };

  state.ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      handleMessage(msg);
    } catch (err) {
      console.error('Parse error:', err);
    }
  };

  state.ws.onerror = () => {
    window.startupGuard?.fail('connection', 'WebSocket error');
    appendTerminalMessage('error', `WebSocket connection error — check ${backendUrl}/api/health`);
  };

  state.ws.onclose = () => {
    document.getElementById('header-connection').innerHTML = '<span class="connection-dot offline"></span> Reconnecting';
    setStatus('error', 'Disconnected');
    appendTerminalMessage('system', 'Disconnected — retrying in 3s...');
    setTimeout(connectWebSocket, 3000);
  };
}

function handleMessage(msg) {
  // Feed the agent registry first: it folds run/task/think-cube/approval messages into tracked agents and fires `agents:changed`.
  if (window.agentRegistry) window.agentRegistry.ingest(msg);
  // Real server events (thoughts, approvals, memory, Think Tokens) become terminal lines; other message types are shown by their handlers below.
  window.KudbeeTerminal?.ingest(msg, { provider: state.config?.provider });
  switch (msg.type) {
    case 'init':
      state.sessionId = SESSION_ID_PATTERN.test(String(msg.data.sessionId)) ? msg.data.sessionId : null;
      state.plugins = msg.data.plugins || [];
      state.models = msg.data.models || [];
      state.config = { ...state.config, ...(msg.data.config || {}) };
      state.tasks = msg.data.tasks || [];
      state.thoughts = [];
      renderTasks();
      renderThoughts();
      renderPlugins();
      renderTasks();
      renderModels();
      window.startupGuard?.ok('models');
      setStatus('idle', 'Ready');
      appendTerminalMessage(state.sessionId ? 'system' : 'error', state.sessionId ? `Session: ${state.sessionId.slice(0, 8)}` : 'The server sent an invalid session id; reload the page.');
      refreshFiles();
      break;

    case 'profile_changed':
      // Another client switched the active profile. Re-read memory and runs, which are now that profile's.
      refreshMemory();
      refreshRuns();
      if (window.profileSwitcher && window.profileSwitcher.store) void window.profileSwitcher.store.refresh();
      break;

    case 'mirror': {
      // A run started from the kudbee CLI, relayed by the server. Shown as labeled terminal lines only: it never changes this session's status or input.
      const inner = msg.data?.message;
      const label = `[${msg.data?.client || 'cli'} ${msg.data?.session || ''}]`;
      if (inner?.type === 'thought') {
        window.KudbeeTerminal?.ingest({ ...inner, data: { ...inner.data, content: `${label} ${inner.data?.content ?? ''}` } }, { provider: state.config?.provider });
      } else if (inner?.type === 'result') {
        const r = inner.data || {};
        appendTerminalMessage(r.success ? 'assistant' : 'error', `${label} ${r.success ? '✓' : '✗'} ${r.result || r.error || 'finished'}`);
        refreshRuns();
      } else if (inner?.type === 'queued') {
        appendTerminalMessage('system', `${label} ⏳ queued: ${inner.data?.goal || ''}`);
      } else if (inner?.type === 'run_update') {
        scheduleRunsRefresh();
      } else if (inner?.type === 'think_token_learned' || inner?.type === 'think_token_used') {
        window.dispatchEvent(new CustomEvent('think-tokens:message', { detail: inner }));
      }
      break;
    }

    case 'status':
      setStatus(msg.data, msg.data === 'running' ? 'Running' : 'Idle');
      break;

    case 'stream':
      appendTerminalStream(msg.data);
      break;

    case 'thought': {
      // The server stamps each thought inside `data`; the message itself carries no timestamp (spreading msg.timestamp over it gave "Invalid Date").
      const thought = { ...msg.data, timestamp: msg.data?.timestamp ?? msg.timestamp ?? Date.now() };
      addThought(thought);
      // Real bridge to the Think Token cube and view: every thought the server actually emits, forwarded as-is,
      // no synthesized events. Persisted tokens arrive separately (think_tokens), read from the database.
      window.dispatchEvent(new CustomEvent('think-cube:thought', { detail: thought }));
      break;
    }

    case 'task':
      addTask({ ...msg.data, timestamp: msg.data?.timestamp ?? msg.timestamp ?? Date.now() });
      break;

    case 'task_update':
      updateTask(msg.data);
      break;

    case 'task_action_result':
      renderTaskActionResult(msg.data);
      break;

    case 'git_action_result':
      appendTerminalMessage(msg.data.success ? 'system' : 'error', msg.data.success
        ? `Git ${msg.data.action || 'action'}${msg.data.path ? ` · ${msg.data.path}` : ''}\n${msg.data.output || ''}`
        : `Git failed: ${msg.data.error || 'unknown error'}`);
      if (msg.data.success && msg.data.action === 'clone') refreshFiles();
      break;

    case 'plugin_result':
      appendTerminalMessage('plugin', `[${msg.data.plugin}] ${msg.data.result.success ? '✓' : '✗'}\n${JSON.stringify(msg.data.result, null, 2)}`);
      break;

    case 'models':
      state.models = msg.data;
      renderModels();
      break;

    case 'files_changed':
      refreshFiles();
      break;

    case 'run_update':
      window.dispatchEvent(new CustomEvent('think-cube:run', { detail: { id: msg.data.id, status: msg.data.status } }));
      state.runProgress[msg.data.id] = msg.data;
      renderTasks();
      scheduleRunsRefresh();
      if (state.openRunId === msg.data.id) openRun(msg.data.id);
      break;

    case 'memory_changed':
      scheduleMemoryRefresh();
      break;

    case 'think_tokens':
    case 'think_token_result':
    case 'think_token_error':
    case 'think_token_cube':
    case 'think_tokens_changed':
    case 'think_token_learned':
    case 'think_token_used':
      window.dispatchEvent(new CustomEvent('think-tokens:message', { detail: msg }));
      break;

    case 'queued':
      appendTerminalMessage('system', `⏳ Queued #${msg.data.position}: ${msg.data.goal}`);
      break;

    case 'approval_request':
      state.approvals.push({ ...msg.data, received_at: Date.now() });
      showNextApproval();
      break;

    case 'approval_resolved':
      state.approvals = state.approvals.filter(a => a.id !== msg.data.id);
      showNextApproval();
      break;

    case 'result': {
      const r = msg.data || {};
      document.querySelector('.terminal-stream')?.classList.remove('terminal-stream');
      window.KudbeeTerminal?.endStream();
      const stats = r.steps !== undefined
        ? `\n— ${r.steps} step(s) · ${r.tool_calls} tool call(s) · ${r.tokens} tokens · ${formatUsd(r.cost_usd)} · ${((r.duration_ms || 0) / 1000).toFixed(1)}s`
        : '';
      if (r.cancelled) {
        appendTerminalMessage('system', `⊘ ${r.error}`);
      } else if (r.success) {
        setStatus('idle', 'Completed');
        // A streamed (local chat) answer is already in the terminal token by token; show only the completion line.
        appendTerminalMessage('assistant', `✓ ${r.streamed ? 'Done' : r.result || 'Done'}${stats}`);
      } else {
        setStatus('error', 'Failed');
        appendTerminalMessage('error', `✗ ${r.error || 'Goal failed'}${stats}`);
      }
      refreshFiles();
      refreshStats();
      refreshRuns();
      enableInput(true);
      break;
    }

    case 'specialist_result': {
      const r = msg.data || {};
      const specialists = (r.specialistsExecuted || []).map((run) =>
        `  ${run.specialistId}: ${run.status}${run.failure ? ` — ${run.failure}` : ''} · box ${run.thinkBoxId}`,
      );
      const summary = [
        `Specialist job ${r.jobId || ''} · ${r.status || 'UNKNOWN'}`,
        `Selected: ${(r.specialistsSelected || []).join(', ') || '(none)'}`,
        ...specialists,
        `Evidence: ${(r.evidence || []).length} · Validator: ${r.validation?.valid ? 'PASS' : 'FAIL'}`,
        `Proof: ${r.proof?.ok ? 'accepted' : 'refused'} · Think Tokens: ${(r.thinkToken || []).length}`,
        r.artifactPath ? `Artifact: ${r.artifactPath}` : '',
      ].filter(Boolean).join('\n');
      setStatus(r.status === 'COMPLETED' ? 'idle' : 'error', r.status === 'COMPLETED' ? 'Specialists completed' : 'Specialist job failed');
      appendTerminalMessage(r.status === 'COMPLETED' ? 'assistant' : 'error', summary);
      refreshFiles();
      refreshRuns();
      enableInput(true);
      break;
    }

    case 'error':
      appendTerminalMessage('error', `Error: ${msg.data}`);
      setStatus('error', 'Error');
      enableInput(true);
      break;
  }
}

// ─── Terminal ──────────────────────────────────────────────────
function appendTerminalMessage(role, content) {
  if (window.KudbeeTerminal) return window.KudbeeTerminal.local(role, content);
  const terminal = document.getElementById('terminal');
  const welcome = terminal.querySelector('.terminal-welcome');
  if (welcome) welcome.remove();

  const msg = document.createElement('div');
  msg.className = `terminal-message ${role}`;

  const header = document.createElement('div');
  header.className = 'message-header';
  header.innerHTML = `<span class="message-role">${escapeHtml(role)}</span><span class="message-time">${new Date().toLocaleTimeString()}</span>`;

  const body = document.createElement('div');
  body.className = 'message-content';
  body.textContent = content;

  msg.appendChild(header);
  msg.appendChild(body);
  terminal.appendChild(msg);
  terminal.scrollTop = terminal.scrollHeight;
}

function appendTerminalStream(token) {
  if (window.KudbeeTerminal) return window.KudbeeTerminal.stream(token);
  const terminal = document.getElementById('terminal');
  let streamEl = terminal.querySelector('.terminal-stream');
  if (!streamEl) {
    streamEl = document.createElement('div');
    streamEl.className = 'terminal-message assistant terminal-stream';
    const body = document.createElement('div');
    body.className = 'message-content';
    streamEl.appendChild(body);
    terminal.appendChild(streamEl);
  }
  const body = streamEl.querySelector('.message-content');
  body.textContent += token;
  terminal.scrollTop = terminal.scrollHeight;
}

function appendTerminalImage(role, content, imageUrl, alt) {
  if (window.KudbeeTerminal) return window.KudbeeTerminal.local(role, `${content}\n[image] ${alt}: ${imageUrl}`);
  const terminal = document.getElementById('terminal');
  const welcome = terminal.querySelector('.terminal-welcome');
  if (welcome) welcome.remove();
  const message = document.createElement('div');
  message.className = `terminal-message ${role}`;
  const header = document.createElement('div');
  header.className = 'message-header';
  header.innerHTML = `<span class="message-role">${escapeHtml(role)}</span><span class="message-time">${new Date().toLocaleTimeString()}</span>`;
  const body = document.createElement('div');
  body.className = 'message-content';
  body.textContent = content;
  const image = document.createElement('img');
  image.className = 'terminal-image';
  if (isSafeImageUrl(imageUrl)) image.src = imageUrl;
  image.alt = alt;
  message.append(header, body, image);
  terminal.appendChild(message);
  terminal.scrollTop = terminal.scrollHeight;
}

async function analyzeImage(file) {
  if (!file || !state.sessionId) return;
  if (file.size > 12 * 1024 * 1024) {
    appendTerminalMessage('error', 'Image is larger than the 12 MB limit.');
    return;
  }
  const form = new FormData();
  form.append('image', file);
  appendTerminalMessage('user', `Analyze image: ${file.name}`);
  setStatus('running', 'Analyzing image');
  try {
    const response = await fetch(`${sessionApi()}/images/analyze`, { method: 'POST', body: form });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || response.statusText);
    appendTerminalImage('assistant', result.answer, result.imageUrl, file.name);
    await refreshFiles();
  } catch (error) {
    appendTerminalMessage('error', `Image analysis failed: ${error.message}. Start the Janus image service to enable image tools.`);
  } finally {
    setStatus('idle', 'Ready');
    document.getElementById('analyze-image-input').value = '';
  }
}

async function generateImage() {
  const input = document.getElementById('goal-input');
  const prompt = input.value.trim();
  if (!prompt) {
    appendTerminalMessage('system', 'Enter an image prompt before generating.');
    input.focus();
    return;
  }
  if (!state.sessionId) return;
  appendTerminalMessage('user', `Generate image: ${prompt}`);
  setStatus('running', 'Generating image');
  try {
    const response = await fetch(`${sessionApi()}/images/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || response.statusText);
    appendTerminalImage('assistant', `Generated from: ${prompt}`, result.imageUrl, prompt);
    input.value = '';
    await refreshFiles();
  } catch (error) {
    appendTerminalMessage('error', `Image generation failed: ${error.message}. Start the Janus image service to enable image tools.`);
  } finally {
    setStatus('idle', 'Ready');
  }
}

function clearTerminal() {
  if (window.KudbeeTerminal) {
    window.KudbeeTerminal.clear();
    state.thoughts = [];
    renderThoughts();
    return;
  }
  const terminal = document.getElementById('terminal');
  terminal.innerHTML = `
    <div class="terminal-welcome">
      <div class="welcome-line">🐝 kudbEE — Agent OS</div>
      <div class="welcome-line">Type a goal and press Run to start.</div>
      <div class="welcome-line">Make sure Ollama is running: <code>ollama serve</code></div>
      <div class="welcome-line">Backend: ${escapeHtml(window.location.origin)}/ws</div>
    </div>
  `;
  state.thoughts = [];
  renderThoughts();
}

// ─── Status ────────────────────────────────────────────────────
function setStatus(status, text) {
  const dot = document.getElementById('status-dot');
  const statusText = document.getElementById('status-text');

  dot.className = `status-dot ${status}`;
  statusText.textContent = text;
  state.isRunning = status === 'running';

  const runBtn = document.getElementById('run-goal');
  const stopBtn = document.getElementById('stop-goal');
  const input = document.getElementById('goal-input');

  const submitBtn = document.getElementById('submit-goal');
  const running = status === 'running';
  // Input stays usable while an agent runs: new goals are queued by the server.
  runBtn.disabled = false;
  submitBtn.disabled = false;
  stopBtn.disabled = !running;
  input.disabled = false;
  runBtn.textContent = running ? '＋ Queue' : '▶ Run';
  submitBtn.textContent = running ? 'Queue' : 'Run';
}

function enableInput(enabled) {
  document.getElementById('goal-input').disabled = !enabled;
  document.getElementById('run-goal').disabled = !enabled;
  document.getElementById('submit-goal').disabled = !enabled;
  document.getElementById('stop-goal').disabled = enabled;
}

// ─── Tasks ─────────────────────────────────────────────────────
function addTask(task) {
  const index = state.tasks.findIndex(existing => existing.id === task.id);
  if (index === -1) state.tasks.push(task);
  else state.tasks[index] = { ...state.tasks[index], ...task };
  renderTasks();
}

function updateTask(updated) {
  const idx = state.tasks.findIndex(t => t.id === updated.id);
  if (idx !== -1) {
    state.tasks[idx] = updated;
    renderTasks();
  }
}

function renderTasks() {
  const container = document.getElementById('task-list');
  const count = document.getElementById('task-count');
  const summary = document.getElementById('task-summary');
  const openTasks = state.tasks.filter(task => ['pending', 'running', 'blocked'].includes(task.status));
  const today = new Date().toISOString().slice(0, 10);
  const overdue = openTasks.filter(task => task.dueDate && task.dueDate < today);
  count.textContent = state.tasks.length;
  summary.innerHTML = `
    <span><strong>${openTasks.length}</strong> open</span>
    <span><strong>${state.tasks.filter(task => task.status === 'blocked').length}</strong> blocked</span>
    <span class="${overdue.length ? 'overdue' : ''}"><strong>${overdue.length}</strong> overdue</span>
  `;
  if (state.tasks.length === 0) {
    container.innerHTML = '<div class="empty-state">No tasks yet</div>';
    return;
  }

  const visible = state.tasks.filter(task => {
    const query = state.taskFilters.query;
    const text = `${task.title || ''} ${task.description || ''} ${task.id} ${task.assignee || ''} ${(task.tags || []).join(' ')}`.toLowerCase();
    const queryMatches = !query || text.includes(query);
    const statusMatches = state.taskFilters.status === 'all'
      || (state.taskFilters.status === 'open' ? ['pending', 'running', 'blocked'].includes(task.status) : state.taskFilters.status === 'overdue'
        ? Boolean(task.dueDate && task.dueDate < today && ['pending', 'running', 'blocked'].includes(task.status))
        : task.status === state.taskFilters.status);
    const priorityMatches = state.taskFilters.priority === 'all' || task.priority === state.taskFilters.priority;
    return queryMatches && statusMatches && priorityMatches;
  }).sort((left, right) => {
    const rank = { critical: 0, high: 1, medium: 2, low: 3 };
    return (rank[left.priority] ?? 2) - (rank[right.priority] ?? 2) || right.timestamp - left.timestamp;
  });
  if (!visible.length) {
    container.innerHTML = '<div class="empty-state">No tasks match these filters</div>';
    return;
  }
  const openActivity = new Set([...container.querySelectorAll('.task-activity[open]')]
    .map(details => details.closest('.task-item')?.dataset.task));
  container.innerHTML = visible.map(task => {
    const overdueTask = task.dueDate && task.dueDate < today && ['pending', 'running', 'blocked'].includes(task.status);
    const actions = task.status === 'completed' ? '' : `
      <button type="button" class="task-action" data-task-action="${task.status === 'running' ? 'done' : 'start'}" data-task-id="${escapeHtml(task.id)}">${task.status === 'running' ? 'Complete' : 'Start'}</button>
      <button type="button" class="task-action" data-task-action="block" data-task-id="${escapeHtml(task.id)}">Block</button>
    `;
    const attachments = (task.attachments || []).filter(image => isSafeImageUrl(image.imageUrl)).map(image => `<img class="task-attachment" src="${escapeHtml(image.imageUrl)}" alt="${escapeHtml(image.filename)}" loading="lazy">`).join('');
    const activity = (task.activity || []).slice(-5).reverse().map(item => `<div class="task-activity-row"><span>${escapeHtml(item.action)}</span><small>${escapeHtml(item.actor)} · ${new Date(item.timestamp).toLocaleString()}</small>${item.note ? `<p>${escapeHtml(item.note)}</p>` : ''}</div>`).join('');
    return `
      <article class="task-item ${escapeHtml(task.status)} priority-${escapeHtml(task.priority || 'medium')}" data-task="${escapeHtml(task.id)}"${state.runProgress[task.id] ? ` data-run="${escapeHtml(task.id)}" title="Click to open run timeline"` : ''}>
        <div class="task-header">
          <span class="task-status ${escapeHtml(task.status)}">${escapeHtml(task.status.replace('_', ' '))}</span>
          <span class="task-priority ${escapeHtml(task.priority || 'medium')}">${escapeHtml(task.priority || 'medium')}</span>
          <code title="${escapeHtml(task.id)}">${escapeHtml(task.id.slice(0, 8))}</code>
        </div>
        <div class="task-description">${escapeHtml(task.title || task.description || 'Untitled task')}</div>
        ${runProgressLine(task)}
        ${task.blockedReason ? `<div class="task-blocked-reason">${escapeHtml(task.blockedReason)}</div>` : ''}
        <div class="task-meta">
          ${task.assignee ? `<span>Owner: ${escapeHtml(task.assignee)}</span>` : '<span>Unassigned</span>'}
          ${task.dueDate ? `<span class="${overdueTask ? 'overdue' : ''}">Due ${escapeHtml(task.dueDate)}</span>` : ''}
        </div>
        ${(task.tags || []).length ? `<div class="task-tags">${task.tags.map(tag => `<span>${escapeHtml(tag)}</span>`).join('')}</div>` : ''}
        ${attachments ? `<div class="task-attachments">${attachments}</div>` : ''}
        <div class="task-card-actions">
          ${actions}
          <button type="button" class="task-action" data-task-attach="${escapeHtml(task.id)}">Attach image</button>
        </div>
        <details class="task-activity"${openActivity.has(task.id) ? ' open' : ''}><summary>Activity (${(task.activity || []).length})</summary>${activity || '<div class="task-activity-row">No activity recorded</div>'}</details>
      </article>
    `;
  }).join('');
}

/** Live step progress (running) or run summary (finished) for tasks created by the worker agent. */
function runProgressLine(task) {
  const run = state.runProgress[task.id];
  if (!run) return '';
  if (task.status === 'running' && !run.ended_at) {
    const elapsed = ((Date.now() - run.started_at) / 1000).toFixed(0);
    return `<div class="task-progress">Step ${Number(run.current_step) || 1} · ${escapeHtml(run.current_action || 'thinking')} · ${Number(elapsed) || 0}s</div>`;
  }
  if (run.ended_at) {
    return `<div class="task-progress">${Number(run.current_step) || 0} step(s) · ${Number(run.tool_calls) || 0} tool(s) · ${formatUsd(run.cost_usd)} · ${((run.duration_ms || 0) / 1000).toFixed(1)}s · timeline ›</div>`;
  }
  return '';
}

// Only the elapsed-time line changes every second; re-rendering the whole list here replaced the
// buttons mid-click and collapsed any open Activity section.
function tickRunningTasks() {
  document.querySelectorAll('#task-list .task-item.running[data-task]').forEach(item => {
    const task = state.tasks.find(t => t.id === item.dataset.task);
    const line = item.querySelector('.task-progress');
    if (task && line) line.outerHTML = runProgressLine(task);
  });
}

function renderTaskActionResult(result) {
  if (!result?.success) {
    appendTerminalMessage('error', `Task command failed: ${result?.error || 'unknown error'}`);
    return;
  }
  if (result.action === 'list') {
    const tasks = result.tasks || [];
    appendTerminalMessage('system', tasks.length
      ? tasks.map(task => `${task.id.slice(0, 8)} [${task.status}/${task.priority}] ${task.title}${task.assignee ? ` · ${task.assignee}` : ''}${task.dueDate ? ` · due ${task.dueDate}` : ''}`).join('\n')
      : 'No tasks match that query.');
    return;
  }
  if (result.action === 'show') {
    appendTerminalMessage('system', JSON.stringify(result.task, null, 2));
    return;
  }
  const task = result.task;
  appendTerminalMessage('system', `Task ${task.id.slice(0, 8)} ${result.action}: ${task.title} [${task.status}/${task.priority}]`);
}

// Used by think-token-dashboard.js; the server validates every field and gates mutations behind approval.
function sendThinkTokenMessage(message) {
  if (state.ws?.readyState !== WebSocket.OPEN) return false;
  state.ws.send(JSON.stringify(message));
  return true;
}
// app.js is an ES module, so its functions are not globals; the classic script think-token-dashboard.js reaches this one through window.
window.sendThinkTokenMessage = sendThinkTokenMessage;

function sendTaskAction(action, payload = {}) {
  if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
    appendTerminalMessage('error', 'Connect to the Agent OS backend before managing tasks.');
    return;
  }
  state.ws.send(JSON.stringify({ type: 'task_action', action, payload }));
}

function sendGitAction(action, payload = {}) {
  if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
    appendTerminalMessage('error', 'Connect to the Agent OS backend before running Git actions.');
    return;
  }
  state.ws.send(JSON.stringify({ type: 'git_action', action, payload }));
}

// ─── Thoughts ──────────────────────────────────────────────────
/** A time of day, or nothing at all for a missing or invalid timestamp: never the text "Invalid Date". */
function formatThoughtTime(timestamp) {
  if (timestamp === null || timestamp === undefined || timestamp === '') return '';
  const date = new Date(timestamp);
  return Number.isFinite(date.getTime()) ? date.toLocaleTimeString() : '';
}

function addThought(thought) {
  state.thoughts.push(thought);
  renderThoughts();
}

function renderThoughts() {
  const container = document.getElementById('thought-list');
  const count = document.getElementById('thought-count');
  count.textContent = state.thoughts.length;

  if (state.thoughts.length === 0) {
    container.innerHTML = '<div class="empty-state">No thoughts yet</div>';
    return;
  }

  const visibleThoughts = state.thoughts.filter(thought => state.thoughtFilter === 'all' || thought.status === state.thoughtFilter);
  container.innerHTML = visibleThoughts.slice(-50).reverse().map(thought => `
    <div class="thought-item ${escapeHtml(thought.status || 'info')}">
      <div class="thought-header">
        <span class="thought-type">${escapeHtml(thought.type || 'thought')}</span>
        <span>${formatThoughtTime(thought.timestamp)}</span>
      </div>
      <div class="thought-content">${escapeHtml(thought.content || thought.plugin || '')}</div>
    </div>
  `).join('');
}

// ─── Plugins ───────────────────────────────────────────────────
function renderPlugins() {
  const container = document.getElementById('plugin-list');
  if (!state.plugins.length) {
    container.innerHTML = '<div class="empty-state">No plugins loaded</div>';
    return;
  }

  const query = state.pluginQuery.toLowerCase();
  const visiblePlugins = state.plugins.filter(plugin => !query || `${plugin.name} ${plugin.description} ${plugin.permission}`.toLowerCase().includes(query));
  container.innerHTML = visiblePlugins.map(plugin => `
    <div class="plugin-item">
      <span class="plugin-icon">${escapeHtml(plugin.icon || '🔌')}</span>
      <div class="plugin-info">
        <div class="plugin-name">${escapeHtml(plugin.name)}</div>
        <div class="plugin-desc">${escapeHtml(plugin.description)}</div>
      </div>
      <span class="plugin-badge ${escapeHtml(plugin.permission)}">${escapeHtml(plugin.permission)}</span>
      <button type="button" class="plugin-test" data-plugin="${escapeHtml(plugin.name)}">Test</button>
    </div>
  `).join('');
}

function testPlugin(pluginName) {
  if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
    appendTerminalMessage('error', 'Connect to the Agent OS backend before testing a plugin.');
    return;
  }
  state.pendingPlugin = pluginName;
  const plugin = state.plugins.find(item => item.name === pluginName);
  document.getElementById('plugin-modal-title').textContent = `Test ${pluginName}`;
  document.getElementById('plugin-permission-note').textContent = plugin && plugin.permission !== 'read_only'
    ? `This test uses ${plugin.permission} permission. Review the input before running.`
    : 'Read-only test. No workspace changes are expected.';
  document.getElementById('plugin-permission-note').className = `permission-note ${plugin?.permission || 'read_only'}`;
  document.getElementById('plugin-input').value = '{}';
  document.getElementById('plugin-modal').hidden = false;
  document.getElementById('plugin-input').focus();
}

function closePluginModal() {
  document.getElementById('plugin-modal').hidden = true;
  state.pendingPlugin = null;
}

function submitPluginTest() {
  try {
    const input = JSON.parse(document.getElementById('plugin-input').value);
    state.ws.send(JSON.stringify({ type: 'plugin_execute', plugin: state.pendingPlugin, input }));
    appendTerminalMessage('system', `Testing plugin: ${state.pendingPlugin}`);
    closePluginModal();
  } catch {
    appendTerminalMessage('error', 'Plugin input must be valid JSON.');
  }
}

async function refreshFiles() {
  if (!state.sessionId) return;
  const response = await fetch(`${sessionApi()}/files`, { cache: 'no-store' });
  if (!response.ok) return;
  const data = await response.json();
  const tree = document.getElementById('file-tree');
  renderGitRepositories(data.files);
  // Git internals (repositories/<name>/.git/...) are noise in the file list; the repository row shows status, log, diff and branch instead.
  const visibleFiles = data.files.filter(file => !/(^|\/)\.git(\/|$)/.test(file.path));
  tree.innerHTML = visibleFiles.length
    ? visibleFiles.map(file => `<button class="file-tree-item" data-path="${escapeHtml(file.path)}"><span>${escapeHtml(file.path)}</span><small>${escapeHtml(formatBytes(file.size))}</small></button>`).join('')
    : '<div class="file-tree-empty">No files in workspace</div>';
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

async function uploadFiles(fileList) {
  if (!state.sessionId || !fileList.length) return;
  const form = new FormData();
  Array.from(fileList).forEach(file => form.append('files', file, file.webkitRelativePath || file.name));
  const response = await fetch(`${sessionApi()}/files`, { method: 'POST', body: form });
  const result = await response.json();
  if (!response.ok) {
    appendTerminalMessage('error', `Upload failed: ${result.error || response.statusText}`);
    return;
  }
  appendTerminalMessage('system', `Uploaded ${result.uploaded.length} file(s) into the session workspace.`);
  await refreshFiles();
}

async function previewFile(filePath) {
  const extension = filePath.split('.').pop().toLowerCase();
  if (['png', 'jpg', 'jpeg', 'webp', 'gif'].includes(extension)) {
    const imageUrl = `${sessionApi()}/files/raw?path=${encodeURIComponent(filePath)}`;
    appendTerminalImage('system', filePath, imageUrl, filePath);
    return;
  }
  const response = await fetch(`${sessionApi()}/files/content?path=${encodeURIComponent(filePath)}`);
  const result = await response.json();
  if (!response.ok) {
    appendTerminalMessage('error', `Preview failed: ${result.error}`);
    return;
  }
  appendTerminalMessage('system', `${filePath}\n\n${result.content}`);
}

// Buttons and shortcuts call this directly so they never overwrite a goal the user is typing.
async function runCommand(command) {
  const name = command.split(/\s+/)[0];
  try {
    if (!(await runSlashCommand(command))) {
      appendTerminalMessage('error', `Unknown command ${name}. Type /help for the list.`);
    }
  } catch (error) {
    appendTerminalMessage('error', `${name} failed: ${error.message}`);
  }
}

function showHelp() {
  void runCommand('/help');
}

async function runSlashCommand(command) {
  const tokens = tokenizeTerminalCommand(command);
  const [name, ...args] = tokens;
  if (name?.toLowerCase() === '/task' || name?.toLowerCase() === '/tasks') return runTaskCommand(args);
  if (name?.toLowerCase() === '/git') return runGitCommand(args);
  switch (name.toLowerCase()) {
    case '/help':
      appendTerminalMessage('system', [
        '╔═══════════════════════════════════════════════════════════════╗',
        '║ kudbEE Agent OS CLI — Command Reference                       ║',
        '╚═══════════════════════════════════════════════════════════════╝',
        '',
        '📋 Core Commands:',
        '  /help              Show this help message',
        '  /clear             Clear the terminal',
        '  /status            Check the Agent OS API health',
        '  /tokens [QUERY]    Think Tokens (lessons): open the view, optionally searching; /lessons and /token TT-ID are the same',
        '  /session           Show current session info',
        '  /refresh           Refresh stats, runs, memory, files',
        '  /models            List available AI models',
        '  /model NAME         Switch to a model',
        '  /agent [NAME]       Switch agent profile (or clear for default)',
        '  /notes [LAYER]     List recent notes (session|task|org|verified)',
        '  /remote CMD        Run an allow-listed read-only command on the UpCloud worker (governed)',
        '  /specialists INTENT Execute Director-selected specialists in independent workspaces',
        '',
        '🔌 Plugins & Integration:',
        '  /plugins           List installed plugins',
        '  /plugin NAME JSON  Execute a plugin with JSON input',
        '',
        '⛓  Algorand (read-only, public nodes):',
        '  /algo status [mainnet]          Network status',
        '  /algo account ADDR | txs ADDR   Balance & holdings | recent transactions',
        '  /algo asset ID | app ID | tx TXID',
        '',
        '🧠 Memory (Markdown files + vector index):',
        '  /memory [QUERY]    Recent memories, or vector search',
        '  /remember TITLE - TEXT   Save an org note (no args opens the form)',
        '  /promote org/ID    Promote an org note to verified knowledge',
        '',
        '📊 Agent Tracking:',
        '  /metrics           Runs, success rate, latency, tokens, cost, per-tool stats',
        '  /runs              Recent runs (saved on the server)',
        '  /run ID            Open the step-by-step timeline of a run',
        '  /capacity          Running agents, approvals, CPU and memory',
        '  /logs [LIMIT]      Show audit logs (default: 10)',
        '  /export            Export current session data',
        '',
        '',
        '🗂  Tasks & Git:',
        '  /task add "title" [priority=high] [assignee=name] [due=YYYY-MM-DD] [tags=a,b]',
        '  /task list [status=open] [priority=high] [q=keyword]',
        '  /task show|start|done ID · /task block ID reason',
        '  /task priority|assign|due|tag ID value · /task note ID text',
        '  /git clone HTTPS_URL · /git status|log|diff|branch PATH',
        '',
        '⚙️  Configuration:',
        '  /theme dark|light  Change theme',
        '  /theme toggle      Toggle dark/light theme',
        '  /config            Show current configuration',
        '  /shortcuts         Show keyboard shortcuts',
        '',
        '⚖️  Approvals: the agent asks before overwriting a file or',
        '   contacting a new domain. Approve/Deny in the popup (auto-deny 120s).',
        '',
        '💡 Examples:',
        '  /runs                           List recent runs',
        '  /logs 20                        Show last 20 audit logs',
        '  /export                         Export session as JSON',
      ].join('\n'));
      Enterprise.auditLog.log('cli', 'Help command executed', 'info');
      return true;

    case '/plugins':
      Enterprise.capacity.update({ activeAgents: Math.min(10, state.plugins.length) });
      appendTerminalMessage('system', state.plugins.length
        ? ['📦 Installed Plugins:', ...state.plugins.map(p => `  ${p.name} [${p.permission}] — ${p.description}`)].join('\n')
        : '📦 No plugins are registered.');
      Enterprise.auditLog.log('cli', 'Plugins listed', 'info');
      return true;

    case '/specialists': {
      const intent = args.join(' ').trim();
      if (!intent) {
        appendTerminalMessage('system', 'Usage: /specialists INTENT');
        return true;
      }
      if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
        appendTerminalMessage('error', 'Not connected to the kudbEE backend.');
        return true;
      }
      appendTerminalMessage('user', `Specialists: ${intent}`);
      setStatus('running', 'Running specialists');
      state.ws.send(JSON.stringify({ type: 'run_specialists', intent }));
      return true;
    }

    case '/models':
      await loadModels();
      Enterprise.auditLog.log('cli', 'Models refreshed', 'info');
      appendTerminalMessage('system', state.models.length
        ? ['🤖 Available Models:', ...state.models.map(m => `  ${m.name} [${m.provider || 'ollama'}]${m.agent ? ' — tool-using worker agent' : ''}`)].join('\n')
        : '🤖 No models found. Start Ollama and pull a model.');
      return true;

    // Think Tokens are the lessons the agent learned: the same store and view as `kudbee tokens ...`.
    case '/tokens':
    case '/token':
    case '/lessons':
      if (!window.thinkTokenDashboard) { appendTerminalMessage('error', 'The Think Tokens view is not loaded.'); break; }
      window.thinkTokenDashboard.openWithQuery(args.join(' '));
      appendTerminalMessage('system', `Opened the Think Tokens view${args.length ? ` for "${args.join(' ')}"` : ''}.`);
      break;

    case '/status': {
      try {
        const response = await fetch('/api/health', { cache: 'no-store' });
        const data = await response.json();
        Enterprise.auditLog.log('cli', 'Status check', 'info');
        appendTerminalMessage('system', `✅ System Status:\n${JSON.stringify(data, null, 2)}`);
      } catch (error) {
        Enterprise.auditLog.log('cli', 'Status check failed', 'error');
        appendTerminalMessage('error', `Status check failed: ${error.message}`);
      }
      return true;
    }

    case '/metrics': {
      await refreshStats();
      const m = state.stats;
      if (!m) {
        appendTerminalMessage('error', 'Stats unavailable — is the backend running?');
        return true;
      }
      const tools = Object.entries(m.tools).map(([name, t]) => `  ${name.padEnd(12)} ${String(t.calls).padStart(4)} calls · ${t.success_rate}% ok · ${formatMs(t.avg_ms)} avg${t.denied ? ` · ${t.denied} denied` : ''}`);
      appendTerminalMessage('system', [
        '📊 Agent Metrics (server):',
        `  Runs: ${m.runs_today} today · ${m.runs_total} total · ${m.running} running`,
        `  Success rate: ${m.success_rate === null ? '—' : `${m.success_rate}%`} · failures: ${JSON.stringify(m.failures)}`,
        `  Duration p50/p95: ${formatMs(m.p50_ms)} / ${formatMs(m.p95_ms)} · avg ${m.avg_steps} steps`,
        `  Tokens today: ${m.tokens_today.toLocaleString()} · cost today ${formatUsd(m.cost_today_usd)} · all-time ${formatUsd(m.cost_total_usd)}${m.budget_usd ? ` · budget ${formatUsd(m.budget_usd)}` : ''}`,
        '',
        '🔧 Tools:',
        ...(tools.length ? tools : ['  (no tool calls yet)']),
      ].join('\n'));
      Enterprise.auditLog.log('cli', 'Metrics displayed', 'info');
      return true;
    }

    case '/runs':
    case '/sessions': {
      await refreshRuns();
      appendTerminalMessage('system', state.runs.length
        ? ['🕑 Recent runs (click one in Run History, or /run ID):', ...state.runs.slice(0, 15).map(r =>
          `  ${r.id.slice(0, 8)}  ${r.status.padEnd(9)} ${formatUsd(r.cost_usd).padStart(8)}  ${r.goal.slice(0, 60)}`)].join('\n')
        : '🕑 No runs yet.');
      return true;
    }

    case '/run': {
      const prefix = (args[0] || '').toLowerCase();
      await refreshRuns();
      const match = state.runs.find(r => r.id.startsWith(prefix));
      if (!prefix || !match) appendTerminalMessage('system', 'Usage: /run ID (first 8 characters from /runs)');
      else openRun(match.id);
      return true;
    }

    case '/memory': {
      const query = args.join(' ').trim();
      const params = new URLSearchParams({ limit: '10' });
      if (query) params.set('q', query);
      const memRes = await fetch(`/api/memory?${params}`, { cache: 'no-store' });
      if (!memRes.ok) throw new Error(`memory search failed (HTTP ${memRes.status})`);
      const { items, backend } = await memRes.json();
      appendTerminalMessage('system', items.length
        ? [`🧠 ${query ? `Memory search "${query}" (${backend})` : 'Recent memories'}:`, ...items.map(item =>
          `  [${item.layer}] ${item.title}${item.score !== undefined ? ` · ${Number(item.score).toFixed(2)}` : ''}\n      ${item.id}`)].join('\n')
        : `🧠 No memories${query ? ` match "${query}"` : ' yet'}.`);
      return true;
    }

    case '/algo': {
      const [action = 'status', target, maybeNetwork] = args;
      const network = [target, maybeNetwork].find(value => value === 'mainnet' || value === 'testnet') || 'testnet';
      const aliases = { app: 'application', tx: 'transaction', txs: 'account_transactions', history: 'account_transactions' };
      const resolved = aliases[action] || action;
      const params = new URLSearchParams({ action: resolved, network });
      if (target && target !== network) {
        if (['account', 'account_transactions'].includes(resolved)) params.set('address', target);
        else if (resolved === 'transaction') params.set('txid', target);
        else params.set('id', target);
      }
      const response = await fetch(`/api/algorand?${params}`, { cache: 'no-store' });
      const result = await response.json();
      appendTerminalMessage(response.ok ? 'system' : 'error', response.ok
        ? `⛓ Algorand ${resolved} (${network}):\n${JSON.stringify(result, null, 2)}`
        : `Algorand lookup failed: ${result.error}\nUsage: /algo status|account ADDR|asset ID|app ID|tx TXID|txs ADDR [mainnet]`);
      return true;
    }

    case '/remember': {
      const text = args.join(' ').trim();
      if (!text) {
        openMemoryForm();
        return true;
      }
      const [title, ...rest] = text.split(/\s+[-—:]\s+/);
      try {
        await saveMemory({ layer: 'org', title: title.slice(0, 120), content: rest.join(' - ') || text, tags: [] });
      } catch (error) {
        appendTerminalMessage('error', `Could not save memory: ${error.message}`);
      }
      return true;
    }

    case '/promote': {
      if (!args[0]) appendTerminalMessage('system', 'Usage: /promote org/<memory-id>  (see /memory)');
      else await promoteMemory(args[0].startsWith('org/') ? args[0] : `org/${args[0]}`);
      return true;
    }

    case '/capacity': {
      await refreshStats();
      const c = state.stats?.capacity;
      if (!c) {
        appendTerminalMessage('error', 'Capacity unavailable — is the backend running?');
        return true;
      }
      appendTerminalMessage('system', [
        '⚙️  Capacity (server):',
        `  Agents running: ${c.running_agents} of ${c.connected_sessions} connected session(s)`,
        `  Pending approvals: ${c.pending_approvals}`,
        `  Server CPU: ${c.server_cpu_pct}% · RSS ${c.server_rss_mb} MB`,
        `  System memory: ${c.system_mem_used_pct}% of ${c.system_mem_total_gb} GB · load ${c.load_avg.join(' / ')} · ${c.cores} cores`,
      ].join('\n'));
      Enterprise.auditLog.log('cli', 'Capacity displayed', 'info');
      return true;
    }

    case '/logs': {
      const limit = parseInt(args[0]) || 10;
      const logs = Enterprise.auditLog.getRecent(limit);
      const msg = logs.length
        ? ['🔐 Recent Audit Logs:', ...logs.map(l => `  [${new Date(l.timestamp).toLocaleTimeString()}] ${l.action} (${l.severity}) — ${l.details}`)].join('\n')
        : '🔐 No audit logs.';
      appendTerminalMessage('system', msg);
      return true;
    }

    case '/export': {
      Enterprise.export.exportSession();
      appendTerminalMessage('system', '✅ Session exported as JSON (check downloads)');
      Enterprise.auditLog.log('cli', 'Session exported', 'info');
      return true;
    }

    case '/theme': {
      const theme = args[0]?.toLowerCase();
      if (theme === 'toggle') {
        Enterprise.theme.toggle();
        appendTerminalMessage('system', `🎨 Theme toggled to: ${Enterprise.theme.current}`);
      } else if (theme === 'dark' || theme === 'light') {
        Enterprise.theme.set(theme);
        appendTerminalMessage('system', `🎨 Theme changed to: ${theme}`);
      } else {
        appendTerminalMessage('system', `Current theme: ${Enterprise.theme.current}. Usage: /theme dark|light|toggle`);
      }
      Enterprise.auditLog.log('cli', `Theme: ${Enterprise.theme.current}`, 'info');
      return true;
    }

    case '/config': {
      const config = {
        model: state.config.model,
        provider: state.config.provider,
        theme: Enterprise.theme.current,
        sessionId: state.sessionId,
        wsConnected: state.ws?.readyState === WebSocket.OPEN,
      };
      appendTerminalMessage('system', `⚙️  Configuration:\n${JSON.stringify(config, null, 2)}`);
      Enterprise.auditLog.log('cli', 'Config displayed', 'info');
      return true;
    }

    case '/shortcuts': {
      appendTerminalMessage('system', [
        '⌨️  Keyboard Shortcuts:',
        '  Ctrl+Shift+M       Toggle metrics display',
        '  Ctrl+Shift+C       Show capacity status',
        '  Ctrl+Shift+L       Show recent logs',
        '  Ctrl+Shift+E       Export session',
        '  Ctrl+K             Open command palette',
        '  Alt+D              Toggle dark theme',
      ].join('\n'));
      Enterprise.auditLog.log('cli', 'Shortcuts displayed', 'info');
      return true;
    }

    case '/clear':
      clearTerminal();
      Enterprise.auditLog.log('cli', 'Terminal cleared', 'info');
      return true;

    case '/skills': {
      if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
        appendTerminalMessage('error', 'Connect to the Agent OS backend before browsing MCP skills.');
        return true;
      }
      state.ws.send(JSON.stringify({ type: 'list_mcp_skills' }));
      appendTerminalMessage('system', 'Fetching MCP skill registry...');
      Enterprise.auditLog.log('cli', 'MCP skills requested', 'info');
      return true;
    }

    case '/skill': {
      if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
        appendTerminalMessage('error', 'Connect to the Agent OS backend before searching MCP skills.');
        return true;
      }
      const skillQuery = args.join(' ').trim();
      state.ws.send(JSON.stringify({
        type: 'search_mcp_skills',
        query: skillQuery
      }));
      if (skillQuery) {
        appendTerminalMessage('system', `Searching MCP skills for: "${skillQuery}"...`);
      } else {
        appendTerminalMessage('system', 'Use: /skill SEARCH_TERM  to find MCP skills');
      }
      Enterprise.auditLog.log('cli', `MCP skill search: ${skillQuery || '(all)'}`, 'info');
      return true;
    }

    case '/plugin': {
      if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
        appendTerminalMessage('error', 'Connect to the Agent OS backend before running a plugin.');
        return true;
      }
      const pluginName = args.shift();
      if (!pluginName || !args.length) {
        appendTerminalMessage('system', 'Usage: /plugin NAME JSON');
        return true;
      }
      try {
        state.ws.send(JSON.stringify({
          type: 'plugin_execute',
          plugin: pluginName,
          input: JSON.parse(args.join(' ')),
        }));
        appendTerminalMessage('system', `Running plugin: ${pluginName}`);
        Enterprise.auditLog.log('cli', `Plugin executed: ${pluginName}`, 'info');
      } catch {
        appendTerminalMessage('error', 'Plugin input must be valid JSON.');
        Enterprise.auditLog.log('cli', `Plugin failed: ${pluginName}`, 'error');
      }
      return true;
    }

    case '/model': {
      const name = args.join(' ').trim();
      if (!name) {
        const list = state.models.map(m => `  ${m.name} ${m.agent ? '— Worker Agent (Inception)' : `[${m.provider || 'ollama'}]`}`).join('\n');
        appendTerminalMessage('system', `Current model: ${state.config.model || '(none)'}\nAvailable models:\n${list}\nUsage: /model NAME`);
        return true;
      }
      const match = state.models.find(m => m.name.toLowerCase() === name.toLowerCase());
      if (!match) {
        appendTerminalMessage('error', `Unknown model "${name}". Available: ${state.models.map(m => m.name).join(', ')}`);
        return true;
      }
      const select = document.getElementById('model-select');
      if (select) select.value = match.name;
      state.config.model = match.name;
      state.ws?.send(JSON.stringify({ type: 'update_config', config: { model: match.name } }));
      const icon = match.agent ? '⚡' : '💻';
      appendTerminalMessage('system', `${icon} Model → ${match.name}`);
      Enterprise.auditLog.log('cli', `Model switched to ${match.name}`, 'info');
      return true;
    }

    case '/agent': {
      const name = args.join(' ').trim();
      if (!name) {
        const select = document.getElementById('agent-select');
        if (!select) {
          appendTerminalMessage('error', 'Agent selector not available');
          return true;
        }
        const opts = Array.from(select.options).filter(o => o.value).map(o => `  ${o.value} — ${o.textContent.trim()}`);
        appendTerminalMessage('system', `Current agent: ${select.value || '(default worker)'}\nAvailable agents:\n${opts.join('\n') || '  (none)'}\nUsage: /agent NAME  (or /agent to clear)`);
        return true;
      }
      const select = document.getElementById('agent-select');
      if (!select) {
        appendTerminalMessage('error', 'Agent selector not available');
        return true;
      }
      const lower = name.toLowerCase();
      if (lower === 'default' || lower === '' || lower === 'worker') {
        select.value = '';
        appendTerminalMessage('system', '🤖 Agent → default worker (full tool access)');
        return true;
      }
      const match = Array.from(select.options).find(o => o.value && o.value.toLowerCase() === lower);
      if (!match) {
        appendTerminalMessage('error', `Unknown agent "${name}". See /agent for list.`);
        return true;
      }
      select.value = match.value;
      appendTerminalMessage('system', `🤖 Agent → ${match.textContent.trim()}`);
      Enterprise.auditLog.log('cli', `Agent switched to ${match.value}`, 'info');
      return true;
    }

    case '/select':
      document.getElementById('model-select')?.focus();
      appendTerminalMessage('system', '📋 Use the Model dropdown in the header to select a model.');
      return true;

    case '/notes': {
      const layer = args[0]?.toLowerCase();
      const valid = ['', 'session', 'task', 'org', 'verified'];
      const params = new URLSearchParams({ limit: '20' });
      if (layer && valid.includes(layer)) params.set('layer', layer);
      try {
        const notesRes = await fetch(`/api/memory?${params}`, { cache: 'no-store' });
        if (!notesRes.ok) throw new Error(`notes request failed (HTTP ${notesRes.status})`);
        const { items, backend } = await notesRes.json();
        if (!items.length) {
          appendTerminalMessage('system', `📝 No notes${layer ? ` in ${layer}` : ''} yet.`);
          return true;
        }
        const rows = items.map(item => `  [${item.layer}] ${item.title} · ${item.id}${item.tags?.length ? ` #${item.tags.join(' #')}` : ''}`);
        appendTerminalMessage('system', `📝 ${layer ? `Notes in ${layer}` : 'Recent notes'} (${backend}):\n${rows.join('\n')}`);
      } catch (error) {
        appendTerminalMessage('error', `Could not load notes: ${error.message}`);
      }
      return true;
    }

    case '/session':
      appendTerminalMessage('system', [
        `🐝 kudbEE Agent OS — Session`,
        `  Session ID: ${state.sessionId || '(disconnected)'}`,
        `  Model: ${state.config.model || '(not selected)'}`,
        `  Provider: ${state.config.provider || 'inception/ollama'}`,
        `  Plugins: ${state.plugins.length}`,
        `  WebSocket: ${state.ws?.readyState === WebSocket.OPEN ? 'Connected' : 'Disconnected'}`,
        '',
        `  Use /model NAME to switch · /agent NAME to select an agent profile`,
      ].join('\n'));
      return true;

    case '/remote': {
      const command = args.join(' ').trim();
      const headers = { 'Content-Type': 'application/json', 'X-Kudbee-Client': 'dashboard' };
      if (!command) {
        appendTerminalMessage('system', 'Usage: /remote hostname | uname -a | uptime | whoami | df -h / | free -m');
        return true;
      }
      try {
        const submit = await fetch('/api/governed/run', { method: 'POST', headers, body: JSON.stringify({ command }) });
        const job = await submit.json();
        if (!submit.ok) {
          appendTerminalMessage('system', `✗ /remote rejected (${submit.status}): ${job.error || 'error'}`);
          return true;
        }
        appendTerminalMessage('system', `⏳ governed job ${job.engine_id} → ${job.execution_substrate} (receipt ${job.receipt_id})`);
        for (let i = 0; i < 40; i += 1) {
          const pollRes = await fetch(`/api/governed/run/${job.engine_id}`, { headers, cache: 'no-store' });
          if (!pollRes.ok) throw new Error(`governed job poll failed (HTTP ${pollRes.status})`);
          const st = await pollRes.json();
          if (st?.poll?.terminal) {
            const proof = st.result?.execution_proof || {};
            appendTerminalMessage('system', [
              `${st.status === 'completed' ? '✓' : '✗'} ${st.status} · provider ${proof.provider || '?'} · exit ${proof.exit_code ?? '?'} · verified ${proof.verified ?? '?'}`,
              `  checkpoint ${proof.checkpoint_id || '-'} · artifact ${String(proof.artifact_hash || '').slice(0, 12)}…`,
            ].join('\n'));
            return true;
          }
          await new Promise(r => setTimeout(r, 500));
        }
        appendTerminalMessage('system', `… job ${job.engine_id} still running; check its receipt ${job.receipt_id}`);
      } catch (err) {
        appendTerminalMessage('system', `✗ /remote failed: ${err instanceof Error ? err.message : String(err)}`);
      }
      return true;
    }

    case '/refresh':
      await Promise.all([refreshStats(), refreshRuns(), refreshMemory(), refreshFiles()]);
      loadModels();
      appendTerminalMessage('system', '🔄 Refreshed stats, runs, memory, files, and models.');
      return true;

    default:
      return false;
  }
}

function tokenizeTerminalCommand(command) {
  return (command.match(/(?:[^\s"']+|"[^"]*"|'[^']*')+/g) || [])
    .map(token => token.replace(/^("|')|("|')$/g, ''));
}

function runTaskCommand(args) {
  const rawAction = String(args.shift() || 'help').toLowerCase();
  const action = ({ create: 'add', complete: 'done', tags: 'tag' })[rawAction] || rawAction;
  const positional = [];
  const options = {};
  args.forEach(argument => {
    const option = argument.match(/^([a-z]+)=(.*)$/i);
    if (option) options[option[1].toLowerCase()] = option[2];
    else positional.push(argument);
  });
  const usage = 'Use /task add "title" [priority=] [assignee=] [due=] [tags=], list [status=] [priority=] [q=], show ID, start ID, done ID, block ID reason, priority ID value, assign ID name, due ID YYYY-MM-DD, tag ID a,b, note ID text';
  if (action === 'help') {
    appendTerminalMessage('system', usage);
    return true;
  }
  if (action === 'add') {
    const title = positional.join(' ').trim();
    if (!title) appendTerminalMessage('error', 'Usage: /task add "title" [priority=high] [assignee=name] [due=YYYY-MM-DD] [tags=a,b]');
    else sendTaskAction('create', { title, priority: options.priority, assignee: options.assignee, dueDate: options.due, tags: options.tags });
    return true;
  }
  if (action === 'list') {
    sendTaskAction('list', { status: options.status, priority: options.priority, query: options.q || positional.join(' ') });
    return true;
  }
  if (action === 'show') {
    if (!positional[0]) appendTerminalMessage('error', 'Usage: /task show ID');
    else sendTaskAction('show', { id: positional[0] });
    return true;
  }
  if (['start', 'done'].includes(action)) {
    if (!positional[0]) appendTerminalMessage('error', `Usage: /task ${action} ID`);
    else sendTaskAction(action, { id: positional[0] });
    return true;
  }
  if (['block', 'priority', 'assign', 'due', 'tag', 'note'].includes(action)) {
    const id = positional.shift();
    const value = positional.join(' ').trim();
    if (!id || !value) appendTerminalMessage('error', `Usage: /task ${action} ID value`);
    else sendTaskAction(action, action === 'block' ? { id, reason: value } : { id, value });
    return true;
  }
  appendTerminalMessage('error', usage);
  return true;
}

function runGitCommand(args) {
  const action = String(args.shift() || 'help').toLowerCase();
  if (action === 'help') {
    appendTerminalMessage('system', 'Git commands: /git clone HTTPS_URL · /git status|log|diff|branch repositories/NAME');
    return true;
  }
  if (action === 'clone') {
    if (!args[0]) appendTerminalMessage('error', 'Usage: /git clone https://github.com/org/repo.git');
    else sendGitAction('clone', { url: args[0] });
    return true;
  }
  if (['status', 'log', 'diff', 'branch'].includes(action)) {
    if (!args[0]) appendTerminalMessage('error', `Usage: /git ${action} repositories/NAME`);
    else sendGitAction(action, { path: args[0] });
    return true;
  }
  appendTerminalMessage('error', 'Allowed Git commands: clone, status, log, diff, branch');
  return true;
}

async function uploadTaskImage(file, taskId) {
  if (!file || !state.sessionId) return;
  const form = new FormData();
  form.append('image', file);
  try {
    const response = await fetch(`${sessionApi()}/tasks/${encodeURIComponent(taskId)}/attachments`, { method: 'POST', body: form });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || response.statusText);
    appendTerminalMessage('system', `Attached ${file.name} to task ${taskId.slice(0, 8)}.`);
  } catch (error) {
    appendTerminalMessage('error', `Image attachment failed: ${error.message}`);
  }
}

async function cloneRepository() {
  const input = document.getElementById('git-url-input');
  const url = input.value.trim();
  if (!url) {
    input.focus();
    return;
  }
  sendGitAction('clone', { url });
}

function renderGitRepositories(files) {
  const container = document.getElementById('git-repository-list');
  const repositories = Array.from(new Set(files
    .map(file => file.path.split('/'))
    .filter(parts => parts[0] === 'repositories' && parts[1])
    .map(parts => parts[1])));
  if (!repositories.length) {
    container.innerHTML = '<div class="file-tree-empty">No Git repositories connected</div>';
    return;
  }
  container.innerHTML = repositories.map(repository => `
    <div class="git-repository-item">
      <strong>${escapeHtml(repository)}</strong>
      <div>${['status', 'log', 'diff', 'branch'].map(action => `<button type="button" data-git-action="${action}" data-git-path="repositories/${escapeHtml(repository)}">${action}</button>`).join('')}</div>
    </div>
  `).join('');
}

async function refreshConnectionMonitor() {
  const container = document.getElementById('connection-monitor');
  const updated = document.getElementById('monitor-updated');
  try {
    const response = await fetch('/api/monitor', { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const snapshot = await response.json();
    container.innerHTML = snapshot.checks.map(check => `
      <div class="plugin-item">
        <span class="plugin-icon">${check.status === 'ok' ? '✓' : '!'}</span>
        <div class="plugin-info">
          <div class="plugin-name">${escapeHtml(check.name)}</div>
          <div class="plugin-desc">${escapeHtml(check.error || `${check.latency_ms}ms`)}</div>
        </div>
        <span class="plugin-badge ${escapeHtml(check.status)}">${escapeHtml(check.status)}</span>
      </div>
    `).join('');
    updated.textContent = `Agent ${snapshot.agent.id.slice(0, 8)}`;
    updated.title = `${snapshot.agent.name}: ${snapshot.agent.checks} checks; last check ${snapshot.agent.last_check}`;
  } catch (error) {
    container.innerHTML = `<div class="empty-state">Monitor unavailable: ${escapeHtml(error.message)}</div>`;
    updated.textContent = 'Offline';
  }
}

async function testMiddleware() {
  try {
    const query = state.sessionId ? `?session_id=${encodeURIComponent(state.sessionId)}` : '';
    const response = await fetch(`/api/middleware/test${query}`, { cache: 'no-store' });
    const result = await response.json();
    if (!response.ok || !Array.isArray(result.checks)) throw new Error(result.error || `HTTP ${response.status}`);
    appendTerminalMessage(result.passed ? 'system' : 'error', [
      `Middleware test: ${result.passed ? 'PASSED' : 'FAILED'}`,
      ...result.checks.map(check => `${check.status === 'ok' ? '✓' : '✗'} ${check.name}: ${check.error || `${check.http_status} (${check.latency_ms}ms)`}`),
    ].join('\n'));
    await refreshConnectionMonitor();
  } catch (error) {
    appendTerminalMessage('error', `Middleware test failed: ${error.message}`);
  }
}

async function refreshSystemHealth() {
  const container = document.getElementById('system-health');
  const badge = document.getElementById('system-health-status');
  try {
    const [healthResponse, modelsResponse] = await Promise.all([
      fetch('/api/health', { cache: 'no-store' }),
      fetch('/api/models', { cache: 'no-store' }),
    ]);
    if (!healthResponse.ok) throw new Error(`Health HTTP ${healthResponse.status}`);
    const health = await healthResponse.json();
    const models = modelsResponse.ok ? await modelsResponse.json() : [];
    const connected = state.ws?.readyState === WebSocket.OPEN;
    const rows = [
      ['Runtime', health.ready ? 'Running' : 'Degraded'],
      ['WebSocket', connected ? 'Connected' : 'Disconnected'],
      ['Session', state.sessionId ? state.sessionId.slice(0, 8) : 'None'],
      ['Models', `${models.length} available`],
      ['Plugins', String(health.plugins)],
      ['Uptime', `${health.uptime_seconds}s`],
      ['Memory', `${health.memory_mb} MB`],
    ];
    container.innerHTML = rows.map(([label, value]) => `
      <div class="health-row"><span>${label}</span><strong>${escapeHtml(value)}</strong></div>
    `).join('');
    badge.textContent = health.ready && connected ? 'Healthy' : 'Degraded';
    badge.className = `badge ${health.ready && connected ? 'health-ok' : 'health-warn'}`;
  } catch (error) {
    container.innerHTML = `<div class="empty-state">Health unavailable: ${escapeHtml(error.message)}</div>`;
    badge.textContent = 'Offline';
    badge.className = 'badge health-error';
  }
}

// ─── Agent tracking: stats, run history, timeline, approvals ───
function formatUsd(value) {
  const v = Number(value) || 0;
  return v >= 0.01 ? `$${v.toFixed(2)}` : `$${v.toFixed(4)}`;
}

function formatMs(ms) {
  if (!ms) return '0s';
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;
}

function setMeter(id, pct) {
  const el = document.getElementById(id);
  if (!el) return;
  const clamped = Math.max(0, Math.min(100, pct || 0));
  el.style.width = `${clamped}%`;
  el.classList.toggle('danger', clamped >= 90);
}

async function refreshStats() {
  try {
    const response = await fetch('/api/stats', { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const s = await response.json();
    state.stats = s;
    document.getElementById('metric-runs').textContent = s.runs_today;
    document.getElementById('metric-suc').textContent = s.success_rate === null ? '—' : `${s.success_rate}%`;
    document.getElementById('metric-lat').textContent = s.runs_total ? `${formatMs(s.p50_ms)} / ${formatMs(s.p95_ms)}` : '—';
    document.getElementById('metric-cost').textContent = formatUsd(s.cost_today_usd);
    document.getElementById('metric-tokens').textContent = `${s.tokens_today.toLocaleString()} tokens today · ${formatUsd(s.cost_total_usd)} all-time`;

    const budgetRow = document.getElementById('budget-row');
    budgetRow.hidden = !s.budget_usd;
    if (s.budget_usd) {
      const pct = (s.cost_today_usd / s.budget_usd) * 100;
      setMeter('budget-bar', pct);
      document.getElementById('budget-text').textContent = `Daily budget ${formatUsd(s.cost_today_usd)} / ${formatUsd(s.budget_usd)} (${pct.toFixed(0)}%)`;
    }

    const max = Math.max(1, ...s.hourly.map(h => h.runs));
    document.getElementById('sparkline').innerHTML = s.hourly.map((h, i) => {
      const hoursAgo = 23 - i;
      const title = escapeHtml(`${hoursAgo === 0 ? 'This hour' : `${hoursAgo}h ago`}: ${h.runs} run(s), ${h.failed} failed, ${formatUsd(h.cost_usd)}`);
      if (!h.runs) return `<div class="bar empty" title="${title}"></div>`;
      const fail = h.failed ? ` has-fail" style="height:${(h.runs / max) * 100}%;--fail:${(h.failed / h.runs) * 100}%` : `" style="height:${(h.runs / max) * 100}%`;
      return `<div class="bar${fail}" title="${title}"></div>`;
    }).join('');

    document.getElementById('metric-failures').innerHTML = Object.entries(s.failures || {})
      .map(([kind, count]) => `<span title="Failure type">${escapeHtml(kind)} × ${escapeHtml(count)}</span>`).join('');

    // Independent try/catch: a token-stats hiccup shouldn't flip the whole
    // metrics panel to "Offline" for an unrelated endpoint.
    refreshTokenSavings();

    const c = s.capacity;
    document.getElementById('cap-agents-text').textContent = `${c.running_agents} running · ${c.queued_goals} queued · ${c.connected_sessions} session(s)`;
    setMeter('cap-agents', c.connected_sessions ? (c.running_agents / c.connected_sessions) * 100 : 0);
    document.getElementById('cap-cpu-text').textContent = `${c.server_cpu_pct}% · ${c.server_rss_mb} MB RSS`;
    setMeter('cap-cpu', c.server_cpu_pct);
    document.getElementById('cap-mem-text').textContent = `${c.system_mem_used_pct}% of ${c.system_mem_total_gb} GB`;
    setMeter('cap-mem', c.system_mem_used_pct);
    document.getElementById('cap-load-text').textContent = `${c.load_avg.join(' / ')} (${c.cores} cores)`;
    const approvalBadge = document.getElementById('approval-badge');
    approvalBadge.textContent = `${c.pending_approvals} approval${c.pending_approvals === 1 ? '' : 's'}`;
    approvalBadge.className = `badge ${c.pending_approvals ? 'health-warn' : ''}`;
    document.getElementById('metrics-badge').textContent = s.running ? `${s.running} running` : 'Live';
  } catch (error) {
    document.getElementById('metrics-badge').textContent = 'Offline';
  }
}

// Feature 5: "Tokens saved (est.)" KPI + sparkline, sourced from /api/stats/tokens
// (aggregates run_metadata.metrics.tokens_saved_est via the SQLite persistence layer).
async function refreshTokenSavings() {
  if (!state.sessionId) return;
  try {
    const response = await fetch(`/api/stats/tokens?sessionId=${encodeURIComponent(state.sessionId)}&limit=24`, { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const t = await response.json();

    document.getElementById('metric-tokens-saved').textContent = t.totalTokensSavedEst.toLocaleString();

    const detail = document.getElementById('metric-tokens-saved-detail');
    detail.textContent = t.totalRunsTracked
      ? `${t.totalRunsTracked} run(s) · avg ~${t.averageSavingsPerRun.toLocaleString()}/run`
      : 'no data yet';

    const bars = t.sparklineData || [];
    const max = Math.max(1, ...bars);
    document.getElementById('token-savings-sparkline').innerHTML = bars.length
      ? bars.map((saved) => {
          const title = saved > 0 ? escapeHtml(`est. ${saved.toLocaleString()} tokens saved`) : 'no local route (Mercury-2 used)';
          const cls = saved > 0 ? 'savings' : 'fallback';
          const height = saved > 0 ? (saved / max) * 100 : 8;
          return `<div class="bar ${cls}" style="height:${height}%" title="${title}"></div>`;
        }).join('')
      : '<div class="bar empty" title="no runs yet"></div>';
  } catch (error) {
    // Leave last-known values on screen; this KPI is best-effort and shouldn't
    // interrupt the rest of the metrics panel.
  }
}

let runsRefreshTimer = null;
function scheduleRunsRefresh() {
  if (runsRefreshTimer) return;
  runsRefreshTimer = setTimeout(() => {
    runsRefreshTimer = null;
    refreshRuns();
  }, 800);
}

async function refreshRuns() {
  try {
    const response = await fetch('/api/runs?limit=30', { cache: 'no-store' });
    if (!response.ok) return;
    const { runs } = await response.json();
    state.runs = runs;
    document.getElementById('run-count').textContent = runs.length;
    const container = document.getElementById('run-history');
    container.innerHTML = runs.length
      ? runs.map(run => `
        <button type="button" class="run-item" data-run="${escapeHtml(run.id)}" title="${escapeHtml(run.goal)}">
          <span class="run-dot ${escapeHtml(run.status)}"></span>
          <span class="goal">${escapeHtml(run.goal)}</span>
          <small>${formatUsd(run.cost_usd)} · ${run.status === 'running' ? 'live' : escapeHtml(formatMs(run.duration_ms))}</small>
        </button>`).join('')
      : '<div class="empty-state">No runs yet</div>';
  } catch {
    // Stats badge already reports the backend as offline.
  }
}

async function openRun(runId) {
  const response = await fetch(`/api/runs/${encodeURIComponent(runId)}`, { cache: 'no-store' });
  if (!response.ok) {
    appendTerminalMessage('error', `Run ${runId.slice(0, 8)} not found`);
    return;
  }
  const run = await response.json();
  state.openRunId = run.id;
  state.openRun = run;
  document.getElementById('run-modal-title').textContent = run.goal;
  const kpis = [
    ['Status', run.status],
    ['Model', run.model],
    ['Duration', run.status === 'running' ? `${((Date.now() - run.started_at) / 1000).toFixed(0)}s…` : formatMs(run.duration_ms)],
    ['Steps', run.current_step],
    ['Tool calls', run.tool_calls],
    ['Tokens', (run.prompt_tokens + run.completion_tokens).toLocaleString()],
    ['Cost', formatUsd(run.cost_usd)],
    ['Approvals', `${run.approvals.approved}✓ ${run.approvals.denied}✗`],
  ];
  const answer = run.result || run.error;
  document.getElementById('run-summary').innerHTML = kpis
    .map(([label, value]) => `<div class="kpi"><span>${escapeHtml(label)}</span><strong>${escapeHtml(String(value))}</strong></div>`).join('')
    + (run.files.length ? `<div class="run-answer">📁 Files: ${run.files.map(escapeHtml).join(', ')}</div>` : '')
    + (run.recalled?.length ? `<div class="run-answer">🧠 Recalled: ${run.recalled.map(escapeHtml).join(', ')}</div>` : '')
    + (answer ? `<div class="run-answer ${run.error ? 'error' : ''}">${escapeHtml(answer)}</div>` : '');

  document.getElementById('run-timeline').innerHTML = run.steps.length ? run.steps.map(step => {
    if (step.kind === 'model') {
      const calls = step.tool_calls.length ? `→ ${step.tool_calls.join(', ')}` : '→ final answer';
      return `<div class="tl-item model">
        <div class="tl-head"><span>🧠 Step ${Number(step.step) || 0} · ${escapeHtml(run.model)} ${escapeHtml(calls)}</span><small>${escapeHtml(formatMs(step.latency_ms))} · ${Number(step.prompt_tokens) || 0}+${Number(step.completion_tokens) || 0} tok · ${formatUsd(step.cost_usd)}</small></div>
        ${step.content ? `<div class="tl-body">${escapeHtml(step.content)}</div>` : ''}
      </div>`;
    }
    const cls = step.approval === 'denied' ? 'denied' : step.ok ? '' : 'fail';
    const tag = step.approval ? `<span class="tl-tag ${escapeHtml(step.approval)}">${escapeHtml(step.approval)}</span>` : '';
    return `<div class="tl-item tool ${cls}">
      <div class="tl-head"><span>${step.ok ? '✓' : '✗'} ${escapeHtml(step.name)}${tag}</span><small>${escapeHtml(formatMs(step.latency_ms))}</small></div>
      <div class="tl-body">${escapeHtml(JSON.stringify(step.args))}${step.approval_reason ? `\n⚖ ${escapeHtml(step.approval_reason)}` : ''}\n→ ${escapeHtml(step.error || step.output)}</div>
    </div>`;
  }).join('') : '<div class="empty-state">No steps recorded yet</div>';
  document.getElementById('run-modal').hidden = false;
}

function closeRunModal() {
  document.getElementById('run-modal').hidden = true;
  state.openRunId = null;
}

let approvalTicker = null;
function showNextApproval() {
  const modal = document.getElementById('approval-modal');
  const next = state.approvals[0];
  clearInterval(approvalTicker);
  if (!next) {
    modal.hidden = true;
    return;
  }
  document.getElementById('approval-title').textContent = `Agent wants to run ${next.tool}`;
  document.getElementById('approval-reason').textContent = `⚖ ${next.reason}`;
  document.getElementById('approval-args').textContent = JSON.stringify(next.args, null, 2);
  const tick = () => {
    const left = Math.max(0, Math.round((next.timeout_ms - (Date.now() - next.received_at)) / 1000));
    document.getElementById('approval-countdown').textContent = `auto-deny in ${left}s${state.approvals.length > 1 ? ` · ${state.approvals.length - 1} more` : ''}`;
  };
  tick();
  approvalTicker = setInterval(tick, 1000);
  modal.hidden = false;
  document.getElementById('approve-approval').focus();
}

function answerApproval(approved) {
  const next = state.approvals.shift();
  if (next && state.ws?.readyState === WebSocket.OPEN) {
    state.ws.send(JSON.stringify({ type: 'approval_response', id: next.id, approved }));
    appendTerminalMessage('system', `${approved ? '✓ Approved' : '✗ Denied'} ${next.tool}: ${next.reason}`);
    Enterprise.auditLog.log('approval', `${approved ? 'approved' : 'denied'} ${next.tool} — ${next.reason}`, approved ? 'info' : 'warning');
  }
  showNextApproval();
}

// ─── Memory layers ─────────────────────────────────────────────
let memoryRefreshTimer = null;
function scheduleMemoryRefresh() {
  clearTimeout(memoryRefreshTimer);
  memoryRefreshTimer = setTimeout(refreshMemory, 300);
}

let memoryRequestSeq = 0;
async function refreshMemory() {
  // Several refreshes can overlap (tab click, search, memory_changed); only the newest may render.
  const seq = ++memoryRequestSeq;
  try {
    const params = new URLSearchParams({ limit: '60' });
    if (state.memoryLayer) params.set('layer', state.memoryLayer);
    if (state.memoryQuery) params.set('q', state.memoryQuery);
    const [listResponse, statusResponse] = await Promise.all([
      fetch(`/api/memory?${params}`, { cache: 'no-store' }),
      fetch('/api/memory/status', { cache: 'no-store' }),
    ]);
    const { items, backend } = await listResponse.json();
    const status = await statusResponse.json();
    if (seq !== memoryRequestSeq) return;
    const counts = status.counts;
    document.getElementById('memory-count-all').textContent = counts.task + counts.org + counts.verified;
    ['verified', 'org', 'task'].forEach(layer => { document.getElementById(`memory-count-${layer}`).textContent = counts[layer]; });
    const badge = document.getElementById('memory-backend');
    const vector = status.vector;
    badge.textContent = vector.backend === 'upstash-sparse' ? (vector.ok ? 'Upstash vector' : 'Vector offline') : 'Local index';
    badge.className = `badge ${vector.backend === 'upstash-sparse' && !vector.ok ? 'health-warn' : ''}`;
    badge.title = vector.error || `${vector.backend} · ${vector.synced} synced · namespace ${status.namespace}`;
    const container = document.getElementById('memory-list');
    container.innerHTML = items.length
      ? items.map(item => `
        <button type="button" class="memory-item" data-memory-id="${escapeHtml(item.id)}" title="${escapeHtml(item.path)}">
          <strong><span class="memory-layer ${escapeHtml(item.layer)}">${escapeHtml(item.layer)}</span>${escapeHtml(item.title)}</strong>
          <small>${item.score !== undefined ? `score ${Number(item.score).toFixed(2)} · ` : ''}${escapeHtml(item.content)}</small>
        </button>`).join('')
      : `<div class="empty-state">${state.memoryQuery ? `No matches (${escapeHtml(backend)})` : 'No memories yet — finished runs are saved here automatically'}</div>`;
    // Real bridge for memory-graph.js: it already listens for this event but nothing ever
    // dispatched it, so the graph only ever showed whatever .memory-item elements existed at
    // page load and never updated again. Real ids/layers/tags, not synthesized ones.
    window.dispatchEvent(new CustomEvent('memory:updated', {
      detail: { memories: items.map((item) => ({ id: item.id, title: item.title, layer: item.layer, tags: item.tags || [] })) },
    }));
  } catch (error) {
    document.getElementById('memory-backend').textContent = 'Offline';
  }
}

function setMemoryModalMode(mode) {
  document.getElementById('memory-view').hidden = mode !== 'view';
  document.getElementById('memory-form').hidden = mode !== 'add';
  document.getElementById('save-memory').hidden = mode !== 'add';
  document.getElementById('delete-memory').hidden = mode !== 'view';
  document.getElementById('memory-modal').hidden = false;
}

async function openMemory(id) {
  const response = await fetch(`/api/memory/item?id=${encodeURIComponent(id)}`, { cache: 'no-store' });
  if (!response.ok) {
    appendTerminalMessage('error', `Memory not found: ${id}`);
    return;
  }
  const item = await response.json();
  state.openMemoryId = item.id;
  document.getElementById('memory-modal-layer').textContent = `${item.layer.toUpperCase()} MEMORY`;
  document.getElementById('memory-modal-title').textContent = item.title;
  document.getElementById('memory-modal-meta').innerHTML = [
    `id ${escapeHtml(item.id)}`,
    `source ${escapeHtml(item.source)}`,
    `updated ${escapeHtml(new Date(item.updated).toLocaleString())}`,
    item.tags.length ? `tags ${escapeHtml(item.tags.join(', '))}` : '',
    `file data/memory/${escapeHtml(item.path)}`,
  ].filter(Boolean).map(part => `<span>${part}</span>`).join('');
  document.getElementById('memory-modal-content').textContent = item.content;
  document.getElementById('promote-memory').hidden = item.layer !== 'org';
  setMemoryModalMode('view');
}

function openMemoryForm(prefill = {}) {
  state.openMemoryId = null;
  document.getElementById('memory-modal-layer').textContent = 'NEW MEMORY';
  document.getElementById('memory-modal-title').textContent = 'Add a note to memory';
  document.getElementById('memory-modal-meta').innerHTML = '<span>Saved as a Markdown file and indexed for vector recall. The agent sees it on related goals.</span>';
  document.getElementById('memory-form-layer').value = prefill.layer || 'org';
  document.getElementById('memory-form-title').value = prefill.title || '';
  document.getElementById('memory-form-tags').value = prefill.tags || '';
  document.getElementById('memory-form-content').value = prefill.content || '';
  document.getElementById('promote-memory').hidden = true;
  setMemoryModalMode('add');
  document.getElementById('memory-form-title').focus();
}

function closeMemoryModal() {
  document.getElementById('memory-modal').hidden = true;
  state.openMemoryId = null;
}

async function saveMemory(body) {
  const response = await fetch('/api/memory', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || response.statusText);
  appendTerminalMessage('system', `🧠 Saved ${result.layer} memory: ${result.title} (${result.path})`);
  Enterprise.auditLog.log('memory', `saved ${result.id}`, 'info');
  await refreshMemory();
  return result;
}

async function promoteMemory(id) {
  const response = await fetch('/api/memory/promote', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id }),
  });
  const result = await response.json();
  if (!response.ok) {
    appendTerminalMessage('error', `Promote failed: ${result.error}`);
    return null;
  }
  appendTerminalMessage('system', `✓ Promoted to verified knowledge: ${result.title}`);
  Enterprise.auditLog.log('memory', `promoted ${id} → ${result.id}`, 'info');
  await refreshMemory();
  return result;
}

async function deleteMemory(id) {
  const response = await fetch(`/api/memory/item?id=${encodeURIComponent(id)}`, { method: 'DELETE' });
  if (!response.ok) {
    appendTerminalMessage('error', `Delete failed: ${(await response.json()).error}`);
    return;
  }
  appendTerminalMessage('system', `🗑 Deleted memory ${id}`);
  Enterprise.auditLog.log('memory', `deleted ${id}`, 'warning');
  await refreshMemory();
}

// ─── Models ────────────────────────────────────────────────────
async function loadModels() {
  if (!state.ws || state.ws.readyState !== WebSocket.OPEN) return;
  state.ws.send(JSON.stringify({ type: 'list_models' }));
}

async function loadAgents() {
  try {
    const res = await fetch('/api/agents', { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const { agents } = await res.json();
    renderAgents(agents);
  } catch (error) {
    console.error('Failed to load agents:', error);
  }
}

function renderModels() {
  const select = document.getElementById('model-select');
  // The list is re-sent every 10s; rebuilding identical options closes the dropdown while it is open.
  const key = JSON.stringify(state.models.map(m => [m.name, m.provider, m.size]));
  if (select.dataset.modelsKey === key) return;
  select.dataset.modelsKey = key;
  if (!state.models.length) {
    select.innerHTML = '<option value="">No models (set INCEPTION_API_KEY or start Ollama)</option>';
    return;
  }
  const previous = select.value || state.config.model;
  select.innerHTML = state.models.map(m => {
    const label = m.provider === 'inception'
      ? `⚡ ${m.name} — Worker Agent (Inception)`
      : `${m.name} — local (${((m.size || 0) / 1e9).toFixed(1)}GB)`;
    return `<option value="${escapeHtml(m.name)}">${escapeHtml(label)}</option>`;
  }).join('');
  if (state.models.some(m => m.name === previous)) select.value = previous;
}

function renderAgents(agents) {
  const select = document.getElementById('agent-select');
  const opts = [{ id: '', name: '(default worker)', description: 'full tool access' }];
  opts.push(...agents);
  const previous = select.value;
  select.innerHTML = opts.map(a => {
    const label = a.id ? `${a.name} — ${a.description}` : a.name;
    return `<option value="${escapeHtml(a.id)}">${escapeHtml(label)}</option>`;
  }).join('');
  if (opts.some(a => a.id === previous)) select.value = previous;
}

// Named profiles: each has isolated memory and run history. Switching re-points the server's stores,
// so memory and run panels are re-read once the switch lands.
function initProfileSwitcher() {
  if (!window.ProfileStore || !window.mountProfileSwitcher) return;
  const store = new window.ProfileStore({
    onChange: () => { refreshMemory(); refreshRuns(); },
  });
  window.profileSwitcher = { store };
  void window.mountProfileSwitcher(store, { prompt: (message, initial) => window.prompt(message, initial) });
}

// ─── Actions ───────────────────────────────────────────────────
// One place that validates and sends a goal. runGoal() and runWorkflow() both go through it.
function submitGoal(goal) {
  if (!goal) return false;
  if (!state.models.length) {
    appendTerminalMessage('error', 'No model is available. Set INCEPTION_API_KEY in .env or start Ollama, then refresh models.');
    return false;
  }
  if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
    appendTerminalMessage('error', `Not connected to kudbEE backend at ${window.location.origin}`);
    return false;
  }

  appendTerminalMessage('user', goal);
  if (!state.isRunning) setStatus('running', 'Running');

  state.ws.send(JSON.stringify({
    type: 'run_goal',
    goal,
    model: document.getElementById('model-select').value,
    agent: document.getElementById('agent-select').value || undefined,
  }));
  return true;
}

function runGoal() {
  const input = document.getElementById('goal-input');
  const goal = input.value.trim();
  if (!goal) {
    appendTerminalMessage('system', 'Enter a goal before pressing Run.');
    input.focus();
    return;
  }
  if (goal.startsWith('/')) {
    void runCommand(goal);
    input.value = '';
    return;
  }
  if (submitGoal(goal)) input.value = '';
}

// A saved workflow becomes a plain-text plan and runs like any other goal (no backend workflow engine yet).
function runWorkflow(workflow) {
  const store = window.WorkflowStore;
  if (!workflow || !store) {
    appendTerminalMessage('error', 'That workflow could not be run.');
    return false;
  }
  if (!workflow.nodes || workflow.nodes.length === 0) {
    appendTerminalMessage('error', `Workflow "${workflow.name || 'untitled'}" has no steps.`);
    return false;
  }
  return submitGoal(store.composeGoal(workflow));
}

function stopGoal() {
  if (state.ws && state.ws.readyState === WebSocket.OPEN) {
    state.ws.send(JSON.stringify({ type: 'stop' }));
    appendTerminalMessage('system', 'Stopping...');
  }
}

// ─── Utilities ─────────────────────────────────────────────────
// Quotes must be escaped too: results are interpolated into attributes (title="…", data-path="…"),
// and file names, run goals and memory paths can contain `"` (a name like `x" onmouseover="…` ran script).
function escapeHtml(text) {
  const entities = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  return String(text ?? '').replace(/[&<>"']/g, ch => entities[ch]);
}

// An image URL is only rendered when it is a same-origin path (`/api/...`) or an inline `data:image/*`.
// The server builds attachment URLs itself, but the client does not assume that: a `javascript:`/`vbscript:`/
// absolute or `data:text/html` value must never reach an <img>. `//host/x` is protocol-relative, i.e. absolute,
// so a single leading slash only (the negative lookahead rejects a second slash). CSP `img-src` is the backstop.
function isSafeImageUrl(url) {
  return typeof url === 'string' && /^\/(?!\/)|^data:image\//.test(url);
}

// ─── Event Listeners ───────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  connectWebSocket();

  document.getElementById('run-goal').addEventListener('click', runGoal);
  document.getElementById('stop-goal').addEventListener('click', stopGoal);
  document.getElementById('submit-goal').addEventListener('click', runGoal);
  document.getElementById('goal-input').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') runGoal();
  });
  document.getElementById('clear-chat').addEventListener('click', clearTerminal);
  document.getElementById('refresh-models').addEventListener('click', loadModels);
  document.getElementById('model-select').addEventListener('change', event => {
    const name = event.target.value;
    if (!name) return;
    state.config.model = name;
    if (state.ws?.readyState === WebSocket.OPEN) {
      state.ws.send(JSON.stringify({ type: 'update_config', config: { model: name } }));
    }
  });
  document.getElementById('refresh-files').addEventListener('click', refreshFiles);
  document.getElementById('upload-files').addEventListener('click', () => document.getElementById('file-upload-input').click());
  document.getElementById('upload-repo').addEventListener('click', () => document.getElementById('repo-upload-input').click());
  document.getElementById('file-upload-input').addEventListener('change', event => uploadFiles(event.target.files));
  document.getElementById('repo-upload-input').addEventListener('change', event => uploadFiles(event.target.files));
  document.getElementById('analyze-image').addEventListener('click', () => document.getElementById('analyze-image-input').click());
  document.getElementById('analyze-image-input').addEventListener('change', event => analyzeImage(event.target.files[0]));
  document.getElementById('generate-image').addEventListener('click', generateImage);
  document.getElementById('git-clone').addEventListener('click', cloneRepository);
  document.getElementById('git-url-input').addEventListener('keypress', event => {
    if (event.key === 'Enter') cloneRepository();
  });
  document.getElementById('git-repository-list').addEventListener('click', event => {
    const button = event.target.closest('[data-git-action]');
    if (button) sendGitAction(button.dataset.gitAction, { path: button.dataset.gitPath });
  });
  document.getElementById('file-tree').addEventListener('click', event => {
    const file = event.target.closest('.file-tree-item');
    if (file) previewFile(file.dataset.path);
  });
  document.getElementById('task-list').addEventListener('click', event => {
    const action = event.target.closest('[data-task-action]');
    if (action) {
      const payload = action.dataset.taskAction === 'block'
        ? { id: action.dataset.taskId, reason: 'Blocked via dashboard' }
        : { id: action.dataset.taskId };
      sendTaskAction(action.dataset.taskAction, payload);
      return;
    }
    const attach = event.target.closest('[data-task-attach]');
    if (attach) {
      const input = document.getElementById('task-attachment-input');
      input.dataset.taskId = attach.dataset.taskAttach;
      input.click();
    }
  });
  document.getElementById('task-attachment-input').addEventListener('change', event => {
    void uploadTaskImage(event.target.files[0], event.target.dataset.taskId);
    event.target.value = '';
  });
  document.getElementById('task-search').addEventListener('input', event => {
    state.taskFilters.query = event.target.value.trim().toLowerCase();
    renderTasks();
  });
  document.getElementById('task-status-filter').addEventListener('change', event => {
    state.taskFilters.status = event.target.value;
    renderTasks();
  });
  document.getElementById('task-priority-filter').addEventListener('change', event => {
    state.taskFilters.priority = event.target.value;
    renderTasks();
  });
  document.getElementById('plugin-list').addEventListener('click', (event) => {
    const button = event.target.closest('.plugin-test');
    if (button) testPlugin(button.dataset.plugin);
  });
  document.getElementById('test-middleware').addEventListener('click', testMiddleware);
  document.getElementById('close-plugin-modal').addEventListener('click', closePluginModal);
  document.getElementById('cancel-plugin-modal').addEventListener('click', closePluginModal);
  document.getElementById('submit-plugin-test').addEventListener('click', submitPluginTest);
  document.getElementById('quick-help').addEventListener('click', showHelp);
  document.getElementById('command-help').addEventListener('click', showHelp);
  document.getElementById('copy-session').addEventListener('click', async () => {
    if (!state.sessionId) return;
    await navigator.clipboard.writeText(state.sessionId);
    appendTerminalMessage('system', 'Session ID copied to clipboard.');
  });
  document.getElementById('plugin-search').addEventListener('input', (event) => {
    state.pluginQuery = event.target.value;
    renderPlugins();
  });
  document.getElementById('file-search').addEventListener('input', (event) => {
    const query = event.target.value.toLowerCase();
    document.querySelectorAll('.file-tree-item').forEach(item => {
      item.hidden = query && !item.textContent.toLowerCase().includes(query);
    });
  });
  document.querySelectorAll('.thought-filter').forEach(button => button.addEventListener('click', () => {
    document.querySelectorAll('.thought-filter').forEach(item => item.classList.remove('active'));
    button.classList.add('active');
    state.thoughtFilter = button.dataset.filter;
    renderThoughts();
  }));
  document.querySelectorAll('.quick-action').forEach(button => button.addEventListener('click', () => {
    void runCommand(button.dataset.command);
  }));
  refreshConnectionMonitor();
  setInterval(refreshConnectionMonitor, 10000);
  refreshSystemHealth();
  setInterval(refreshSystemHealth, 5000);

  // ─── Agent tracking panels (server is the source of truth) ───
  refreshStats();
  refreshRuns();
  loadAgents();  // Load available agent profiles
  initProfileSwitcher();
  setInterval(refreshStats, 3000);
  setInterval(refreshRuns, 10000);
  setInterval(() => { if (state.isRunning) tickRunningTasks(); }, 1000);
  document.getElementById('run-history').addEventListener('click', event => {
    const item = event.target.closest('.run-item');
    if (item) openRun(item.dataset.run);
  });
  document.getElementById('task-list').addEventListener('click', event => {
    if (event.target.closest('button, details, img, a, input, select')) return;
    const item = event.target.closest('.task-item[data-run]');
    if (item) openRun(item.dataset.run);
  });
  document.getElementById('close-run-modal').addEventListener('click', closeRunModal);
  document.getElementById('close-run-modal-2').addEventListener('click', closeRunModal);
  document.getElementById('rerun-goal').addEventListener('click', () => {
    const goal = state.openRun?.goal;
    closeRunModal();
    if (!goal) return;
    document.getElementById('goal-input').value = goal;
    runGoal();
  });
  refreshMemory();
  setInterval(refreshMemory, 30000);
  let memorySearchTimer = null;
  document.getElementById('memory-search').addEventListener('input', event => {
    clearTimeout(memorySearchTimer);
    memorySearchTimer = setTimeout(() => {
      state.memoryQuery = event.target.value.trim();
      refreshMemory();
    }, 250);
  });
  document.querySelectorAll('[data-memory-layer]').forEach(button => button.addEventListener('click', () => {
    document.querySelectorAll('[data-memory-layer]').forEach(item => item.classList.remove('active'));
    button.classList.add('active');
    state.memoryLayer = button.dataset.memoryLayer;
    refreshMemory();
  }));
  document.getElementById('memory-list').addEventListener('click', event => {
    const item = event.target.closest('.memory-item');
    if (item) openMemory(item.dataset.memoryId);
  });
  document.getElementById('add-memory').addEventListener('click', () => openMemoryForm());
  document.getElementById('close-memory-modal').addEventListener('click', closeMemoryModal);
  document.getElementById('promote-memory').addEventListener('click', async () => {
    if (state.openMemoryId && await promoteMemory(state.openMemoryId)) closeMemoryModal();
  });
  document.getElementById('delete-memory').addEventListener('click', async () => {
    if (state.openMemoryId && confirm(`Delete memory ${state.openMemoryId}? The Markdown file is removed.`)) {
      await deleteMemory(state.openMemoryId);
      closeMemoryModal();
    }
  });
  document.getElementById('save-memory').addEventListener('click', async () => {
    const title = document.getElementById('memory-form-title').value.trim();
    const content = document.getElementById('memory-form-content').value.trim();
    if (!title || !content) {
      appendTerminalMessage('error', 'A memory needs a title and content.');
      return;
    }
    try {
      await saveMemory({
        layer: document.getElementById('memory-form-layer').value,
        title,
        content,
        tags: document.getElementById('memory-form-tags').value.split(',').map(tag => tag.trim()).filter(Boolean),
      });
      closeMemoryModal();
    } catch (error) {
      appendTerminalMessage('error', `Could not save memory: ${error.message}`);
    }
  });
  document.getElementById('approve-approval').addEventListener('click', () => answerApproval(true));
  document.getElementById('deny-approval').addEventListener('click', () => answerApproval(false));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !document.getElementById('run-modal').hidden) closeRunModal();
    if (event.key === 'Escape' && !document.getElementById('memory-modal').hidden) closeMemoryModal();
  });

  // Setup enterprise keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.shiftKey) {
      switch (e.key.toUpperCase()) {
        case 'M': // Ctrl+Shift+M: Show metrics
          e.preventDefault();
          void runCommand('/metrics');
          break;
        case 'C': // Ctrl+Shift+C: Show capacity
          e.preventDefault();
          void runCommand('/capacity');
          break;
        case 'L': // Ctrl+Shift+L: Show logs
          e.preventDefault();
          void runCommand('/logs 10');
          break;
        case 'E': // Ctrl+Shift+E: Export
          e.preventDefault();
          void runCommand('/export');
          break;
      }
    }
  });

  Enterprise.auditLog.log('system', 'kudbEE Agent OS started', 'info');

  // Workflow builder save + Actions menu run. The builder dispatches; app.js owns persistence and the run.
  window.addEventListener('workflow:created', (e) => {
    const store = window.WorkflowStore;
    const saved = store ? store.saveWorkflow(localStorage, e.detail) : e.detail;
    if (!saved) {
      appendTerminalMessage('error', 'Could not save that workflow.');
      return;
    }
    appendTerminalMessage('system', `Workflow "${saved.name}" saved (${saved.nodes.length} step(s)).`);
    runWorkflow(saved);
  });
  window.addEventListener('workflow:run', (e) => {
    const workflow = e.detail;
    if (!workflow) return;
    appendTerminalMessage('system', `Running workflow "${workflow.name}"...`);
    runWorkflow(workflow);
  });

  // The governance window's Approve/Reject buttons dispatch this; the dashboard owns the WebSocket response.
  window.addEventListener('approval:resolved', (e) => {
    const d = e.detail || {};
    if (!d.id) return;
    if (state.ws && state.ws.readyState === WebSocket.OPEN) {
      state.ws.send(JSON.stringify({ type: 'approval_response', id: d.id, approved: !!d.approved }));
    }
  });

  // Initialize Dashboard UIs
  try {
    new AnalyticsDashboardUI();
    new TimelineUI();
    new SharingUI();
    new TemplateBrowserUI();
  } catch (err) {
    console.error('Failed to initialize dashboard UIs:', err);
  }

  appendTerminalMessage('system', [
    '╔══════════════════════════════════════════════════════════════╗',
    '║  🐝 kudbEE Agent OS — Enterprise Edition                     ║',
    '╚══════════════════════════════════════════════════════════════╝',
    '',
    '✨ Agent tracking:',
    '  🕑 Run history + step timeline (click any task or run)',
    '  💲 Live token & cost tracking   ⚖️  Approval gates',
    '  📊 Server metrics & capacity    🔐 Audit logging',
    '',
    'Pick ⚡ mercury-2 and give the Worker Agent a real goal, e.g.:',
    '  Read https://hnrss.org/frontpage and write top5.md with the 5 top stories',
    'Type /help for CLI commands.',
  ].join('\n'));

  // Load models periodically
  setInterval(loadModels, 10000);
  setTimeout(loadModels, 1000);
});
