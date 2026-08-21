// THINK BOX AI — kudbEE Devin-like Interface
// Connects to FastAPI backend on port 8000

const state = {
  ws: null,
  sessionId: null,
  isRunning: false,
  models: [],
  plugins: [],
  tasks: [],
  thoughts: [],
  config: {
    model: 'deepseek-coder:6.7b',
    provider: 'ollama',
  }
};

function connectWebSocket() {
  const wsUrl = `ws://${window.location.hostname}:8000/ws`;
  state.ws = new WebSocket(wsUrl);

  state.ws.onopen = () => {
    console.log('kudbEE WebSocket connected');
    appendTerminalMessage('system', '🐝 Connected to kudbEE backend');
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
    appendTerminalMessage('error', 'WebSocket connection error — is the backend running on port 8000?');
  };

  state.ws.onclose = () => {
    setStatus('error', 'Disconnected');
    appendTerminalMessage('system', 'Disconnected — retrying in 3s...');
    setTimeout(connectWebSocket, 3000);
  };
}

function handleMessage(msg) {
  switch (msg.type) {
    case 'init':
      state.sessionId = msg.data.sessionId;
      state.plugins = msg.data.plugins || [];
      state.models = msg.data.models || [];
      renderPlugins();
      renderModels();
      setStatus('idle', 'Ready');
      appendTerminalMessage('system', `Session: ${state.sessionId.slice(0, 8)}`);
      break;

    case 'STATUS':
      setStatus(msg.data.status, msg.data.status === 'running' ? 'Running' : 'Idle');
      break;

    case 'TOKEN':
      appendTerminalStream(msg.data.value);
      break;

    case 'THOUGHT':
      addThought({ ...msg.data, timestamp: msg.timestamp });
      break;

    case 'TASK_UPDATE':
      addTask({ ...msg.data, timestamp: msg.timestamp });
      break;

    case 'TOOL_CALL':
      appendTerminalMessage('plugin', `🔧 [${msg.data.tool}] ${JSON.stringify(msg.data.args)}`);
      break;

    case 'TOOL_RESULT': {
      const result = msg.data.result;
      const icon = result?.error ? '✗' : '✓';
      appendTerminalMessage('plugin', `${icon} [${msg.data.tool}] ${result?.data?.content || result?.error || JSON.stringify(result)}`);
      break;
    }

    case 'plugin_result':
      appendTerminalMessage('plugin', `[${msg.data.plugin}] ${msg.data.result.success ? '✓' : '✗'} ${msg.data.result.content || msg.data.result.error || ''}`);
      break;

    case 'models':
      state.models = msg.data;
      renderModels();
      break;

    case 'result':
      setStatus('idle', 'Completed');
      appendTerminalMessage('assistant', `\n✓ Goal completed\n${msg.data.result || ''}`);
      enableInput(true);
      break;

    case 'error':
      appendTerminalMessage('error', `Error: ${msg.data}`);
      setStatus('error', 'Error');
      enableInput(true);
      break;
  }
}

// ─── Terminal ──────────────────────────────────────────────────
function appendTerminalMessage(role, content) {
  const terminal = document.getElementById('terminal');
  const welcome = terminal.querySelector('.terminal-welcome');
  if (welcome) welcome.remove();

  const msg = document.createElement('div');
  msg.className = `terminal-message ${sanitizeCssToken(role)}`.trim();

  const header = document.createElement('div');
  header.className = 'message-header';

  const roleLabel = document.createElement('span');
  roleLabel.className = 'message-role';
  roleLabel.textContent = role;

  const timeLabel = document.createElement('span');
  timeLabel.className = 'message-time';
  timeLabel.textContent = new Date().toLocaleTimeString();

  header.append(roleLabel, timeLabel);

  const body = document.createElement('div');
  body.className = 'message-content';
  body.textContent = content;

  msg.appendChild(header);
  msg.appendChild(body);
  terminal.appendChild(msg);
  terminal.scrollTop = terminal.scrollHeight;
}

function appendTerminalStream(token) {
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

function clearTerminal() {
  const terminal = document.getElementById('terminal');
  terminal.innerHTML = `
    <div class="terminal-welcome">
      <div class="welcome-line">🐝 kudbEE — Agent OS</div>
      <div class="welcome-line">Type a goal and press Run to start.</div>
      <div class="welcome-line">Make sure Ollama is running: <code>ollama serve</code></div>
      <div class="welcome-line">Backend: ws://localhost:8000/ws</div>
    </div>
  `;
  state.thoughts = [];
  state.tasks = [];
  renderTasks();
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

  if (status === 'running') {
    runBtn.disabled = true;
    stopBtn.disabled = false;
    input.disabled = true;
  } else {
    runBtn.disabled = false;
    stopBtn.disabled = true;
    input.disabled = false;
  }
}

function enableInput(enabled) {
  document.getElementById('goal-input').disabled = !enabled;
  document.getElementById('run-goal').disabled = !enabled;
  document.getElementById('stop-goal').disabled = enabled;
}

// ─── Tasks ─────────────────────────────────────────────────────
function addTask(task) {
  state.tasks.push(task);
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
  if (state.tasks.length === 0) {
    container.innerHTML = '<div class="empty-state">No tasks yet</div>';
    return;
  }

  container.replaceChildren(...state.tasks.map(task => {
    const item = document.createElement('div');
    const status = sanitizeCssToken(task.status);
    item.className = `task-item ${status}`.trim();

    const header = document.createElement('div');
    header.className = 'task-header';

    const badge = document.createElement('span');
    badge.className = `task-status ${status}`.trim();
    badge.textContent = task.status || '';
    header.appendChild(badge);

    const description = document.createElement('div');
    description.className = 'task-description';
    description.textContent = task.description || '';

    const time = document.createElement('div');
    time.className = 'task-time';
    time.textContent = new Date(task.timestamp).toLocaleTimeString();

    item.append(header, description, time);
    return item;
  }));
}

// ─── Thoughts ──────────────────────────────────────────────────
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

  container.replaceChildren(...state.thoughts.slice(-50).reverse().map(thought => {
    const item = document.createElement('div');
    item.className = `thought-item ${sanitizeCssToken(thought.status || 'info')}`.trim();

    const header = document.createElement('div');
    header.className = 'thought-header';

    const type = document.createElement('span');
    type.className = 'thought-type';
    type.textContent = thought.type || 'thought';

    const time = document.createElement('span');
    time.textContent = new Date(thought.timestamp).toLocaleTimeString();

    header.append(type, time);

    const content = document.createElement('div');
    content.className = 'thought-content';
    content.textContent = thought.content || thought.plugin || '';

    item.append(header, content);
    return item;
  }));
}

// ─── Plugins ───────────────────────────────────────────────────
function renderPlugins() {
  const container = document.getElementById('plugin-list');
  if (!state.plugins.length) {
    container.innerHTML = '<div class="empty-state">No plugins loaded</div>';
    return;
  }

  container.replaceChildren(...state.plugins.map(plugin => {
    const item = document.createElement('div');
    item.className = 'plugin-item';

    const icon = document.createElement('span');
    icon.className = 'plugin-icon';
    icon.textContent = plugin.icon || '🔌';

    const info = document.createElement('div');
    info.className = 'plugin-info';

    const name = document.createElement('div');
    name.className = 'plugin-name';
    name.textContent = plugin.name || '';

    const description = document.createElement('div');
    description.className = 'plugin-desc';
    description.textContent = plugin.description || '';

    info.append(name, description);

    const badge = document.createElement('span');
    const permission = sanitizeCssToken(plugin.permission);
    badge.className = `plugin-badge ${permission}`.trim();
    badge.textContent = plugin.permission || '';

    item.append(icon, info, badge);
    return item;
  }));
}

// ─── Models ────────────────────────────────────────────────────
async function loadModels() {
  if (!state.ws || state.ws.readyState !== WebSocket.OPEN) return;
  state.ws.send(JSON.stringify({ type: 'list_models' }));
}

function renderModels() {
  const select = document.getElementById('model-select');
  if (!state.models.length) {
    select.innerHTML = '<option value="">No models found (start Ollama)</option>';
    return;
  }

  select.replaceChildren(...state.models.map((model) => {
    const option = document.createElement('option');
    option.value = model.name || '';
    option.textContent = `${model.name || ''} (${(model.size / 1e9).toFixed(1)}GB)`;
    return option;
  }));
}

// ─── Actions ───────────────────────────────────────────────────
function runGoal() {
  const input = document.getElementById('goal-input');
  const goal = input.value.trim();
  if (!goal) return;
  if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
    appendTerminalMessage('error', 'Not connected to kudbEE backend (port 8000)');
    return;
  }

  appendTerminalMessage('user', goal);
  setStatus('running', 'Running');

  state.ws.send(JSON.stringify({
    type: 'run_goal',
    goal,
    model: document.getElementById('model-select').value,
  }));

  input.value = '';
}

function stopGoal() {
  if (state.ws && state.ws.readyState === WebSocket.OPEN) {
    state.ws.send(JSON.stringify({ type: 'stop' }));
    appendTerminalMessage('system', 'Stopping...');
  }
}

// ─── Utilities ─────────────────────────────────────────────────
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function sanitizeCssToken(value) {
  return String(value || '').replace(/[^a-zA-Z0-9_-]/g, '');
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
  document.getElementById('refresh-files').addEventListener('click', () => {
    appendTerminalMessage('system', 'File refresh triggered');
  });

  // Load models periodically
  setInterval(loadModels, 10000);
  setTimeout(loadModels, 1000);
});
