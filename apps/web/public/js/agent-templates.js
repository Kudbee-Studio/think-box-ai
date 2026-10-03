// kudbEE Agent Templates — Pre-built agent profiles for common tasks

const AGENT_TEMPLATES = {
  researcher: {
    id: 'researcher',
    name: 'Research Agent',
    icon: '🔍',
    description: 'Gathers, analyzes, and synthesizes information from multiple sources',
    tools: ['web_search', 'fetch_url', 'memory_search', 'summarize'],
    systemPrompt: `You are a research agent specializing in gathering and synthesizing information.
Your approach:
1. Search for authoritative sources on the topic
2. Evaluate source credibility and relevance
3. Cross-reference findings to identify patterns
4. Synthesize into coherent, well-sourced insights
5. Document sources and reasoning transparently

Always cite your sources and acknowledge limitations in the available information.`,
    model: 'mercury-2',
    timeout: 300,
    memoryLayers: ['org', 'verified']
  },

  validator: {
    id: 'validator',
    name: 'Validator Agent',
    icon: '✓',
    description: 'Verifies claims, checks for errors, and validates outputs against criteria',
    tools: ['fact_check', 'code_verify', 'test_runner', 'memory_search'],
    systemPrompt: `You are a validation agent that ensures quality and accuracy.
Your process:
1. Define clear validation criteria
2. Check each claim systematically
3. Identify gaps or inconsistencies
4. Test assumptions when possible
5. Provide detailed feedback

Be thorough but fair. Distinguish between critical errors and minor improvements.`,
    model: 'mercury-2',
    timeout: 180,
    memoryLayers: ['verified']
  },

  executor: {
    id: 'executor',
    name: 'Executor Agent',
    icon: '⚡',
    description: 'Takes action by running code, executing tasks, and managing workflows',
    tools: ['code_execute', 'terminal_run', 'api_call', 'file_write'],
    systemPrompt: `You are an execution agent focused on getting things done reliably.
Your execution framework:
1. Break down tasks into smaller steps
2. Execute systematically with error handling
3. Verify each step before proceeding
4. Log actions for audit trail
5. Report outcomes clearly

Always ask for confirmation on destructive operations.`,
    model: 'mercury-2',
    timeout: 600,
    memoryLayers: ['task', 'org'],
    requiresApproval: true
  },

  writer: {
    id: 'writer',
    name: 'Writer Agent',
    icon: '✍',
    description: 'Creates high-quality written content, documentation, and communications',
    tools: ['fetch_url', 'memory_search', 'spell_check', 'tone_analyzer'],
    systemPrompt: `You are a professional writer creating clear, engaging content.
Your writing principles:
1. Know your audience and adapt tone
2. Structure content logically
3. Use clear, concise language
4. Eliminate jargon or explain it
5. Proofread and refine

Focus on clarity and impact.`,
    model: 'opus-5.5',
    timeout: 120,
    memoryLayers: ['org']
  },

  coordinator: {
    id: 'coordinator',
    name: 'Coordinator Agent',
    icon: '🔗',
    description: 'Orchestrates multi-agent workflows and manages task dependencies',
    tools: ['task_queue', 'agent_dispatch', 'memory_store', 'workflow_monitor'],
    systemPrompt: `You are a coordination agent managing multiple agents and workflows.
Your responsibilities:
1. Decompose complex goals into tasks
2. Assign tasks to appropriate agents
3. Track progress and dependencies
4. Handle failures and retries
5. Synthesize results

Think strategically about optimal task ordering.`,
    model: 'mercury-2',
    timeout: 1800,
    memoryLayers: ['task', 'org']
  }
};

class AgentTemplates {
  constructor() {
    this.templates = AGENT_TEMPLATES;
    this.setupEventListeners();
  }

  setupEventListeners() {
    const btn = document.getElementById('agent-templates-button');
    if (btn) {
      btn.addEventListener('click', () => this.showTemplatesModal());
    }

    window.addEventListener('agent:create-from-template', (e) => {
      this.createAgentFromTemplate(e.detail.templateId);
    });
  }

  showTemplatesModal() {
    const modal = document.createElement('div');
    modal.className = 'modal-backdrop';
    modal.innerHTML = `
      <section class="modal modal-wide" role="dialog" aria-modal="true">
        <div class="modal-header">
          <div>
            <span class="modal-eyebrow">QUICK START</span>
            <h2>Agent Templates</h2>
          </div>
          <button class="btn-icon" data-action="close">×</button>
        </div>
        <div class="templates-grid">
          ${Object.values(this.templates).map(template => `
            <div class="template-card">
              <div class="template-header">
                <span class="template-icon">${escapeHtml(template.icon)}</span>
                <h3>${escapeHtml(template.name)}</h3>
              </div>
              <p class="template-desc">${escapeHtml(template.description)}</p>
              <div class="template-tools">
                <strong>Tools:</strong> ${escapeHtml(template.tools.slice(0, 3).join(', '))}${template.tools.length > 3 ? '...' : ''}
              </div>
              <div class="template-model">
                <strong>Model:</strong> ${escapeHtml(template.model)}
              </div>
              <button class="btn-primary" data-action="use-template" data-template-id="${escapeHtml(template.id)}">
                Use this template
              </button>
            </div>
          `).join('')}
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" data-action="close">Close</button>
        </div>
      </section>
    `;

    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.remove();
      const actionEl = e.target.closest?.('[data-action]');
      if (!actionEl || !modal.contains(actionEl)) return;
      if (actionEl.dataset.action === 'close') modal.remove();
      else if (actionEl.dataset.action === 'use-template') {
        this.createAgentFromTemplate(actionEl.dataset.templateId);
      }
    });

    document.body.appendChild(modal);
  }

  createAgentFromTemplate(templateId) {
    const template = this.templates[templateId];
    if (!template) return;

    const agentConfig = {
      id: `agent-${Date.now()}`,
      name: template.name,
      template: templateId,
      tools: template.tools,
      systemPrompt: template.systemPrompt,
      model: template.model,
      timeout: template.timeout,
      memoryLayers: template.memoryLayers,
      requiresApproval: template.requiresApproval || false,
      createdAt: new Date().toISOString()
    };

    console.log('Agent created from template:', agentConfig);
    window.dispatchEvent(new CustomEvent('agent:created', { detail: agentConfig }));

    // Show confirmation
    alert(`✓ Created "${template.name}" agent\nID: ${agentConfig.id}`);
  }

  getTemplate(templateId) {
    return this.templates[templateId];
  }

  listTemplates() {
    return Object.values(this.templates);
  }

  describeTemplate(templateId) {
    const template = this.getTemplate(templateId);
    if (!template) return null;

    return `
**${template.name}** (${template.icon})

${template.description}

**Tools**: ${template.tools.join(', ')}
**Model**: ${template.model}
**Timeout**: ${template.timeout}s
**Memory Layers**: ${template.memoryLayers.join(', ')}
${template.requiresApproval ? '**Requires Approval**: Yes' : ''}

${template.systemPrompt}
    `.trim();
  }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  window.agentTemplates = new AgentTemplates();
});
