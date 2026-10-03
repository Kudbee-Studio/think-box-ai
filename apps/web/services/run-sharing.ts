// Run Sharing Service - Share run snapshots and manage sharing links

export interface RunShareLink {
  id: string;
  runId: string;
  createdAt: number;
  expiresAt?: number;
  accessType: 'view-only' | 'anonymous' | 'comment';
  password?: string;
  downloadAllowed: boolean;
}

export interface RunSnapshot {
  id: string;
  timestamp: number;
  runId: string;
  goal: string;
  model: string;
  duration: number;
  success: boolean;
  messages: Array<{
    role: 'user' | 'assistant' | 'tool';
    content: string;
    timestamp: number;
  }>;
  metadata: Record<string, any>;
  anonymized: boolean;
}

// Exported HTML is opened from disk and shared: every run-derived value (goal, model, agent output) is untrusted text.
function escapeHtml(value: unknown): string {
  return String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] as string);
}

export class RunSharingService {
  private shareLinks: Map<string, RunShareLink> = new Map();
  private snapshots: Map<string, RunSnapshot> = new Map();

  constructor() {
    this.loadFromStorage();
  }

  // Create a share link for a run
  createShareLink(
    runId: string,
    options: {
      expiresIn?: number;
      accessType?: 'view-only' | 'anonymous' | 'comment';
      password?: string;
      downloadAllowed?: boolean;
    } = {}
  ): RunShareLink {
    const linkId = this.generateId();
    const link: RunShareLink = {
      id: linkId,
      runId,
      createdAt: Date.now(),
      expiresAt: options.expiresIn
        ? Date.now() + options.expiresIn
        : undefined,
      accessType: options.accessType || 'view-only',
      password: options.password,
      downloadAllowed: options.downloadAllowed !== false,
    };

    this.shareLinks.set(linkId, link);
    this.saveToStorage();
    return link;
  }

  // Get share link
  getShareLink(linkId: string): RunShareLink | null {
    const link = this.shareLinks.get(linkId);
    if (!link) return null;

    // Check if link is expired
    if (link.expiresAt && Date.now() > link.expiresAt) {
      this.shareLinks.delete(linkId);
      this.saveToStorage();
      return null;
    }

    return link;
  }

  // List share links for a run
  getShareLinksForRun(runId: string): RunShareLink[] {
    return Array.from(this.shareLinks.values()).filter(
      (link) => link.runId === runId && (!link.expiresAt || link.expiresAt > Date.now())
    );
  }

  // Revoke a share link
  revokeShareLink(linkId: string): boolean {
    const deleted = this.shareLinks.delete(linkId);
    if (deleted) {
      this.saveToStorage();
    }
    return deleted;
  }

  // Create run snapshot
  createSnapshot(run: Omit<RunSnapshot, 'id' | 'timestamp'>): RunSnapshot {
    const snapshot: RunSnapshot = {
      ...run,
      id: this.generateId(),
      timestamp: Date.now(),
    };

    this.snapshots.set(snapshot.id, snapshot);
    this.saveToStorage();
    return snapshot;
  }

  // Get snapshot
  getSnapshot(snapshotId: string): RunSnapshot | null {
    return this.snapshots.get(snapshotId) || null;
  }

  // Export snapshot as JSON
  exportJSON(snapshotId: string): string {
    const snapshot = this.getSnapshot(snapshotId);
    if (!snapshot) throw new Error(`Snapshot ${snapshotId} not found`);

    return JSON.stringify(this.sanitizeSnapshot(snapshot), null, 2);
  }

  // Export snapshot as Markdown
  exportMarkdown(snapshotId: string): string {
    const snapshot = this.getSnapshot(snapshotId);
    if (!snapshot) throw new Error(`Snapshot ${snapshotId} not found`);

    let md = '# Run Report\n\n';
    md += `**Generated:** ${new Date(snapshot.timestamp).toISOString()}\n\n`;
    md += '## Summary\n\n';
    md += `- **Goal:** ${snapshot.goal}\n`;
    md += `- **Model:** ${snapshot.model}\n`;
    md += `- **Duration:** ${Math.round(snapshot.duration / 1000)}s\n`;
    md += `- **Status:** ${snapshot.success ? '✅ Success' : '❌ Failed'}\n\n`;

    md += '## Messages\n\n';
    snapshot.messages.forEach((msg) => {
      const time = new Date(msg.timestamp).toLocaleTimeString();
      md += `### ${msg.role.toUpperCase()} (${time})\n\n`;
      md += `${msg.content}\n\n`;
    });

    return md;
  }

  // Export snapshot as HTML
  exportHTML(snapshotId: string): string {
    const snapshot = this.getSnapshot(snapshotId);
    if (!snapshot) throw new Error(`Snapshot ${snapshotId} not found`);

    let html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Run Report - ${escapeHtml(snapshot.goal)}</title>
  <style>
    body { font-family: system-ui, sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px; }
    .summary { background: #f0f9ff; padding: 16px; border-radius: 8px; margin-bottom: 20px; }
    .message { margin-bottom: 20px; padding: 12px; border-left: 4px solid #06b6d4; }
    .message.assistant { background: #f0f9ff; border-left-color: #0ea5e9; }
    .message.tool { background: #f5f3ff; border-left-color: #a855f7; }
    .time { font-size: 0.85em; color: #666; }
  </style>
</head>
<body>
  <h1>Run Report</h1>
  <div class="summary">
    <p><strong>Goal:</strong> ${escapeHtml(snapshot.goal)}</p>
    <p><strong>Model:</strong> ${escapeHtml(snapshot.model)}</p>
    <p><strong>Duration:</strong> ${Math.round(snapshot.duration / 1000)}s</p>
    <p><strong>Status:</strong> ${snapshot.success ? '✅ Success' : '❌ Failed'}</p>
    <p><strong>Generated:</strong> ${new Date(snapshot.timestamp).toISOString()}</p>
  </div>

  <h2>Messages</h2>
`;

    snapshot.messages.forEach((msg) => {
      const time = new Date(msg.timestamp).toLocaleTimeString();
      html += `<div class="message ${escapeHtml(msg.role)}">
    <strong>${escapeHtml(msg.role.toUpperCase())}</strong>
    <span class="time">${escapeHtml(time)}</span>
    <p>${escapeHtml(msg.content)}</p>
  </div>
`;
    });

    html += `</body>
</html>`;

    return html;
  }

  // Delete snapshot
  deleteSnapshot(snapshotId: string): boolean {
    const deleted = this.snapshots.delete(snapshotId);
    if (deleted) {
      this.saveToStorage();
    }
    return deleted;
  }

  // Get all snapshots
  getAllSnapshots(): RunSnapshot[] {
    return Array.from(this.snapshots.values()).sort(
      (a, b) => b.timestamp - a.timestamp
    );
  }

  // Private helpers
  private sanitizeSnapshot(snapshot: RunSnapshot): RunSnapshot {
    if (!snapshot.anonymized) {
      return snapshot;
    }

    // Remove sensitive data
    return {
      ...snapshot,
      messages: snapshot.messages.map((msg) => ({
        ...msg,
        content: '[REDACTED]',
      })),
    };
  }

  private generateId(): string {
    return Math.random().toString(36).substring(2, 15);
  }

  private saveToStorage(): void {
    try {
      const data = {
        links: Array.from(this.shareLinks.entries()),
        snapshots: Array.from(this.snapshots.entries()),
      };
      localStorage.setItem('kudbee_sharing', JSON.stringify(data));
    } catch (err) {
      console.error('Failed to save sharing data:', err);
    }
  }

  private loadFromStorage(): void {
    try {
      const stored = localStorage.getItem('kudbee_sharing');
      if (stored) {
        const data = JSON.parse(stored);
        this.shareLinks = new Map(data.links);
        this.snapshots = new Map(data.snapshots);
      }
    } catch (err) {
      console.error('Failed to load sharing data:', err);
    }
  }
}

// Global instance
let runSharingService: RunSharingService | null = null;

export function getRunSharingService(): RunSharingService {
  if (!runSharingService) {
    runSharingService = new RunSharingService();
  }
  return runSharingService;
}
