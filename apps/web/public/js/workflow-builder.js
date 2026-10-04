// kudbEE Workflow Builder — Task automation with drag-and-drop interface

class WorkflowBuilder {
  constructor() {
    this.modal = document.getElementById('workflow-modal');
    this.closeBtn = document.getElementById('close-workflow-modal');
    this.cancelBtn = document.getElementById('cancel-workflow');
    this.saveBtn = document.getElementById('save-workflow');
    this.loadBtn = document.getElementById('load-workflow');
    this.createBtn = document.getElementById('create-workflow');
    this.templates = document.querySelectorAll('.workflow-template');
    this.canvasArea = document.getElementById('workflow-canvas-area');
    this.nameInput = document.getElementById('workflow-name');
    this.descInput = document.getElementById('workflow-desc');
    this.statusEl = document.getElementById('workflow-status');
    this.loadListEl = document.getElementById('workflow-load-list');

    this.workflowNodes = [];
    this.draggedTemplate = null;
    this.editingId = null;

    this.setupEventListeners();
  }

  setupEventListeners() {
    this.createBtn?.addEventListener('click', () => this.openModal());
    this.closeBtn?.addEventListener('click', () => this.closeModal());
    this.cancelBtn?.addEventListener('click', () => this.closeModal());
    this.saveBtn?.addEventListener('click', () => this.saveWorkflow());
    this.loadBtn?.addEventListener('click', () => this.loadWorkflow());

    // Drag and drop
    if (this.templates && this.templates.length > 0) {
      this.templates.forEach(template => {
        // The elements are <div>s: without draggable="true" the browser never starts a drag, so a mouse user could not add a step at all.
        template.setAttribute('draggable', 'true');
        template.addEventListener('dragstart', (e) => this.handleDragStart(e));
        // Click or Enter/Space adds the step too (keyboard and touch have no drag).
        const type = template.dataset.template;
        template.addEventListener('click', () => this.addNode(type));
        template.addEventListener('keydown', (e) => {
          if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); this.addNode(type); }
        });
      });
    }

    if (this.canvasArea) {
      this.canvasArea.addEventListener('dragover', (e) => this.handleDragOver(e));
      this.canvasArea.addEventListener('drop', (e) => this.handleDrop(e));
      this.canvasArea.addEventListener('dragleave', (e) => this.handleDragLeave(e));
    }
  }

  handleDragStart(e) {
    const template = e.target.closest('.workflow-template');
    if (!template) return;

    this.draggedTemplate = template.dataset.template;
    e.dataTransfer.effectAllowed = 'copy';
    e.dataTransfer.setData('text/plain', this.draggedTemplate);
  }

  handleDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
    if (this.canvasArea) this.canvasArea.classList.add('drag-over');
  }

  handleDragLeave(e) {
    if (this.canvasArea && e.target === this.canvasArea) {
      this.canvasArea.classList.remove('drag-over');
    }
  }

  handleDrop(e) {
    e.preventDefault();
    this.canvasArea.classList.remove('drag-over');

    const templateType = e.dataTransfer.getData('text/plain');
    if (templateType) {
      this.addNode(templateType);
    }
  }

  addNode(templateType, existing) {
    if (this.workflowNodes.length === 0) {
      this.canvasArea.innerHTML = '';
    }

    const nodeId = (existing && existing.id) || `node-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const nodeName = (existing && existing.name) || '';
    const labels = {
      'sequential': 'Sequential Steps',
      'parallel': 'Parallel Tasks',
      'conditional': 'Conditional Branch',
      'loop': 'Loop with Retry'
    };

    const node = document.createElement('div');
    node.className = 'workflow-node';
    node.dataset.nodeId = nodeId;
    node.dataset.template = templateType;
    node.innerHTML = `
      <div class="node-header">
        <span class="node-icon">${this.getIcon(templateType)}</span>
        <span class="node-label">${escapeHtml(labels[templateType])}</span>
      </div>
      <div class="node-content">
        <input type="text" class="node-name" placeholder="Task name..." value="${escapeHtml(nodeName)}">
      </div>
      <button class="node-remove" title="Remove node">×</button>
    `;

    node.querySelector('.node-remove').addEventListener('click', () => {
      node.remove();
      this.workflowNodes = this.workflowNodes.filter(n => n.id !== nodeId);
      if (this.workflowNodes.length === 0) {
        this.canvasArea.innerHTML = '<div class="canvas-placeholder">Drag a template here, or click one, to build the workflow</div>';
      }
    });

    this.canvasArea.appendChild(node);
    this.workflowNodes.push({
      id: nodeId,
      type: templateType,
      name: nodeName
    });
  }

  getIcon(type) {
    const icons = {
      'sequential': '→',
      'parallel': '⇄',
      'conditional': '◇',
      'loop': '⟳'
    };
    return icons[type] || '○';
  }

  openModal() {
    this.modal.removeAttribute('hidden');
    this.workflowNodes = [];
    this.editingId = null;
    this.canvasArea.innerHTML = '<div class="canvas-placeholder">Drag a template here, or click one, to build the workflow</div>';
    this.nameInput.value = '';
    this.descInput.value = '';
    if (this.loadListEl) this.loadListEl.innerHTML = '';
    this.setStatus('');
  }

  closeModal() {
    this.modal.setAttribute('hidden', '');
  }

  setStatus(message) {
    if (!this.statusEl) return;
    this.statusEl.textContent = message || '';
    this.statusEl.hidden = !message;
  }

  saveWorkflow() {
    const name = this.nameInput.value.trim();
    const desc = this.descInput.value.trim();

    if (!name) {
      this.setStatus('Please enter a workflow name.');
      return;
    }

    if (this.workflowNodes.length === 0) {
      this.setStatus('Please add at least one task to the workflow.');
      return;
    }

    // Update node names from inputs
    document.querySelectorAll('.workflow-node').forEach((nodeEl, idx) => {
      const nameInput = nodeEl.querySelector('.node-name');
      if (nameInput && idx < this.workflowNodes.length) {
        this.workflowNodes[idx].name = nameInput.value.trim() || `${this.workflowNodes[idx].type} #${idx + 1}`;
      }
    });

    const workflow = {
      id: this.editingId || undefined,
      name,
      description: desc,
      nodes: this.workflowNodes.map((n) => ({ id: n.id, type: n.type, name: n.name }))
    };

    this.setStatus(`Workflow "${name}" saved.`);
    this.editingId = null;

    // app.js persists it (window.WorkflowStore), shows the terminal confirmation and queues the run.
    window.dispatchEvent(new CustomEvent('workflow:created', { detail: workflow }));

    this.closeModal();
  }

  // List the saved workflows so one can be loaded back into the builder for editing.
  loadWorkflow() {
    const store = window.WorkflowStore;
    const workflows = store ? store.listWorkflows(localStorage) : [];
    if (!this.loadListEl) return;
    this.loadListEl.innerHTML = '';
    if (!workflows.length) {
      this.setStatus('No saved workflows yet.');
      return;
    }
    this.setStatus(`Loaded ${workflows.length} saved workflow(s).`);
    workflows.forEach((wf) => {
      const item = document.createElement('button');
      item.type = 'button';
      item.className = 'workflow-load-item';
      item.textContent = `${wf.name} · ${wf.nodes.length} step(s)`;
      item.addEventListener('click', () => this.applyWorkflow(wf));
      this.loadListEl.appendChild(item);
    });
  }

  applyWorkflow(workflow) {
    this.editingId = workflow.id;
    this.nameInput.value = workflow.name || '';
    this.descInput.value = workflow.description || '';
    this.workflowNodes = [];
    this.canvasArea.innerHTML = '';
    (workflow.nodes || []).forEach((node) => this.addNode(node.type, node));
    if (this.workflowNodes.length === 0) {
      this.canvasArea.innerHTML = '<div class="canvas-placeholder">Drag a template here, or click one, to build the workflow</div>';
    }
    this.setStatus(`Editing "${workflow.name}". Save to update it.`);
  }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  window.workflowBuilder = new WorkflowBuilder();
});
