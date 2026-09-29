// kudbEE Memory Graph — Semantic knowledge graph visualization

class MemoryGraph {
  constructor() {
    this.memories = [];
    this.nodes = [];
    this.edges = [];
    this.selectedNode = null;
    this.zoomLevel = 1;
    this.panX = 0;
    this.panY = 0;

    this.initialize();
  }

  initialize() {
    this.setupCanvasListener();
    this.loadMemoriesFromUI();
  }

  setupCanvasListener() {
    const canvas = document.getElementById('memory-graph-canvas');
    if (!canvas) return;

    canvas.addEventListener('click', (e) => this.handleCanvasClick(e));
    window.addEventListener('memory:updated', (e) => {
      this.memories = e.detail.memories || [];
      this.buildGraph();
      this.render();
    });
  }

  loadMemoriesFromUI() {
    const memoryItems = document.querySelectorAll('.memory-item');
    if (!memoryItems || memoryItems.length === 0) {
      this.memories = [];
      return;
    }

    this.memories = Array.from(memoryItems).map((el, idx) => ({
      id: `mem-${idx}`,
      title: el.querySelector('strong')?.textContent || 'Untitled',
      layer: el.querySelector('.memory-layer')?.textContent?.trim() || 'org',
      tags: el.querySelector('small')?.textContent?.split(',') || [],
      x: Math.random() * 400,
      y: Math.random() * 300
    }));

    this.buildGraph();
  }

  buildGraph() {
    this.nodes = this.memories.map(mem => ({
      id: mem.id,
      label: mem.title.substring(0, 20),
      layer: mem.layer,
      x: mem.x,
      y: mem.y,
      radius: 20 + (mem.tags.length * 3)
    }));

    // Create edges based on tag similarity
    this.edges = [];
    for (let i = 0; i < this.nodes.length; i++) {
      for (let j = i + 1; j < this.nodes.length; j++) {
        const mem1 = this.memories[i];
        const mem2 = this.memories[j];
        const commonTags = mem1.tags.filter(tag => mem2.tags.includes(tag)).length;

        if (commonTags > 0) {
          this.edges.push({
            source: this.nodes[i].id,
            target: this.nodes[j].id,
            weight: commonTags,
            strength: Math.min(commonTags / 3, 1)
          });
        }
      }
    }
  }

  render() {
    this.loadMemoriesFromUI();
    const canvas = document.getElementById('memory-graph-canvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.fillStyle = '#0a0f1f';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Draw edges
    ctx.strokeStyle = 'rgba(6, 182, 212, 0.2)';
    ctx.lineWidth = 1;
    this.edges.forEach(edge => {
      const source = this.nodes.find(n => n.id === edge.source);
      const target = this.nodes.find(n => n.id === edge.target);
      if (source && target) {
        ctx.beginPath();
        ctx.moveTo(source.x, source.y);
        ctx.lineTo(target.x, target.y);
        ctx.stroke();
      }
    });

    // Draw nodes
    this.nodes.forEach(node => {
      const color = this.getLayerColor(node.layer);
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
      ctx.fill();

      // Node label
      ctx.fillStyle = '#f8fafc';
      ctx.font = '11px monospace';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(node.label, node.x, node.y);
    });
  }

  getLayerColor(layer) {
    const colors = {
      'verified': 'rgba(16, 185, 129, 0.7)',
      'org': 'rgba(245, 158, 11, 0.7)',
      'task': 'rgba(14, 165, 233, 0.7)',
      'session': 'rgba(139, 92, 246, 0.7)'
    };
    return colors[layer] || 'rgba(6, 182, 212, 0.7)';
  }

  handleCanvasClick(e) {
    const canvas = document.getElementById('memory-graph-canvas');
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    // Find clicked node
    for (const node of this.nodes) {
      const dist = Math.sqrt((x - node.x) ** 2 + (y - node.y) ** 2);
      if (dist <= node.radius) {
        this.selectNode(node);
        return;
      }
    }
  }

  selectNode(node) {
    this.selectedNode = node;
    const memory = this.memories.find(m => m.id === node.id);
    this.showNodeDetails(memory);
  }

  showNodeDetails(memory) {
    const details = document.getElementById('graph-details');
    if (!details) return;

    details.innerHTML = `
      <div class="graph-detail-header">
        <h4>${this.escapeHtml(memory.title)}</h4>
        <span class="memory-layer ${this.escapeHtml(memory.layer)}">${this.escapeHtml(memory.layer)}</span>
      </div>
      <div class="graph-detail-content">
        <p><strong>Tags:</strong> ${this.escapeHtml(memory.tags.join(', ') || 'None')}</p>
        <p><strong>Connected memories:</strong> ${this.findConnectedMemories(memory.id).length}</p>
        <button class="btn-secondary" onclick="memoryGraph.expandNode('${memory.id}')">Expand</button>
      </div>
    `;
  }

  findConnectedMemories(memoryId) {
    return this.edges.filter(e => e.source === memoryId || e.target === memoryId);
  }

  expandNode(memoryId) {
    console.log('Expanding node:', memoryId);
    // Could trigger a detailed view modal
  }

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text ?? '';
    return div.innerHTML;
  }

  zoom(factor) {
    this.zoomLevel *= factor;
    this.render();
  }

  pan(dx, dy) {
    this.panX += dx;
    this.panY += dy;
    this.render();
  }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  window.memoryGraph = new MemoryGraph();
});
