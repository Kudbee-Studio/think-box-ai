// kudbEE Collaboration Dashboard — Multi-agent coordination and team workflows

class CollaborationDashboard {
  constructor() {
    this.agents = readStoredJson('kudbee-agents', []);
    this.tasks = readStoredJson('kudbee-collab-tasks', []);
    this.sessions = readStoredJson('kudbee-sessions', []);
    this.setupEventListeners();
  }

  setupEventListeners() {
    // Instances are created on DOMContentLoaded, so wire the header button now (a nested
    // DOMContentLoaded listener would never fire and the button would do nothing).
    const collabBtn = document.getElementById('collaboration-button');
    if (collabBtn) {
      collabBtn.addEventListener('click', () => this.openDashboard());
    }

    window.addEventListener('agent:created', (e) => this.registerAgent(e.detail));
    window.addEventListener('task:assigned', (e) => this.recordTaskAssignment(e.detail));
  }

  registerAgent(agent) {
    const agentRecord = {
      id: agent.id,
      name: agent.name,
      template: agent.template,
      status: 'idle',
      tasksCompleted: 0,
      currentTask: null,
      registeredAt: new Date().toISOString(),
      lastActive: new Date().toISOString()
    };
    this.agents.push(agentRecord);
    this.saveAgents();
  }

  recordTaskAssignment(task) {
    const taskRecord = {
      id: `task-${Date.now()}`,
      name: task.name,
      assignedTo: task.agentId,
      assignedAt: new Date().toISOString(),
      status: 'assigned',
      priority: task.priority || 'normal',
      dueAt: task.dueAt,
      dependencies: task.dependencies || []
    };
    this.tasks.push(taskRecord);
    this.saveTasks();
  }

  openDashboard() {
    const modal = document.createElement('div');
    modal.className = 'modal-backdrop';
    modal.id = 'collaboration-modal';
    modal.innerHTML = `
      <section class="modal modal-wide" role="dialog" aria-modal="true">
        <div class="modal-header">
          <div>
            <span class="modal-eyebrow">COLLABORATION · DEMO</span>
            <h2>Multi-Agent Coordination</h2>
          </div>
          <button class="btn-icon" data-action="close">×</button>
        </div>

        <div class="demo-banner" role="note">Demo data - not connected to real services</div>

        <div class="collaboration-dashboard">
          <div class="team-overview">
            <h3>Team Status</h3>
            <div class="team-stats">
              <div class="stat-card">
                <span class="stat-label">Active Agents</span>
                <span class="stat-value">${this.getActiveAgents().length}</span>
              </div>
              <div class="stat-card">
                <span class="stat-label">Tasks in Progress</span>
                <span class="stat-value">${this.tasks.filter(t => t.status === 'in_progress').length}</span>
              </div>
              <div class="stat-card">
                <span class="stat-label">Completed Today</span>
                <span class="stat-value">${this.getCompletedToday()}</span>
              </div>
              <div class="stat-card">
                <span class="stat-label">Team Efficiency</span>
                <span class="stat-value">${this.tasks.length ? `${this.calculateTeamEfficiency()}%` : '—'}</span>
              </div>
            </div>
          </div>

          <div class="agents-panel">
            <h3>Agents</h3>
            <div class="agents-grid">
              ${this.agents.map(agent => `
                <div class="agent-card" data-agent-id="${escapeHtml(agent.id)}">
                  <div class="agent-header">
                    <span class="agent-name">${escapeHtml(agent.name)}</span>
                    <span class="agent-status ${escapeHtml(agent.status)}">${escapeHtml(agent.status)}</span>
                  </div>
                  <div class="agent-template">${escapeHtml(agent.template)}</div>
                  ${agent.currentTask ? `
                    <div class="agent-task">
                      <span class="task-label">Current:</span>
                      <span class="task-name">${escapeHtml(agent.currentTask)}</span>
                    </div>
                  ` : ''}
                  <div class="agent-stats">
                    <span>✓ ${Number(agent.tasksCompleted) || 0} completed</span>
                  </div>
                  <div class="agent-actions">
                    <button class="btn-secondary" data-action="assign" data-agent-id="${escapeHtml(agent.id)}">Assign Task</button>
                  </div>
                </div>
              `).join('')}
            </div>
          </div>

          <div class="tasks-panel">
            <h3>Task Queue</h3>
            <div class="task-filters">
              <button class="filter-btn active" data-action="filter" data-status="all">All</button>
              <button class="filter-btn" data-action="filter" data-status="assigned">Assigned</button>
              <button class="filter-btn" data-action="filter" data-status="in_progress">In Progress</button>
              <button class="filter-btn" data-action="filter" data-status="completed">Completed</button>
            </div>

            <div class="tasks-list">
              ${this.tasks.slice(0, 10).map(task => `
                <div class="task-item priority-${escapeHtml(task.priority)}">
                  <div class="task-header">
                    <strong>${escapeHtml(task.name)}</strong>
                    <span class="task-status">${escapeHtml(task.status)}</span>
                  </div>
                  <div class="task-meta">
                    ${task.assignedTo ? `
                      <span class="assigned-to">${escapeHtml(this.getAgentName(task.assignedTo))}</span>
                    ` : ''}
                    <span class="task-time">${escapeHtml(new Date(task.assignedAt).toLocaleTimeString())}</span>
                  </div>
                  ${task.dependencies?.length > 0 ? `
                    <div class="task-deps">Dependencies: ${Number(task.dependencies.length) || 0}</div>
                  ` : ''}
                </div>
              `).join('')}
            </div>
            <button class="btn-primary" data-action="create-task">+ Create Task</button>
          </div>

          <div class="workflow-timeline">
            <h3>Example workflows <span class="example-tag">example data, not real runs</span></h3>
            <div class="timeline">
              ${this.buildWorkflowTimeline().map(item => `
                <div class="timeline-item">
                  <div class="timeline-marker"></div>
                  <div class="timeline-content">
                    <strong>${escapeHtml(item.name)}</strong>
                    <span class="timeline-status">${escapeHtml(item.status)} · example</span>
                    <div class="timeline-bar">
                      <div class="progress-bar" style="width: ${Number(item.progress) || 0}%"></div>
                    </div>
                  </div>
                </div>
              `).join('')}
            </div>
          </div>
        </div>

        <div class="modal-actions">
          <button class="btn-secondary" data-action="close">Close</button>
        </div>
      </section>
    `;

    modal.addEventListener('click', (e) => {
      if (e.target === modal) { modal.remove(); return; }
      this.handleModalAction(e, modal);
    });

    document.body.appendChild(modal);
  }

  handleModalAction(e, modal) {
    const el = e.target.closest ? e.target.closest('[data-action]') : null;
    if (!el || !modal.contains(el)) return;
    const action = el.dataset.action;
    if (action === 'close') modal.remove();
    else if (action === 'filter') this.filterTasks(el.dataset.status);
    else if (action === 'assign') this.assignTask(el.dataset.agentId);
    else if (action === 'create-task') this.createTask();
    else if (action === 'submit-assign') this.submitTaskAssignment(el.dataset.agentId);
    else if (action === 'create-new') this.createNewTask();
  }

  assignTask(agentId) {
    const taskModal = document.createElement('div');
    taskModal.className = 'modal-backdrop';
    taskModal.innerHTML = `
      <section class="modal" role="dialog" aria-modal="true">
        <div class="modal-header">
          <h2>Assign Task</h2>
          <button class="btn-icon" data-action="close">×</button>
        </div>

        <div class="task-form">
          <label>
            Task Name:
            <input type="text" id="task-name" placeholder="Enter task name">
          </label>

          <label>
            Description:
            <textarea id="task-desc" placeholder="What should this task do?"></textarea>
          </label>

          <label>
            Priority:
            <select id="task-priority">
              <option value="low">Low</option>
              <option value="normal" selected>Normal</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>
          </label>

          <label>
            <input type="checkbox" id="task-urgent">
            Mark as urgent
          </label>
        </div>

        <div class="modal-actions">
          <button class="btn-secondary" data-action="close">Cancel</button>
          <button class="btn-success" data-action="submit-assign" data-agent-id="${escapeHtml(agentId)}">Assign</button>
        </div>
      </section>
    `;

    taskModal.addEventListener('click', (e) => {
      if (e.target === taskModal) { taskModal.remove(); return; }
      this.handleModalAction(e, taskModal);
    });

    document.body.appendChild(taskModal);
  }

  submitTaskAssignment(agentId) {
    const taskName = document.getElementById('task-name')?.value || 'Unnamed';
    const taskData = {
      agentId,
      name: taskName,
      description: document.getElementById('task-desc')?.value,
      priority: document.getElementById('task-priority')?.value || 'normal',
      assignedAt: new Date().toISOString()
    };
    this.recordTaskAssignment(taskData);
    document.querySelector('.modal-backdrop')?.remove();
    this.openDashboard();
  }

  createTask() {
    const taskModal = document.createElement('div');
    taskModal.className = 'modal-backdrop';
    taskModal.innerHTML = `
      <section class="modal" role="dialog" aria-modal="true">
        <div class="modal-header">
          <h2>Create Task</h2>
          <button class="btn-icon" data-action="close">×</button>
        </div>

        <div class="task-form">
          <label>
            Task Name:
            <input type="text" id="new-task-name" placeholder="Enter task name">
          </label>

          <label>
            Assign to:
            <select id="new-task-agent">
              <option value="">Any available agent</option>
              ${this.getActiveAgents().map(a => `<option value="${escapeHtml(a.id)}">${escapeHtml(a.name)}</option>`).join('')}
            </select>
          </label>

          <label>
            Priority:
            <select id="new-task-priority">
              <option value="low">Low</option>
              <option value="normal" selected>Normal</option>
              <option value="high">High</option>
            </select>
          </label>
        </div>

        <div class="modal-actions">
          <button class="btn-secondary" data-action="close">Cancel</button>
          <button class="btn-success" data-action="create-new">Create</button>
        </div>
      </section>
    `;

    taskModal.addEventListener('click', (e) => {
      if (e.target === taskModal) { taskModal.remove(); return; }
      this.handleModalAction(e, taskModal);
    });

    document.body.appendChild(taskModal);
  }

  createNewTask() {
    const taskName = document.getElementById('new-task-name')?.value || 'Unnamed Task';
    const agentId = document.getElementById('new-task-agent')?.value || this.getActiveAgents()[0]?.id;
    const priority = document.getElementById('new-task-priority')?.value || 'normal';

    const taskData = {
      agentId,
      name: taskName,
      priority,
      assignedAt: new Date().toISOString()
    };
    this.recordTaskAssignment(taskData);
    document.querySelector('.modal-backdrop')?.remove();
    this.openDashboard();
  }

  getActiveAgents() {
    return this.agents.filter(a => a.status === 'idle' || a.status === 'active');
  }

  getAgentName(agentId) {
    return this.agents.find(a => a.id === agentId)?.name || 'Unknown';
  }

  getCompletedToday() {
    const today = new Date().toDateString();
    return this.tasks.filter(t =>
      t.status === 'completed' &&
      new Date(t.assignedAt).toDateString() === today
    ).length;
  }

  calculateTeamEfficiency() {
    if (this.tasks.length === 0) return 100;
    const completed = this.tasks.filter(t => t.status === 'completed').length;
    return Math.round((completed / this.tasks.length) * 100);
  }

  /** Fixed example data for the demo panel; not read from any real run. */
  buildWorkflowTimeline() {
    return [
      { name: 'Research Phase', status: 'completed', progress: 100 },
      { name: 'Validation', status: 'in_progress', progress: 65 },
      { name: 'Integration', status: 'pending', progress: 0 }
    ];
  }

  filterTasks(status) {
    const buttons = document.querySelectorAll('.filter-btn');
    buttons.forEach(btn => btn.classList.remove('active'));
    event.target?.classList.add('active');

    const tasksList = document.querySelector('.tasks-list');
    if (!tasksList) return;

    const filtered = status === 'all' ? this.tasks : this.tasks.filter(t => t.status === status);
    tasksList.innerHTML = filtered.slice(0, 10).map(task => `
      <div class="task-item priority-${escapeHtml(task.priority)}">
        <div class="task-header">
          <strong>${escapeHtml(task.name)}</strong>
          <span class="task-status">${escapeHtml(task.status)}</span>
        </div>
        <div class="task-meta">
          ${task.assignedTo ? `<span class="assigned-to">${escapeHtml(this.getAgentName(task.assignedTo))}</span>` : ''}
          <span class="task-time">${escapeHtml(new Date(task.assignedAt).toLocaleTimeString())}</span>
        </div>
      </div>
    `).join('');
  }

  saveAgents() {
    localStorage.setItem('kudbee-agents', JSON.stringify(this.agents));
  }

  saveTasks() {
    localStorage.setItem('kudbee-collab-tasks', JSON.stringify(this.tasks));
  }
}

document.addEventListener('DOMContentLoaded', () => {
  window.collaborationDashboard = new CollaborationDashboard();
});
