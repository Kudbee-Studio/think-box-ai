// User Preferences Service - Appearance, Behavior, Data Settings

export type Theme = 'dark' | 'light' | 'high-contrast';
export type RunHistoryRetention = 7 | 30 | 90 | 365;

export interface UserPreferences {
  // Appearance
  theme: Theme;
  fontSize: 'small' | 'normal' | 'large';
  customColors?: {
    accentPrimary?: string;
    accentSecondary?: string;
    background?: string;
    text?: string;
  };

  // Behavior
  autoRefresh: boolean;
  refreshInterval: number;
  runHistoryRetention: RunHistoryRetention;
  keyboardShortcuts: Record<string, string>;
  confirmDestructiveActions: boolean;

  // Data
  exportFormat: 'json' | 'csv' | 'markdown';
  anonymizeExports: boolean;
  localStorageOptimization: boolean;

  // Accessibility
  reducedMotion: boolean;
  highContrast: boolean;
  screenReaderMode: boolean;

  // Experimental
  betaFeatures: boolean;
}

const STORAGE_KEY = 'kudbee_preferences';
const DEFAULT_PREFERENCES: UserPreferences = {
  theme: 'dark',
  fontSize: 'normal',
  autoRefresh: true,
  refreshInterval: 5000,
  runHistoryRetention: 90,
  keyboardShortcuts: {
    'toggle-theme': 'Cmd+Shift+T',
    'focus-terminal': 'Cmd+L',
    'run-goal': 'Cmd+Enter',
    'clear-terminal': 'Cmd+K',
  },
  confirmDestructiveActions: true,
  exportFormat: 'json',
  anonymizeExports: false,
  localStorageOptimization: true,
  reducedMotion: false,
  highContrast: false,
  screenReaderMode: false,
  betaFeatures: false,
};

export class UserPreferencesService {
  private preferences: UserPreferences;
  private listeners: Set<(prefs: UserPreferences) => void> = new Set();

  constructor() {
    this.preferences = this.loadFromStorage();
  }

  // Get all preferences
  getAll(): UserPreferences {
    return { ...this.preferences };
  }

  // Get specific preference
  get<K extends keyof UserPreferences>(key: K): UserPreferences[K] {
    return this.preferences[key];
  }

  // Update preference
  async set<K extends keyof UserPreferences>(key: K, value: UserPreferences[K]): Promise<void> {
    this.preferences[key] = value;
    this.applyPreferences();
    this.saveToStorage();
    this.notifyListeners();
  }

  // Update multiple preferences
  async update(partial: Partial<UserPreferences>): Promise<void> {
    this.preferences = { ...this.preferences, ...partial };
    this.applyPreferences();
    this.saveToStorage();
    this.notifyListeners();
  }

  // Reset to defaults
  async reset(): Promise<void> {
    this.preferences = { ...DEFAULT_PREFERENCES };
    this.applyPreferences();
    this.saveToStorage();
    this.notifyListeners();
  }

  // Export preferences as JSON
  async exportJSON(): Promise<string> {
    return JSON.stringify(this.preferences, null, 2);
  }

  // Import preferences from JSON
  async importJSON(json: string): Promise<void> {
    try {
      const imported = JSON.parse(json);
      this.preferences = { ...DEFAULT_PREFERENCES, ...imported };
      this.applyPreferences();
      this.saveToStorage();
      this.notifyListeners();
    } catch (err) {
      throw new Error(`Failed to import preferences: ${err}`);
    }
  }

  // Apply preferences to DOM/environment
  private applyPreferences(): void {
    const root = document.documentElement;

    // Theme
    root.setAttribute('data-theme', this.preferences.theme);
    if (this.preferences.customColors) {
      Object.entries(this.preferences.customColors).forEach(([key, value]) => {
        if (value) {
          root.style.setProperty(`--user-${key}`, value);
        }
      });
    }

    // Font size
    root.style.fontSize = this.getFontSize();

    // Accessibility
    if (this.preferences.reducedMotion) {
      root.classList.add('reduce-motion');
    } else {
      root.classList.remove('reduce-motion');
    }

    if (this.preferences.highContrast) {
      root.classList.add('high-contrast');
    } else {
      root.classList.remove('high-contrast');
    }

    if (this.preferences.screenReaderMode) {
      root.setAttribute('aria-mode', 'screen-reader');
    } else {
      root.removeAttribute('aria-mode');
    }
  }

  // Subscribe to changes
  onChange(callback: (prefs: UserPreferences) => void): () => void {
    this.listeners.add(callback);
    return () => {
      this.listeners.delete(callback);
    };
  }

  // Get keyboard shortcut
  getShortcut(action: string): string | undefined {
    return this.preferences.keyboardShortcuts[action];
  }

  // Update keyboard shortcut
  async updateShortcut(action: string, keys: string): Promise<void> {
    this.preferences.keyboardShortcuts[action] = keys;
    this.saveToStorage();
    this.notifyListeners();
  }

  // Private helpers
  private notifyListeners(): void {
    this.listeners.forEach((listener) => {
      listener(this.getAll());
    });
  }

  private saveToStorage(): void {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(this.preferences));
    } catch (err) {
      console.error('Failed to save preferences:', err);
    }
  }

  private loadFromStorage(): UserPreferences {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        return { ...DEFAULT_PREFERENCES, ...JSON.parse(stored) };
      }
    } catch (err) {
      console.error('Failed to load preferences:', err);
    }
    return { ...DEFAULT_PREFERENCES };
  }

  private getFontSize(): string {
    const map = {
      small: '12px',
      normal: '13px',
      large: '14px',
    };
    return map[this.preferences.fontSize];
  }
}

// Global instance
let service: UserPreferencesService | null = null;

export function getUserPreferencesService(): UserPreferencesService {
  if (!service) {
    service = new UserPreferencesService();
  }
  return service;
}
