// THINK BOX AI — kudbEE Devin-like Interface

const state = {
  ws: null,
  sessionId: null,
  isRunning: false,
  models: [],
  plugins: [],
  tasks: [],
  thoughts: [],
  thoughtFilter: 'all',
  pluginQuery: '',
  config: {
    model: 'deepseek-coder:6.7b',
    provider: 'ollama',
  }
};

function connectWebSocket() {
  const sdk = window.KudbeeSdkBrowser?.loadConfig?.() ?? null;
  const wsUrl = sdk?.wsUrl ?? `ws://${window.location.hostname}:${window.location.port || 3000}/ws`;
  const backendUrl = wsUrl.replace(/^ws/, 'http').replace(/\/ws$/, '');
  state.correlationId = sdk?.newCorrelationId?.() ?? null;
  state.ws = new WebSocket(wsUrl);

  state.ws.onopen = () => {
    console.log('kudbEE WebSocket connected');
    document.getElementById('header-connection').innerHTML = '<span class="connection-dot"></span> Connected';
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
  switch (msg.type) {
    case 'init':
      state.sessionId = msg.data.sessionId;
      state.plugins = msg.data.plugins || [];
      state.models = msg.data.models || [];
      renderPlugins();
      renderModels();
      setStatus('idle', 'Ready');
      appendTerminalMessage('system', `Session: ${state.sessionId.slice(0, 8)}`);
      refreshFiles();
      break;

    case 'status':
      setStatus(msg.data, msg.data === 'running' ? 'Running' : 'Idle');
      break;

    case 'stream':
      appendTerminalStream(msg.data);
      break;

    case 'thought':
      addThought({ ...msg.data, timestamp: msg.timestamp });
      break;

    case 'task':
      addTask({ ...msg.data, timestamp: msg.timestamp });
      break;

    case 'task_update':
      updateTask(msg.data);
      break;

    case 'plugin_result':
      if (msg.data.result.image_url) {
        appendTerminalImage('plugin', `[${msg.data.plugin}] Image generated`, msg.data.result.image_url, 'Generated image');
        } else {
          appendTerminalMessage('plugin', `[${msg.data.plugin}] ${msg.data.result.success ? '✓' : '✗'}\n${JSON.stringify(msg.data.result, null, 2)}`);
        }
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
  msg.className = `terminal-message ${role}`;

  const header = document.createElement('div');
  header.className = 'message-header';
  header.innerHTML = `<span class="message-role">${role}</span><span class="message-time">${new Date().toLocaleTimeString()}</span>`;

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

function appendTerminalImage(role, content, imageUrl, alt) {
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
  image.src = imageUrl;
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
    const response = await fetch(`/api/sessions/${state.sessionId}/images/analyze`, { method: 'POST', body: form });
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
    const response = await fetch(`/api/sessions/${state.sessionId}/images/generate`, {
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
  const terminal = document.getElementById('terminal');
  terminal.innerHTML = `
    <div class="terminal-welcome">
      <div class="welcome-line">🐝 kudbEE — Agent OS</div>
      <div class="welcome-line">Type a goal and press Run to start.</div>
      <div class="welcome-line">Make sure Ollama is running: <code>ollama serve</code></div>
      <div class="welcome-line">Backend: ${window.location.origin}/ws</div>
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

  container.innerHTML = state.tasks.map(task => `
    <div class="task-item ${task.status}">
      <div class="task-header">
        <span class="task-status ${task.status}">${task.status}</span>
      </div>
      <div class="task-description">${escapeHtml(task.description)}</div>
      <div class="task-time">${new Date(task.timestamp).toLocaleTimeString()}</div>
    </div>
  `).join('');
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

  const visibleThoughts = state.thoughts.filter(thought => state.thoughtFilter === 'all' || thought.status === state.thoughtFilter);
  container.innerHTML = visibleThoughts.slice(-50).reverse().map(thought => `
    <div class="thought-item ${thought.status || 'info'}">
      <div class="thought-header">
        <span class="thought-type">${thought.type || 'thought'}</span>
        <span>${new Date(thought.timestamp).toLocaleTimeString()}</span>
      </div>
      <div class="thought-content">${escapeHtml(thought.content || thought.plugin || thought.answer || '')}</div>
      ${thoughtDetails(thought)}
    </div>
  `).join('');
}

function thoughtDetails(thought) {
  const details = {};
  if (thought.plugin) details.plugin = thought.plugin;
  if (thought.input && typeof thought.input === 'object') {
    details.input = Object.fromEntries(Object.entries(thought.input).map(([key, value]) => [
      key,
      /base64|token|secret|password|authorization/i.test(key) ? '[omitted]' : value,
    ]));
  }
  if (thought.result && typeof thought.result === 'object') {
    details.result = Object.fromEntries(Object.entries(thought.result).filter(([key]) => !/base64|token|secret|password|authorization/i.test(key)));
  }
  if (thought.path) details.path = thought.path;
  if (thought.image) details.image = thought.image;
  if (thought.error) details.error = thought.error;
  if (Object.keys(details).length === 0) return '';
  return `<pre class="thought-detail">${escapeHtml(JSON.stringify(details, null, 2))}</pre>`;
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
      <span class="plugin-icon">${plugin.icon || '🔌'}</span>
      <div class="plugin-info">
        <div class="plugin-name">${plugin.name}</div>
        <div class="plugin-desc">${plugin.description}</div>
      </div>
      <span class="plugin-badge ${plugin.permission}">${plugin.permission}</span>
      <button type="button" class="plugin-test" data-plugin="${plugin.name}">Test</button>
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
  const response = await fetch(`/api/sessions/${state.sessionId}/files`, { cache: 'no-store' });
  if (!response.ok) return;
  const data = await response.json();
  const tree = document.getElementById('file-tree');
  tree.innerHTML = data.files.length
    ? data.files.map(file => `<button class="file-tree-item" data-path="${escapeHtml(file.path)}"><span>${escapeHtml(file.path)}</span><small>${formatBytes(file.size)}</small></button>`).join('')
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
  const response = await fetch(`/api/sessions/${state.sessionId}/files`, { method: 'POST', body: form });
  const result = await response.json();
  if (!response.ok) {
    appendTerminalMessage('error', `Upload failed: ${result.error || response.statusText}`);
    return;
  }
  appendTerminalMessage('system', `Uploaded ${result.uploaded.length} file(s) into the session workspace.`);
  await refreshFiles();
}

async function previewFile(filePath) {
  const response = await fetch(`/api/sessions/${state.sessionId}/files/content?path=${encodeURIComponent(filePath)}`);
  const result = await response.json();
  if (!response.ok) {
    appendTerminalMessage('error', `Preview failed: ${result.error}`);
    return;
  }
  appendTerminalMessage('system', `${filePath}\n\n${result.content}`);
}

function showHelp() {
  document.getElementById('goal-input').value = '/help';
  runGoal();
}

async function runSlashCommand(command) {
  const [name, ...args] = command.trim().split(/\s+/);
  switch (name.toLowerCase()) {
    case '/help':
      appendTerminalMessage('system', [
        '/help              Show available commands',
        '/plugins           List installed plugins and permissions',
        '/models            Refresh and list available models',
        '/status            Check the Agent OS API',
        '/clear             Clear the terminal',
        '/plugin NAME JSON  Execute a plugin with JSON input',
      ].join('\n'));
      return true;
    case '/plugins':
      appendTerminalMessage('system', state.plugins.length
        ? state.plugins.map(plugin => `${plugin.name} [${plugin.permission}] — ${plugin.description}`).join('\n')
        : 'No plugins are registered.');
      return true;
    case '/models':
      await loadModels();
      appendTerminalMessage('system', state.models.length
        ? state.models.map(model => model.name).join('\n')
        : 'No models found. Start Ollama and pull a model.');
      return true;
    case '/status': {
      try {
        const response = await fetch('/api/health', { cache: 'no-store' });
        appendTerminalMessage('system', JSON.stringify(await response.json(), null, 2));
      } catch (error) {
        appendTerminalMessage('error', `Status check failed: ${error.message}`);
      }
      return true;
    }
    case '/clear':
      clearTerminal();
      return true;
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
      } catch {
        appendTerminalMessage('error', 'Plugin input must be valid JSON.');
      }
      return true;
    }
    default:
      return false;
  }
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
        <span class="plugin-badge ${check.status}">${escapeHtml(check.status)}</span>
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

  select.innerHTML = state.models.map(m =>
    `<option value="${m.name}">${m.name} (${(m.size / 1e9).toFixed(1)}GB)</option>`
  ).join('');
}

// ─── Actions ───────────────────────────────────────────────────
function runGoal() {
  const input = document.getElementById('goal-input');
  const goal = input.value.trim();
  if (!goal) {
    appendTerminalMessage('system', 'Enter a goal before pressing Run.');
    input.focus();
    return;
  }
  if (goal.startsWith('/')) {
    void runSlashCommand(goal);
    input.value = '';
    return;
  }
  if (!state.models.length) {
    appendTerminalMessage('error', 'No Ollama model is available. Start Ollama and pull a model, then refresh models.');
    return;
  }
  if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
    appendTerminalMessage('error', `Not connected to kudbEE backend at ${window.location.origin}`);
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

// ─── Event Listeners ───────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  connectWebSocket();

  document.getElementById('run-goal').addEventListener('click', runGoal);
  document.getElementById('stop-goal').addEventListener('click', stopGoal);
  document.getElementById('submit-goal').addEventListener('click', runGoal);
  document.getElementById('analyze-image').addEventListener('click', () => document.getElementById('analyze-image-input').click());
  document.getElementById('analyze-image-input').addEventListener('change', event => analyzeImage(event.target.files[0]));
  document.getElementById('generate-image').addEventListener('click', generateImage);
  document.getElementById('goal-input').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') runGoal();
  });
  document.getElementById('clear-chat').addEventListener('click', clearTerminal);
  document.getElementById('refresh-models').addEventListener('click', loadModels);
  document.getElementById('refresh-files').addEventListener('click', refreshFiles);
  document.getElementById('upload-files').addEventListener('click', () => document.getElementById('file-upload-input').click());
  document.getElementById('upload-repo').addEventListener('click', () => document.getElementById('repo-upload-input').click());
  document.getElementById('file-upload-input').addEventListener('change', event => uploadFiles(event.target.files));
  document.getElementById('repo-upload-input').addEventListener('change', event => uploadFiles(event.target.files));
  document.getElementById('file-tree').addEventListener('click', event => {
    const file = event.target.closest('.file-tree-item');
    if (file) previewFile(file.dataset.path);
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
    document.getElementById('goal-input').value = button.dataset.command;
    runGoal();
  }));
  refreshConnectionMonitor();
  setInterval(refreshConnectionMonitor, 10000);
  refreshSystemHealth();
  setInterval(refreshSystemHealth, 5000);

  // Load models periodically
  setInterval(loadModels, 10000);
  setTimeout(loadModels, 1000);
});
