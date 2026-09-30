// kudbEE Approval Workflows — Multi-stage gates and sign-offs

class ApprovalWorkflow {
  constructor() {
    this.workflows = JSON.parse(localStorage.getItem('kudbee-approval-workflows') || '{}');
    this.approvals = JSON.parse(localStorage.getItem('kudbee-approvals') || '{}');
    this.setupEventListeners();
  }

  setupEventListeners() {
    // Instances are created on DOMContentLoaded, so wire the header button now (a nested
    // DOMContentLoaded listener would never fire and the button would do nothing).
    const workflowBtn = document.getElementById('approval-workflow-button');
    if (workflowBtn) {
      workflowBtn.addEventListener('click', () => this.openWorkflowBuilder());
    }

    window.addEventListener('task:needs-approval', (e) => {
      this.showApprovalRequest(e.detail);
    });
  }

  openWorkflowBuilder() {
    const modal = document.createElement('div');
    modal.className = 'modal-backdrop';
    modal.id = 'approval-workflow-modal';
    modal.innerHTML = `
      <section class="modal modal-wide" role="dialog" aria-modal="true">
        <div class="modal-header">
          <div>
            <span class="modal-eyebrow">GOVERNANCE</span>
            <h2>Approval Workflows</h2>
          </div>
          <button class="btn-icon" onclick="this.closest('.modal-backdrop').remove()">×</button>
        </div>

        <div class="approval-builder">
          <div class="workflow-templates">
            <h3>Quick Templates</h3>
            <div class="template-row">
              <button class="template-chip" onclick="approvalWorkflow.createWorkflow('single', 'Single Approver')">
                <span class="template-icon">👤</span> Single Approver
              </button>
              <button class="template-chip" onclick="approvalWorkflow.createWorkflow('serial', 'Serial Chain')">
                <span class="template-icon">⛓</span> Serial Chain
              </button>
              <button class="template-chip" onclick="approvalWorkflow.createWorkflow('parallel', 'Parallel Vote')">
                <span class="template-icon">🗳</span> Parallel Vote
              </button>
              <button class="template-chip" onclick="approvalWorkflow.createWorkflow('hierarchical', 'Hierarchical')">
                <span class="template-icon">🏢</span> Hierarchical
              </button>
            </div>
          </div>

          <div class="current-workflows">
            <h3>Active Workflows</h3>
            <div id="workflows-list" class="workflows-list">
              ${Object.entries(this.workflows).map(([id, wf]) => `
                <div class="workflow-card">
                  <div class="workflow-header">
                    <strong>${wf.name}</strong>
                    <span class="workflow-type">${wf.type}</span>
                  </div>
                  <div class="workflow-stages">
                    ${wf.stages.map((stage, idx) => `
                      <div class="stage-indicator">
                        <span class="stage-number">${idx + 1}</span>
                        <span class="stage-label">${stage.role}</span>
                        <span class="stage-action">${stage.action}</span>
                      </div>
                    `).join('')}
                  </div>
                  <button class="btn-danger" onclick="approvalWorkflow.deleteWorkflow('${id}')">Delete</button>
                </div>
              `).join('')}
            </div>
          </div>

          <div class="pending-approvals">
            <h3>Pending Approvals</h3>
            <div id="pending-approvals" class="pending-approvals-list">
              ${Object.entries(this.approvals).filter(([_, a]) => a.status === 'pending').map(([id, approval]) => `
                <div class="approval-request">
                  <div class="approval-meta">
                    <strong>${approval.taskName}</strong>
                    <span class="approval-time">${new Date(approval.createdAt).toLocaleTimeString()}</span>
                  </div>
                  <div class="approval-detail">${approval.description}</div>
                  <div class="approval-actions">
                    <button class="btn-success" onclick="approvalWorkflow.approveRequest('${id}')">✓ Approve</button>
                    <button class="btn-danger" onclick="approvalWorkflow.rejectRequest('${id}')">✗ Reject</button>
                  </div>
                </div>
              `).join('')}
            </div>
          </div>
        </div>

        <div class="modal-actions">
          <button class="btn-secondary" onclick="this.closest('.modal-backdrop').remove()">Close</button>
        </div>
      </section>
    `;

    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.remove();
    });

    document.body.appendChild(modal);
  }

  createWorkflow(type, name) {
    const workflows = {
      single: {
        type: 'single',
        name: 'Single Approver',
        stages: [{ role: 'Manager', action: 'approve', delay: 0 }]
      },
      serial: {
        type: 'serial',
        name: 'Serial Chain',
        stages: [
          { role: 'Team Lead', action: 'review', delay: 0 },
          { role: 'Manager', action: 'approve', delay: 5 },
          { role: 'Executive', action: 'sign-off', delay: 10 }
        ]
      },
      parallel: {
        type: 'parallel',
        name: 'Parallel Vote',
        stages: [
          { role: 'Reviewer 1', action: 'approve', delay: 0 },
          { role: 'Reviewer 2', action: 'approve', delay: 0 },
          { role: 'Reviewer 3', action: 'approve', delay: 0 }
        ]
      },
      hierarchical: {
        type: 'hierarchical',
        name: 'Hierarchical',
        stages: [
          { role: 'Team', action: 'approve', delay: 0 },
          { role: 'Department', action: 'review', delay: 5 },
          { role: 'Executive', action: 'sign-off', delay: 10 }
        ]
      }
    };

    const id = `workflow-${Date.now()}`;
    const workflow = { ...workflows[type], id, createdAt: new Date().toISOString() };
    if (name) workflow.name = name;
    this.workflows[id] = workflow;
    this.saveWorkflows();
    this.openWorkflowBuilder();
  }

  showApprovalRequest(task) {
    const modal = document.createElement('div');
    modal.className = 'modal-backdrop';
    modal.innerHTML = `
      <section class="modal modal-approval" role="dialog" aria-modal="true">
        <div class="modal-header">
          <span class="modal-eyebrow">APPROVAL REQUIRED</span>
          <h2>${task.title}</h2>
        </div>

        <div class="approval-content">
          <div class="approval-summary">
            <p class="approval-description">${task.description}</p>
            <div class="approval-metadata">
              <div class="meta-item">
                <span class="meta-label">Requested by:</span>
                <span class="meta-value">${task.requestedBy}</span>
              </div>
              <div class="meta-item">
                <span class="meta-label">Priority:</span>
                <span class="meta-value badge-${task.priority}">${task.priority}</span>
              </div>
            </div>
          </div>

          ${task.context ? `
            <div class="approval-context">
              <h4>Context</h4>
              <pre><code>${JSON.stringify(task.context, null, 2)}</code></pre>
            </div>
          ` : ''}

          <div class="approval-decision">
            <label>
              <textarea id="approval-notes" placeholder="Add notes or conditions..." rows="4"></textarea>
            </label>
          </div>
        </div>

        <div class="modal-actions">
          <button class="btn-success" onclick="approvalWorkflow.approveTask('${task.id}')">Approve</button>
          <button class="btn-warning" onclick="approvalWorkflow.requestChanges('${task.id}')">Request Changes</button>
          <button class="btn-danger" onclick="approvalWorkflow.rejectTask('${task.id}')">Reject</button>
        </div>
      </section>
    `;

    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.remove();
    });

    document.body.appendChild(modal);
  }

  approveRequest(id) {
    if (!this.approvals[id]) return;
    this.approvals[id].status = 'approved';
    this.approvals[id].approvedAt = new Date().toISOString();
    this.saveApprovals();
    window.dispatchEvent(new CustomEvent('approval:granted', { detail: { id, status: 'approved' } }));
    this.openWorkflowBuilder();
  }

  rejectRequest(id) {
    if (!this.approvals[id]) return;
    this.approvals[id].status = 'rejected';
    this.approvals[id].rejectedAt = new Date().toISOString();
    this.saveApprovals();
    window.dispatchEvent(new CustomEvent('approval:denied', { detail: { id, status: 'rejected' } }));
    this.openWorkflowBuilder();
  }

  approveTask(taskId) {
    const notes = document.getElementById('approval-notes')?.value || '';
    this.recordApproval(taskId, 'approved', notes);
    document.querySelector('.modal-backdrop')?.remove();
  }

  requestChanges(taskId) {
    const notes = document.getElementById('approval-notes')?.value || '';
    this.recordApproval(taskId, 'changes-requested', notes);
    document.querySelector('.modal-backdrop')?.remove();
  }

  rejectTask(taskId) {
    const notes = document.getElementById('approval-notes')?.value || '';
    this.recordApproval(taskId, 'rejected', notes);
    document.querySelector('.modal-backdrop')?.remove();
  }

  recordApproval(taskId, status, notes) {
    const approval = {
      id: `approval-${Date.now()}`,
      taskId,
      status,
      notes,
      decidedBy: 'current-user',
      decidedAt: new Date().toISOString()
    };
    this.approvals[approval.id] = approval;
    this.saveApprovals();
    window.dispatchEvent(new CustomEvent('approval:recorded', { detail: approval }));
  }

  deleteWorkflow(id) {
    delete this.workflows[id];
    this.saveWorkflows();
    this.openWorkflowBuilder();
  }

  saveWorkflows() {
    localStorage.setItem('kudbee-approval-workflows', JSON.stringify(this.workflows));
  }

  saveApprovals() {
    localStorage.setItem('kudbee-approvals', JSON.stringify(this.approvals));
  }
}

document.addEventListener('DOMContentLoaded', () => {
  window.approvalWorkflow = new ApprovalWorkflow();
});
