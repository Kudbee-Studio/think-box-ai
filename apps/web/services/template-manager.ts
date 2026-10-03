// Template Manager - Workflow template creation and management

export interface ToolCall {
  name: string;
  args: Record<string, any>;
}

export interface WorkflowTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  tags: string[];
  tools: ToolCall[];
  createdAt: number;
  updatedAt: number;
  isBuiltIn: boolean;
  isPublic: boolean;
  author?: string;
  usage: number;
  rating: number;
}

export class TemplateManager {
  private templates: Map<string, WorkflowTemplate> = new Map();

  constructor() {
    this.initializeBuiltInTemplates();
    this.loadFromStorage();
  }

  // Create new template
  createTemplate(
    template: Omit<WorkflowTemplate, 'id' | 'createdAt' | 'updatedAt' | 'isBuiltIn' | 'usage' | 'rating'>
  ): WorkflowTemplate {
    const id = this.generateId();
    const now = Date.now();

    const newTemplate: WorkflowTemplate = {
      ...template,
      id,
      createdAt: now,
      updatedAt: now,
      isBuiltIn: false,
      usage: 0,
      rating: 0,
    };

    this.templates.set(id, newTemplate);
    this.saveToStorage();
    return newTemplate;
  }

  // Get template
  getTemplate(id: string): WorkflowTemplate | null {
    return this.templates.get(id) || null;
  }

  // List templates
  listTemplates(filters?: {
    category?: string;
    tags?: string[];
    isPublic?: boolean;
    search?: string;
  }): WorkflowTemplate[] {
    let results = Array.from(this.templates.values());

    if (filters?.category) {
      results = results.filter((t) => t.category === filters.category);
    }

    if (filters?.tags && filters.tags.length > 0) {
      results = results.filter((t) =>
        filters.tags!.some((tag) => t.tags.includes(tag))
      );
    }

    if (filters?.isPublic !== undefined) {
      results = results.filter((t) => t.isPublic === filters.isPublic);
    }

    if (filters?.search) {
      const searchLower = filters.search.toLowerCase();
      results = results.filter(
        (t) =>
          t.name.toLowerCase().includes(searchLower) ||
          t.description.toLowerCase().includes(searchLower)
      );
    }

    return results.sort((a, b) => b.updatedAt - a.updatedAt);
  }

  // Update template
  updateTemplate(id: string, updates: Partial<WorkflowTemplate>): WorkflowTemplate | null {
    const template = this.templates.get(id);
    if (!template || template.isBuiltIn) {
      return null;
    }

    const updated = {
      ...template,
      ...updates,
      id: template.id,
      createdAt: template.createdAt,
      updatedAt: Date.now(),
      isBuiltIn: template.isBuiltIn,
    };

    this.templates.set(id, updated);
    this.saveToStorage();
    return updated;
  }

  // Record template usage
  recordUsage(id: string): void {
    const template = this.templates.get(id);
    if (template) {
      template.usage++;
      template.updatedAt = Date.now();
      this.saveToStorage();
    }
  }

  // Rate template
  rateTemplate(id: string, rating: number): void {
    const template = this.templates.get(id);
    if (template && rating >= 0 && rating <= 5) {
      template.rating = rating;
      template.updatedAt = Date.now();
      this.saveToStorage();
    }
  }

  // Delete template
  deleteTemplate(id: string): boolean {
    const template = this.templates.get(id);
    if (!template || template.isBuiltIn) {
      return false;
    }

    this.templates.delete(id);
    this.saveToStorage();
    return true;
  }

  // Duplicate template
  duplicateTemplate(id: string, newName?: string): WorkflowTemplate | null {
    const original = this.templates.get(id);
    if (!original) return null;

    return this.createTemplate({
      name: newName || `${original.name} (Copy)`,
      description: original.description,
      category: original.category,
      tags: [...original.tags],
      tools: JSON.parse(JSON.stringify(original.tools)),
      isPublic: false,
      author: original.author,
    });
  }

  // Get categories
  getCategories(): string[] {
    const categories = new Set<string>();
    this.templates.forEach((t) => categories.add(t.category));
    return Array.from(categories).sort();
  }

  // Get tags
  getTags(): { tag: string; count: number }[] {
    const tags = new Map<string, number>();
    this.templates.forEach((t) => {
      t.tags.forEach((tag) => {
        tags.set(tag, (tags.get(tag) || 0) + 1);
      });
    });

    return Array.from(tags.entries())
      .map(([tag, count]) => ({ tag, count }))
      .sort((a, b) => b.count - a.count);
  }

  // Export template as JSON
  exportTemplate(id: string): string {
    const template = this.templates.get(id);
    if (!template) throw new Error(`Template ${id} not found`);
    return JSON.stringify(template, null, 2);
  }

  // Import template from JSON
  importTemplate(json: string): WorkflowTemplate {
    const data = JSON.parse(json);
    const template = this.createTemplate({
      name: data.name,
      description: data.description,
      category: data.category,
      tags: data.tags,
      tools: data.tools,
      isPublic: false,
      author: data.author,
    });
    return template;
  }

  // Private helpers
  private initializeBuiltInTemplates(): void {
    const builtInTemplates: WorkflowTemplate[] = [
      {
        id: 'template-code-analysis',
        name: 'Code Analysis',
        description: 'Analyze code for issues and improvements',
        category: 'Development',
        tags: ['code', 'analysis', 'review'],
        tools: [
          { name: 'file_read', args: { path: '.' } },
          { name: 'analyze', args: { type: 'code-quality' } },
        ],
        createdAt: Date.now(),
        updatedAt: Date.now(),
        isBuiltIn: true,
        isPublic: true,
        usage: 0,
        rating: 5,
      },
      {
        id: 'template-documentation',
        name: 'Generate Documentation',
        description: 'Create documentation for codebase',
        category: 'Documentation',
        tags: ['docs', 'generation'],
        tools: [
          { name: 'file_read', args: { path: '.' } },
          { name: 'generate', args: { type: 'markdown-docs' } },
        ],
        createdAt: Date.now(),
        updatedAt: Date.now(),
        isBuiltIn: true,
        isPublic: true,
        usage: 0,
        rating: 5,
      },
      {
        id: 'template-testing',
        name: 'Run Test Suite',
        description: 'Execute tests and generate report',
        category: 'Quality',
        tags: ['testing', 'ci'],
        tools: [
          { name: 'shell_exec', args: { command: 'npm test' } },
          { name: 'write_file', args: { path: 'test-report.md' } },
        ],
        createdAt: Date.now(),
        updatedAt: Date.now(),
        isBuiltIn: true,
        isPublic: true,
        usage: 0,
        rating: 5,
      },
    ];

    builtInTemplates.forEach((template) => {
      this.templates.set(template.id, template);
    });
  }

  private generateId(): string {
    return 'template-' + Math.random().toString(36).substring(2, 15);
  }

  private saveToStorage(): void {
    try {
      const templates = Array.from(this.templates.values()).filter(
        (t) => !t.isBuiltIn
      );
      localStorage.setItem('kudbee_templates', JSON.stringify(templates));
    } catch (err) {
      console.error('Failed to save templates:', err);
    }
  }

  private loadFromStorage(): void {
    try {
      const stored = localStorage.getItem('kudbee_templates');
      if (stored) {
        const templates = JSON.parse(stored);
        templates.forEach((template: WorkflowTemplate) => {
          this.templates.set(template.id, template);
        });
      }
    } catch (err) {
      console.error('Failed to load templates:', err);
    }
  }
}

// Global instance
let templateManager: TemplateManager | null = null;

export function getTemplateManager(): TemplateManager {
  if (!templateManager) {
    templateManager = new TemplateManager();
  }
  return templateManager;
}
