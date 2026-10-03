// THINK BOX AI — kudbEE Devin-like Interface (Mock Mode)

const state = {
  sessionId: null,
  isRunning: false,
  models: ["smollm2:135m"],
  plugins: [],
  tasks: [],
  taskFilters: { query: '', status: 'all', priority: 'all' },
  thoughts: [],
  thoughtFilter: 'all',
  pluginQuery: '',
  config: {
    model: 'smollm2:135m',
    provider: 'ollama',
  }
};

// Initialize on load
window.addEventListener('load', async () => {
  try {
    await initializeApp();
    setupEventListeners();
    enableInput(true);
    setStatus('idle', 'Ready');
    appendTerminalMessage('system', '🐝 Connected to kudbEE (Mock Mode)');
  } catch (err) {
    console.error('Init error:', err);
    appendTerminalMessage('error', `Initialization error: ${err.message}`);
  }
});

async function initializeApp() {
  console.log('Initializing app...');

  try {
    // Fetch initial data from API
    const response = await fetch('http://localhost:3000/api/init', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const text = await response.text();
    console.log('Response:', text.substring(0, 100));

    const data = JSON.parse(text);
    state.sessionId = data.sessionId;
    state.plugins = data.plugins || [];
    state.models = data.models || ["smollm2:135m"];
    state.tasks = data.tasks || [];

    renderPlugins();
    renderTasks();
    renderModels();
    appendTerminalMessage('system', `Session: ${state.sessionId.slice(0, 8)}`);
  } catch (err) {
    console.error('Fetch error:', err);
    throw err;
  }
}

function setupEventListeners() {
  const goalInput = document.getElementById('goal-input');
  const submitBtn = document.getElementById('submit-goal');
  const runBtn = document.getElementById('run-goal');
  const stopBtn = document.getElementById('stop-goal');
  const clearBtn = document.getElementById('clear-chat');
  const modelSelect = document.getElementById('model-select');

  if (submitBtn) submitBtn.addEventListener('click', () => executeGoal(goalInput?.value || ''));
  if (runBtn) runBtn.addEventListener('click', () => executeGoal(goalInput?.value || ''));
  if (clearBtn) clearBtn.addEventListener('click', () => clearTerminal());
  if (goalInput) {
    goalInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        executeGoal(goalInput.value);
      }
    });
  }
  if (modelSelect) {
    modelSelect.addEventListener('change', (e) => {
      state.config.model = e.target.value;
    });
  }

  // Quick actions
  document.querySelectorAll('.quick-action').forEach(btn => {
    btn.addEventListener('click', () => {
      const cmd = btn.getAttribute('data-command');
      executeGoal(cmd);
    });
  });
}

async function executeGoal(goal) {
  if (!goal || !goal.trim()) {
    appendTerminalMessage('error', 'Please enter a goal');
    return;
  }

  enableInput(false);
  setStatus('running', 'Processing...');
  appendTerminalMessage('user', goal);

  try {
    const response = await fetch('http://localhost:3000/api/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        goal,
        model: state.config.model,
        sessionId: state.sessionId
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const result = await response.json();

    if (result.success) {
      appendTerminalMessage('assistant', result.result || 'Goal executed successfully');
      setStatus('idle', 'Completed');
      addThought({ text: goal, type: 'thinking' });
    } else {
      appendTerminalMessage('error', `Error: ${result.error}`);
      setStatus('error', 'Error');
    }
  } catch (err) {
    console.error('Execution error:', err);
    appendTerminalMessage('error', `Error: ${err.message}`);
    setStatus('error', 'Error');
  } finally {
    enableInput(true);
    const goalInput = document.getElementById('goal-input');
    if (goalInput) goalInput.value = '';
  }
}

// ─── Terminal ──────────────────────────────────────────────────
function appendTerminalMessage(role, content) {
  const terminal = document.getElementById('terminal');
  if (!terminal) return;

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

function clearTerminal() {
  const terminal = document.getElementById('terminal');
  if (terminal) {
    terminal.innerHTML = '<div class="terminal-welcome"><div class="welcome-line">Terminal cleared</div></div>';
  }
}

// ─── Plugins ───────────────────────────────────────────────────
function renderPlugins() {
  const list = document.getElementById('plugin-list');
  if (!list) return;

  if (!state.plugins || state.plugins.length === 0) {
    list.innerHTML = '<div class="empty-state">No plugins loaded</div>';
    return;
  }

  list.innerHTML = state.plugins.map(p => `
    <div class="plugin-item" style="display: flex; gap: 8px; padding: 8px; border-bottom: 1px solid #eee; cursor: pointer;">
      <span style="font-size: 20px;">${p.icon}</span>
      <div style="flex: 1;">
        <div style="font-weight: bold; font-size: 12px;">${p.name}</div>
        <div style="font-size: 11px; color: #666;">${p.description}</div>
      </div>
      <button onclick="testPlugin('${p.id}')" style="padding: 4px 8px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer;">▶</button>
    </div>
  `).join('');
}

function testPlugin(pluginId) {
  appendTerminalMessage('system', `Testing plugin: ${pluginId}`);
}

// ─── Models ────────────────────────────────────────────────────
function renderModels() {
  const select = document.getElementById('model-select');
  if (!select) return;

  if (!state.models || state.models.length === 0) {
    select.innerHTML = '<option>No models available</option>';
    return;
  }

  select.innerHTML = state.models.map(m => `<option value="${m}">${m}</option>`).join('');
  select.value = state.config.model;
}

// ─── Tasks ─────────────────────────────────────────────────────
function renderTasks() {
  const list = document.getElementById('task-list');
  if (!list) return;

  const filtered = (state.tasks || []).filter(t => {
    const matchStatus = state.taskFilters.status === 'all' || t.status === state.taskFilters.status;
    const matchQuery = !state.taskFilters.query || (t.title && t.title.toLowerCase().includes(state.taskFilters.query.toLowerCase()));
    return matchStatus && matchQuery;
  });

  if (filtered.length === 0) {
    list.innerHTML = '<div class="empty-state">No tasks</div>';
  } else {
    list.innerHTML = filtered.map(t => `
      <div class="task-item" style="padding: 8px; border-bottom: 1px solid #eee;">
        <div style="font-weight: bold;">${t.title}</div>
        <div style="font-size: 12px; color: #666;">${t.status}</div>
      </div>
    `).join('');
  }

  const count = document.getElementById('task-count');
  if (count) count.textContent = filtered.length;
}

function addTask(task) {
  state.tasks = state.tasks || [];
  state.tasks.push(task);
  renderTasks();
}

function addThought(thought) {
  state.thoughts = state.thoughts || [];
  state.thoughts.push(thought);
  const list = document.getElementById('thought-list');
  if (list) {
    const item = document.createElement('div');
    item.className = 'thought-item';
    item.style.cssText = 'padding: 8px; border-bottom: 1px solid #eee;';
    const body = document.createElement('div');
    body.className = 'thought-text';
    body.textContent = thought.text || 'thinking...';
    item.appendChild(body);
    list.appendChild(item);
  }
  const count = document.getElementById('thought-count');
  if (count) count.textContent = (state.thoughts || []).length;
}

// ─── Status & Input ────────────────────────────────────────────
function setStatus(status, text) {
  const dot = document.getElementById('status-dot');
  const txt = document.getElementById('status-text');
  if (dot) {
    dot.className = `status-dot ${status}`;
  }
  if (txt) txt.textContent = text;
}

function enableInput(enabled) {
  const input = document.getElementById('goal-input');
  const submit = document.getElementById('submit-goal');
  const run = document.getElementById('run-goal');

  if (input) input.disabled = !enabled;
  if (submit) submit.disabled = !enabled;
  if (run) run.disabled = !enabled;
}

// Update header on load
window.addEventListener('load', () => {
  const header = document.getElementById('header-connection');
  if (header) {
    header.innerHTML = '<span class="connection-dot" style="background: #4caf50;"></span> Connected (Mock)';
  }
});
