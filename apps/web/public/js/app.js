// THINK BOX AI — kudbEE Devin-like Interface

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
      state.tasks = msg.data.tasks || [];
      renderPlugins();
      renderTasks();
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
  container.innerHTML = visible.map(task => {
    const overdueTask = task.dueDate && task.dueDate < today && ['pending', 'running', 'blocked'].includes(task.status);
    const actions = task.status === 'completed' ? '' : `
      <button type="button" class="task-action" data-task-action="${task.status === 'running' ? 'done' : 'start'}" data-task-id="${task.id}">${task.status === 'running' ? 'Complete' : 'Start'}</button>
      <button type="button" class="task-action" data-task-action="block" data-task-id="${task.id}">Block</button>
    `;
    const attachments = (task.attachments || []).map(image => `<img class="task-attachment" src="${escapeHtml(image.imageUrl)}" alt="${escapeHtml(image.filename)}" loading="lazy">`).join('');
    const activity = (task.activity || []).slice(-5).reverse().map(item => `<div class="task-activity-row"><span>${escapeHtml(item.action)}</span><small>${escapeHtml(item.actor)} · ${new Date(item.timestamp).toLocaleString()}</small>${item.note ? `<p>${escapeHtml(item.note)}</p>` : ''}</div>`).join('');
    return `
      <article class="task-item ${task.status} priority-${task.priority || 'medium'}">
        <div class="task-header">
          <span class="task-status ${task.status}">${escapeHtml(task.status.replace('_', ' '))}</span>
          <span class="task-priority ${task.priority || 'medium'}">${escapeHtml(task.priority || 'medium')}</span>
          <code title="${task.id}">${escapeHtml(task.id.slice(0, 8))}</code>
        </div>
        <div class="task-description">${escapeHtml(task.title || task.description || 'Untitled task')}</div>
        ${task.blockedReason ? `<div class="task-blocked-reason">${escapeHtml(task.blockedReason)}</div>` : ''}
        <div class="task-meta">
          ${task.assignee ? `<span>Owner: ${escapeHtml(task.assignee)}</span>` : '<span>Unassigned</span>'}
          ${task.dueDate ? `<span class="${overdueTask ? 'overdue' : ''}">Due ${escapeHtml(task.dueDate)}</span>` : ''}
        </div>
        ${(task.tags || []).length ? `<div class="task-tags">${task.tags.map(tag => `<span>${escapeHtml(tag)}</span>`).join('')}</div>` : ''}
        ${attachments ? `<div class="task-attachments">${attachments}</div>` : ''}
        <div class="task-card-actions">
          ${actions}
          <button type="button" class="task-action" data-task-attach="${task.id}">Attach image</button>
        </div>
        <details class="task-activity"><summary>Activity (${(task.activity || []).length})</summary>${activity || '<div class="task-activity-row">No activity recorded</div>'}</details>
      </article>
    `;
  }).join('');
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
  renderGitRepositories(data.files);
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
  const extension = filePath.split('.').pop().toLowerCase();
  if (['png', 'jpg', 'jpeg', 'webp', 'gif'].includes(extension)) {
    const imageUrl = `/api/sessions/${state.sessionId}/files/raw?path=${encodeURIComponent(filePath)}`;
    appendTerminalImage('system', filePath, imageUrl, filePath);
    return;
  }
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
  const tokens = tokenizeTerminalCommand(command);
  const [name, ...args] = tokens;
  if (name?.toLowerCase() === '/task' || name?.toLowerCase() === '/tasks') return runTaskCommand(args);
  if (name?.toLowerCase() === '/git') return runGitCommand(args);
  switch (name.toLowerCase()) {
    case '/help':
      appendTerminalMessage('system', [
        '/help              Show available commands',
        '/plugins           List installed plugins and permissions',
        '/models            Refresh and list available models',
        '/status            Check the Agent OS API',
        '/clear             Clear the terminal',
        '/plugin NAME JSON  Execute a plugin with JSON input',
        '/task add "title" [priority=high] [assignee=name] [due=YYYY-MM-DD] [tags=a,b]',
        '/task list [status=open] [priority=high] [q=keyword]',
        '/task show|start|done ID · /task block ID reason',
        '/task priority|assign|due|tag ID value · /task note ID text',
        '/git clone HTTPS_URL · /git status|log|diff|branch PATH',
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
      const response = await fetch(`/api/sessions/${state.sessionId}/tasks/${taskId}/attachments`, { method: 'POST', body: form });
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
