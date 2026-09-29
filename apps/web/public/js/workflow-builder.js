// kudbEE Workflow Builder — Task automation with drag-and-drop interface

class WorkflowBuilder {
  constructor() {
    this.modal = document.getElementById('workflow-modal');
    this.closeBtn = document.getElementById('close-workflow-modal');
    this.cancelBtn = document.getElementById('cancel-workflow');
    this.saveBtn = document.getElementById('save-workflow');
    this.createBtn = document.getElementById('create-workflow');
    this.templates = document.querySelectorAll('.workflow-template');
    this.canvasArea = document.getElementById('workflow-canvas-area');
    this.nameInput = document.getElementById('workflow-name');
    this.descInput = document.getElementById('workflow-desc');

    this.workflowNodes = [];
    this.draggedTemplate = null;

    this.setupEventListeners();
  }

  setupEventListeners() {
    this.createBtn?.addEventListener('click', () => this.openModal());
    this.closeBtn?.addEventListener('click', () => this.closeModal());
    this.cancelBtn?.addEventListener('click', () => this.closeModal());
    this.saveBtn?.addEventListener('click', () => this.saveWorkflow());

    // Drag and drop
    this.templates.forEach(template => {
      template.addEventListener('dragstart', (e) => this.handleDragStart(e));
    });

    this.canvasArea.addEventListener('dragover', (e) => this.handleDragOver(e));
    this.canvasArea.addEventListener('drop', (e) => this.handleDrop(e));
    this.canvasArea.addEventListener('dragleave', (e) => this.handleDragLeave(e));
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
    this.canvasArea.classList.add('drag-over');
  }

  handleDragLeave(e) {
    if (e.target === this.canvasArea) {
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

  addNode(templateType) {
    if (this.workflowNodes.length === 0) {
      this.canvasArea.innerHTML = '';
    }

    const nodeId = `node-${Date.now()}`;
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
        <span class="node-label">${labels[templateType]}</span>
      </div>
      <div class="node-content">
        <input type="text" class="node-name" placeholder="Task name..." value="">
      </div>
      <button class="node-remove" title="Remove node">×</button>
    `;

    node.querySelector('.node-remove').addEventListener('click', () => {
      node.remove();
      this.workflowNodes = this.workflowNodes.filter(n => n.id !== nodeId);
      if (this.workflowNodes.length === 0) {
        this.canvasArea.innerHTML = '<div class="canvas-placeholder">Drag templates here to build workflow</div>';
      }
    });

    this.canvasArea.appendChild(node);
    this.workflowNodes.push({
      id: nodeId,
      type: templateType,
      name: ''
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
    this.canvasArea.innerHTML = '<div class="canvas-placeholder">Drag templates here to build workflow</div>';
    this.nameInput.value = '';
    this.descInput.value = '';
  }

  closeModal() {
    this.modal.setAttribute('hidden', '');
  }

  saveWorkflow() {
    const name = this.nameInput.value.trim();
    const desc = this.descInput.value.trim();

    if (!name) {
      alert('Please enter a workflow name');
      return;
    }

    if (this.workflowNodes.length === 0) {
      alert('Please add at least one task to the workflow');
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
      id: `workflow-${Date.now()}`,
      name,
      description: desc,
      nodes: this.workflowNodes,
      createdAt: new Date().toISOString()
    };

    console.log('Workflow saved:', workflow);

    // Emit event for app.js to handle
    window.dispatchEvent(new CustomEvent('workflow:created', { detail: workflow }));

    this.closeModal();
  }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  window.workflowBuilder = new WorkflowBuilder();
});
