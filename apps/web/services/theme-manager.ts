// Theme Manager - Enterprise Color Themes

export interface ThemeDefinition {
  id: string;
  name: string;
  description: string;
  isDark: boolean;
  colors: {
    bgPrimary: string;
    bgSecondary: string;
    bgTertiary: string;
    textPrimary: string;
    textSecondary: string;
    textMuted: string;
    accentPrimary: string;
    accentSecondary: string;
    accentLight: string;
    success: string;
    warning: string;
    error: string;
    info: string;
    borderLight: string;
    borderMedium: string;
    borderDark: string;
  };
}

export const THEMES: Record<string, ThemeDefinition> = {
  dark: {
    id: 'dark',
    name: 'Dark Professional',
    description: 'Premium dark theme with cyan accents',
    isDark: true,
    colors: {
      bgPrimary: '#0a0f1f',
      bgSecondary: '#141b2e',
      bgTertiary: '#1f2a3e',
      textPrimary: '#f8fafc',
      textSecondary: '#cbd5e1',
      textMuted: '#94a3b8',
      accentPrimary: '#06b6d4',
      accentSecondary: '#0ea5e9',
      accentLight: '#22d3ee',
      success: '#10b981',
      warning: '#f59e0b',
      error: '#ef4444',
      info: '#3b82f6',
      borderLight: '#1f3a4f',
      borderMedium: '#2a4a63',
      borderDark: '#0a1218',
    },
  },

  light: {
    id: 'light',
    name: 'Light Professional',
    description: 'Clean light theme with blue accents',
    isDark: false,
    colors: {
      bgPrimary: '#ffffff',
      bgSecondary: '#f8fafc',
      bgTertiary: '#f1f5f9',
      textPrimary: '#0f172a',
      textSecondary: '#475569',
      textMuted: '#78716c',
      accentPrimary: '#0284c7',
      accentSecondary: '#0369a1',
      accentLight: '#38bdf8',
      success: '#16a34a',
      warning: '#ea580c',
      error: '#dc2626',
      info: '#2563eb',
      borderLight: '#e2e8f0',
      borderMedium: '#cbd5e1',
      borderDark: '#94a3b8',
    },
  },

  'high-contrast': {
    id: 'high-contrast',
    name: 'High Contrast',
    description: 'WCAG AAA compliant, maximum contrast',
    isDark: true,
    colors: {
      bgPrimary: '#000000',
      bgSecondary: '#1a1a1a',
      bgTertiary: '#2d2d2d',
      textPrimary: '#ffffff',
      textSecondary: '#e6e6e6',
      textMuted: '#cccccc',
      accentPrimary: '#ffff00',
      accentSecondary: '#00ffff',
      accentLight: '#00ff00',
      success: '#00ff00',
      warning: '#ffff00',
      error: '#ff0000',
      info: '#00ccff',
      borderLight: '#ffffff',
      borderMedium: '#e6e6e6',
      borderDark: '#999999',
    },
  },
};

export class ThemeManager {
  private currentThemeId: string = 'dark';
  private customThemes: Map<string, ThemeDefinition> = new Map();
  private listeners: Set<(themeId: string) => void> = new Set();

  constructor() {
    this.loadFromStorage();
    this.applyTheme(this.currentThemeId);
  }

  // Get current theme
  getCurrentTheme(): ThemeDefinition {
    return this.getTheme(this.currentThemeId)!;
  }

  // Get theme by ID
  getTheme(id: string): ThemeDefinition | undefined {
    return THEMES[id] || this.customThemes.get(id);
  }

  // List all available themes
  listThemes(): ThemeDefinition[] {
    return [
      ...Object.values(THEMES),
      ...Array.from(this.customThemes.values()),
    ];
  }

  // Apply theme
  async applyTheme(themeId: string): Promise<void> {
    const theme = this.getTheme(themeId);
    if (!theme) {
      throw new Error(`Theme ${themeId} not found`);
    }

    this.currentThemeId = themeId;
    this.updateDOM(theme);
    this.saveToStorage();
    this.notifyListeners();
  }

  // Create custom theme
  async createCustomTheme(theme: ThemeDefinition): Promise<void> {
    this.customThemes.set(theme.id, theme);
    this.saveCustomThemesToStorage();
  }

  // Delete custom theme
  async deleteCustomTheme(id: string): Promise<void> {
    if (THEMES[id]) {
      throw new Error('Cannot delete built-in themes');
    }
    this.customThemes.delete(id);
    if (this.currentThemeId === id) {
      await this.applyTheme('dark');
    }
    this.saveCustomThemesToStorage();
  }

  // Subscribe to theme changes
  onChange(callback: (themeId: string) => void): () => void {
    this.listeners.add(callback);
    return () => {
      this.listeners.delete(callback);
    };
  }

  // Toggle theme
  async toggleTheme(): Promise<void> {
    const theme = this.getCurrentTheme();
    const nextThemeId = theme.isDark ? 'light' : 'dark';
    await this.applyTheme(nextThemeId);
  }

  // Private helpers
  private updateDOM(theme: ThemeDefinition): void {
    const root = document.documentElement;

    // Set CSS variables
    Object.entries(theme.colors).forEach(([key, value]) => {
      const cssVar = `--theme-${key.replace(/([A-Z])/g, '-$1').toLowerCase()}`;
      root.style.setProperty(cssVar, value);
    });

    // Set theme attribute
    root.setAttribute('data-theme', theme.id);

    // Dark mode class
    if (theme.isDark) {
      root.classList.add('dark-theme');
      root.classList.remove('light-theme');
    } else {
      root.classList.add('light-theme');
      root.classList.remove('dark-theme');
    }
  }

  private notifyListeners(): void {
    this.listeners.forEach((listener) => {
      listener(this.currentThemeId);
    });
  }

  private saveToStorage(): void {
    try {
      localStorage.setItem('kudbee_current_theme', this.currentThemeId);
    } catch (err) {
      console.error('Failed to save theme:', err);
    }
  }

  private saveCustomThemesToStorage(): void {
    try {
      const customThemes = Array.from(this.customThemes.values());
      localStorage.setItem('kudbee_custom_themes', JSON.stringify(customThemes));
    } catch (err) {
      console.error('Failed to save custom themes:', err);
    }
  }

  private loadFromStorage(): void {
    try {
      const stored = localStorage.getItem('kudbee_current_theme');
      if (stored && this.getTheme(stored)) {
        this.currentThemeId = stored;
      }

      const customStored = localStorage.getItem('kudbee_custom_themes');
      if (customStored) {
        const customThemes = JSON.parse(customStored);
        customThemes.forEach((theme: ThemeDefinition) => {
          this.customThemes.set(theme.id, theme);
        });
      }
    } catch (err) {
      console.error('Failed to load themes:', err);
    }
  }
}

// Global instance
let themeManager: ThemeManager | null = null;

export function getThemeManager(): ThemeManager {
  if (!themeManager) {
    themeManager = new ThemeManager();
  }
  return themeManager;
}

// Keyboard shortcut: Cmd/Ctrl+Shift+T to toggle theme
if (typeof window !== 'undefined') {
  window.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.code === 'KeyT') {
      e.preventDefault();
      getThemeManager().toggleTheme();
    }
  });
}
