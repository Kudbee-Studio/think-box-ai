// kudbEE Git Integration — Dashboard sync for cloned repos and generated files

class GitIntegration {
  constructor() {
    this.repositories = [];
    this.workspaceFiles = [];
    this.setupEventListeners();
    this.loadRepositories();
  }

  setupEventListeners() {
    // Git URL paste detection
    const goalInput = document.getElementById('goal-input');
    if (goalInput) {
      goalInput.addEventListener('paste', (e) => this.handleGitPaste(e));
      goalInput.addEventListener('keydown', (e) => this.handleGitCommand(e));
    }

    // File tree interactions
    const fileTree = document.getElementById('file-tree');
    if (fileTree) {
      fileTree.addEventListener('click', (e) => this.handleFileTreeClick(e));
    }

    // Listen for agent-generated files
    window.addEventListener('agent:file-created', (e) => this.addGeneratedFile(e.detail));
    window.addEventListener('agent:file-modified', (e) => this.updateGeneratedFile(e.detail));
  }

  /**
   * Detect git URL pastes and clone
   */
  handleGitPaste(event) {
    const text = (event.clipboardData || window.clipboardData).getData('text');
    const gitUrlPattern = /^(https?:\/\/)?(www\.)?github\.com\/[^/]+\/[^/]+(?:\.git)?$/;

    if (gitUrlPattern.test(text)) {
      event.preventDefault();

      // Show git clone UI
      this.showGitCloneDialog(text);
    }
  }

  /**
   * Detect /git commands in terminal
   */
  handleGitCommand(event) {
    if (event.key === 'Enter' && event.target.value.startsWith('/git ')) {
      event.preventDefault();

      const url = event.target.value.replace('/git ', '').trim();
      event.target.value = '';

      if (url) {
        this.cloneRepository(url);
      }
    }
  }

  /**
   * Show git clone dialog
   */
  showGitCloneDialog(url) {
    const dialog = document.createElement('div');
    dialog.className = 'modal-backdrop';
    dialog.innerHTML = `
      <section class="modal" role="dialog" aria-modal="true">
        <div class="modal-header">
          <div>
            <span class="modal-eyebrow">📦 GIT INTEGRATION</span>
            <h2>Clone Repository</h2>
          </div>
          <button class="btn-icon" onclick="this.closest('.modal-backdrop').remove()">×</button>
        </div>

        <div class="git-clone-form">
          <label>Repository URL
            <input type="text" id="git-url" value="${this.escapeHtml(url)}" placeholder="https://github.com/owner/repo.git">
          </label>

          <label>Branch (optional)
            <input type="text" id="git-branch" placeholder="main" value="main">
          </label>

          <label>
            <input type="checkbox" id="git-shallow" checked>
            Shallow clone (faster for large repos)
          </label>

          <div class="progress-bar" id="git-progress" hidden>
            <div class="progress-fill"></div>
            <span class="progress-text">Cloning...</span>
          </div>
        </div>

        <div class="modal-actions">
          <button class="btn-secondary" onclick="this.closest('.modal-backdrop').remove()">Cancel</button>
          <button class="btn-primary" onclick="gitIntegration.cloneRepositoryFromDialog(this)">Clone</button>
        </div>
      </section>
    `;

    document.body.appendChild(dialog);
    document.getElementById('git-url').focus();
  }

  /**
   * Clone repository from dialog
   */
  async cloneRepositoryFromDialog(button) {
    const dialog = button.closest('.modal-backdrop');
    const url = document.getElementById('git-url').value;
    const branch = document.getElementById('git-branch').value || 'main';
    const shallow = document.getElementById('git-shallow').checked;

    button.disabled = true;

    try {
      const progressBar = document.getElementById('git-progress');
      progressBar.hidden = false;

      const result = await this.cloneRepository(url, { branch, shallow });

      // Show success
      this.showNotification(`✓ Repository cloned: ${result.name}`, 'success');
      dialog.remove();

      // Sync files to UI
      await this.syncRepositoryFiles(result.name, result.localPath);
    } catch (error) {
      this.showNotification(`✗ Clone failed: ${error.message}`, 'error');
      button.disabled = false;
    }
  }

  /**
   * Clone a repository via API
   */
  async cloneRepository(url, options = {}) {
    const response = await fetch('/api/git/clone', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url,
        branch: options.branch || 'main',
        shallow: options.shallow !== false
      })
    });

    if (!response.ok) {
      throw new Error(`Clone failed: ${response.statusText}`);
    }

    const result = await response.json();
    this.repositories.push(result);
    return result;
  }

  /**
   * Sync repository files to the UI file tree
   */
  async syncRepositoryFiles(repoName, localPath) {
    try {
      const response = await fetch(`/api/git/tree?repo=${encodeURIComponent(repoName)}`);
      if (!response.ok) throw new Error('Failed to fetch file tree');

      const fileTree = await response.json();
      this.renderFileTree(fileTree, `[${repoName}]`);
    } catch (error) {
      console.error('Failed to sync repository files:', error);
    }
  }

  /**
   * Render file tree in the UI
   */
  renderFileTree(node, prefix = '') {
    const fileTreeContainer = document.getElementById('file-tree');
    if (!fileTreeContainer) return;

    const createTreeNode = (item, level = 0) => {
      const div = document.createElement('div');
      div.className = `file-tree-item level-${level}`;
      div.dataset.path = item.path;
      div.dataset.type = item.type;

      const indent = '  '.repeat(level);
      const icon = item.type === 'directory' ? '📁' : '📄';
      const toggle = item.type === 'directory' ? '<span class="toggle">▶</span>' : '';

      div.innerHTML = `
        <div class="file-tree-entry">
          ${toggle}
          <span class="icon">${icon}</span>
          <span class="name">${this.escapeHtml(item.name)}</span>
          ${item.size ? `<span class="size">${this.formatSize(item.size)}</span>` : ''}
        </div>
      `;

      if (item.type === 'directory' && item.children) {
        const childContainer = document.createElement('div');
        childContainer.className = 'file-tree-children';
        childContainer.hidden = true;

        for (const child of item.children) {
          childContainer.appendChild(createTreeNode(child, level + 1));
        }

        div.appendChild(childContainer);
      }

      return div;
    };

    const existingRepo = fileTreeContainer.querySelector(`[data-repo="${prefix}"]`);
    if (!existingRepo) {
      const repoNode = document.createElement('div');
      repoNode.className = 'file-tree-repo';
      repoNode.dataset.repo = prefix;
      repoNode.innerHTML = `<div class="repo-name">${this.escapeHtml(prefix)}</div>`;

      const treeRoot = createTreeNode(node, 0);
      repoNode.appendChild(treeRoot);
      fileTreeContainer.appendChild(repoNode);
    }
  }

  /**
   * Handle file tree interactions
   */
  handleFileTreeClick(event) {
    const entry = event.target.closest('.file-tree-entry');
    if (!entry) return;

    const item = entry.closest('.file-tree-item');
    const toggle = entry.querySelector('.toggle');

    if (toggle) {
      event.preventDefault();
      const children = item.querySelector('.file-tree-children');
      if (children) {
        children.hidden = !children.hidden;
        toggle.textContent = children.hidden ? '▶' : '▼';
      }
    } else if (item.dataset.type === 'file') {
      this.openFile(item.dataset.path);
    }
  }

  /**
   * Open file in editor
   */
  async openFile(filePath) {
    try {
      const response = await fetch(`/api/git/file?path=${encodeURIComponent(filePath)}`);
      if (!response.ok) throw new Error('Failed to read file');

      const { content, language } = await response.json();

      // Show file editor modal
      this.showFileEditor(filePath, content, language);
    } catch (error) {
      this.showNotification(`✗ Failed to open file: ${error.message}`, 'error');
    }
  }

  /**
   * Show file editor
   */
  showFileEditor(filePath, content, language) {
    const fileName = filePath.split('/').pop();
    const dialog = document.createElement('div');
    dialog.className = 'modal-backdrop';
    dialog.innerHTML = `
      <section class="modal modal-wide" role="dialog" aria-modal="true">
        <div class="modal-header">
          <div>
            <span class="modal-eyebrow">📝 FILE EDITOR</span>
            <h2>${this.escapeHtml(fileName)}</h2>
          </div>
          <button class="btn-icon" onclick="this.closest('.modal-backdrop').remove()">×</button>
        </div>

        <div class="file-editor">
          <pre><code class="language-${language}">${this.escapeHtml(content)}</code></pre>
          <textarea class="file-content" hidden>${this.escapeHtml(content)}</textarea>
        </div>

        <div class="modal-actions">
          <button class="btn-secondary" onclick="this.closest('.modal-backdrop').remove()">Close</button>
          <button class="btn-primary" data-action="save">Save</button>
        </div>
      </section>
    `;

    document.body.appendChild(dialog);
    dialog.querySelector('[data-action="save"]').addEventListener('click', (event) => this.saveFile(filePath, event.currentTarget));
  }

  /**
   * Save file to workspace
   */
  async saveFile(filePath, button) {
    const textarea = button.closest('.modal-backdrop').querySelector('.file-content');
    const content = textarea.value;

    try {
      const response = await fetch('/api/git/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: filePath, content })
      });

      if (!response.ok) throw new Error('Failed to save file');

      this.showNotification('✓ File saved', 'success');
      button.closest('.modal-backdrop').remove();

      // Emit event for other systems
      window.dispatchEvent(new CustomEvent('workspace:file-saved', {
        detail: { path: filePath, content }
      }));
    } catch (error) {
      this.showNotification(`✗ Save failed: ${error.message}`, 'error');
    }
  }

  /**
   * Handle agent-generated files
   */
  addGeneratedFile(file) {
    const workspaceFile = {
      path: file.path,
      content: file.content,
      language: this.detectLanguage(file.path),
      createdAt: Date.now(),
      generated: true
    };

    this.workspaceFiles.push(workspaceFile);
    this.addFileToTree(workspaceFile, '[Generated]');
  }

  /**
   * Update generated file
   */
  updateGeneratedFile(file) {
    const existing = this.workspaceFiles.find(f => f.path === file.path);
    if (existing) {
      existing.content = file.content;
    }
  }

  /**
   * Add file to tree UI
   */
  addFileToTree(file, section) {
    const fileTreeContainer = document.getElementById('file-tree');
    if (!fileTreeContainer) return;

    let sectionNode = fileTreeContainer.querySelector(`[data-section="${section}"]`);
    if (!sectionNode) {
      sectionNode = document.createElement('div');
      sectionNode.className = 'file-tree-section';
      sectionNode.dataset.section = section;
      sectionNode.innerHTML = `<div class="section-name">${section}</div>`;
      fileTreeContainer.appendChild(sectionNode);
    }

    const fileNode = document.createElement('div');
    fileNode.className = 'file-tree-item file-generated';
    fileNode.dataset.path = file.path;
    fileNode.dataset.type = 'file';
    fileNode.innerHTML = `
      <div class="file-tree-entry">
        <span class="icon">✨</span>
        <span class="name">${file.path.split('/').pop()}</span>
        <span class="badge">${file.language}</span>
      </div>
    `;

    sectionNode.appendChild(fileNode);
  }

  /**
   * Load repositories from server
   */
  async loadRepositories() {
    try {
      const response = await fetch('/api/git/repos');
      if (response.ok) {
        this.repositories = await response.json();
        for (const repo of this.repositories) {
          this.syncRepositoryFiles(repo.name, repo.localPath);
        }
      }
    } catch (error) {
      console.warn('Failed to load repositories:', error);
    }
  }

  /**
   * Detect language from file extension
   */
  detectLanguage(filePath) {
    const ext = filePath.split('.').pop()?.toLowerCase();
    const languages = {
      'js': 'javascript',
      'ts': 'typescript',
      'jsx': 'jsx',
      'tsx': 'tsx',
      'py': 'python',
      'java': 'java',
      'go': 'go',
      'rs': 'rust',
      'cpp': 'cpp',
      'c': 'c',
      'cs': 'csharp',
      'rb': 'ruby',
      'php': 'php',
      'swift': 'swift',
      'kt': 'kotlin',
      'sql': 'sql',
      'html': 'html',
      'css': 'css',
      'json': 'json',
      'yaml': 'yaml',
      'yml': 'yaml',
      'md': 'markdown',
      'sh': 'bash'
    };
    return languages[ext] || 'plaintext';
  }

  /**
   * Format file size
   */
  formatSize(bytes) {
    if (bytes === 0) return '0B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + sizes[i];
  }

  /**
   * Show notification
   */
  showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
      position: fixed;
      bottom: 20px;
      right: 20px;
      padding: 12px 16px;
      background: ${type === 'success' ? '#22c55e' : type === 'error' ? '#ef4444' : '#3b82f6'};
      color: white;
      border-radius: 6px;
      font-size: 14px;
      z-index: 10000;
      animation: slideIn 0.3s ease;
    `;

    document.body.appendChild(notification);
    setTimeout(() => notification.remove(), 4000);
  }

  /**
   * Escape HTML
   */
  escapeHtml(text) {
    // Quotes too: this output also goes inside value="..." attributes (textContent -> innerHTML leaves quotes as-is).
    const entities = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
    return String(text ?? '').replace(/[&<>"']/g, ch => entities[ch]);
  }
}

// Auto-initialize
document.addEventListener('DOMContentLoaded', () => {
  window.gitIntegration = new GitIntegration();
});
