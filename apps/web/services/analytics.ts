// Analytics Service - Run metrics aggregation and KPI calculation

export interface RunMetrics {
  id: string;
  timestamp: number;
  duration: number;
  success: boolean;
  model: string;
  tokensSaved?: number;
  toolCount: number;
  toolDuration: number;
  approvalWaitTime: number;
  errorCategory?: string;
}

export interface KPICard {
  title: string;
  value: string | number;
  subtitle?: string;
  trend?: number;
  icon: string;
  color: 'success' | 'warning' | 'error' | 'info';
}

export interface TimeSeriesPoint {
  timestamp: number;
  value: number;
  label: string;
}

export interface ModelDistribution {
  model: string;
  count: number;
  percentage: number;
  avgDuration: number;
}

export interface FailureAnalysis {
  category: string;
  count: number;
  percentage: number;
  examples: string[];
}

export class AnalyticsService {
  private runs: RunMetrics[] = [];

  constructor() {
    this.loadFromStorage();
  }

  // Add run metrics
  addRun(metrics: RunMetrics): void {
    this.runs.push(metrics);
    this.saveToStorage();
  }

  // Get KPI cards for dashboard
  getKPICards(): KPICard[] {
    if (this.runs.length === 0) {
      return [
        {
          title: 'Total Runs',
          value: 0,
          icon: '🏃',
          color: 'info',
        },
        {
          title: 'Success Rate',
          value: '0%',
          icon: '✓',
          color: 'success',
        },
        {
          title: 'Avg Latency',
          value: '0ms',
          icon: '⏱',
          color: 'info',
        },
        {
          title: 'Tokens Saved',
          value: 0,
          icon: '💾',
          color: 'success',
        },
      ];
    }

    const totalRuns = this.runs.length;
    const successCount = this.runs.filter((r) => r.success).length;
    const successRate = Math.round((successCount / totalRuns) * 100);
    const avgDuration = Math.round(
      this.runs.reduce((sum, r) => sum + r.duration, 0) / totalRuns
    );
    const totalTokensSaved = this.runs.reduce(
      (sum, r) => sum + (r.tokensSaved || 0),
      0
    );

    // Calculate trend (compare last 5 runs to previous 5)
    const recent = this.runs.slice(-5);
    const previous = this.runs.slice(-10, -5);
    const recentRate =
      recent.filter((r) => r.success).length / Math.max(recent.length, 1);
    const previousRate =
      previous.filter((r) => r.success).length / Math.max(previous.length, 1);
    const trend = Math.round((recentRate - previousRate) * 100);

    return [
      {
        title: 'Total Runs',
        value: totalRuns,
        icon: '🏃',
        color: 'info',
        trend: totalRuns > 0 ? 100 : 0,
      },
      {
        title: 'Success Rate',
        value: `${successRate}%`,
        icon: '✓',
        color: successRate >= 90 ? 'success' : 'warning',
        trend,
      },
      {
        title: 'Avg Latency',
        value: `${avgDuration}ms`,
        icon: '⏱',
        color: avgDuration < 5000 ? 'success' : 'warning',
      },
      {
        title: 'Tokens Saved',
        value: totalTokensSaved,
        icon: '💾',
        color: 'success',
      },
    ];
  }

  // Get time-series data for runs per hour
  getRunsPerHour(): TimeSeriesPoint[] {
    const hours = new Map<number, number>();

    this.runs.forEach((run) => {
      const hour = Math.floor(run.timestamp / (60 * 60 * 1000));
      hours.set(hour, (hours.get(hour) || 0) + 1);
    });

    return Array.from(hours.entries())
      .sort((a, b) => a[0] - b[0])
      .map(([hour, count]) => ({
        timestamp: hour * 60 * 60 * 1000,
        value: count,
        label: new Date(hour * 60 * 60 * 1000).toLocaleTimeString([], {
          hour: '2-digit',
          minute: '2-digit',
        }),
      }));
  }

  // Get latency trend data
  getLatencyTrend(): TimeSeriesPoint[] {
    return this.runs.slice(-20).map((run) => ({
      timestamp: run.timestamp,
      value: run.duration,
      label: new Date(run.timestamp).toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
      }),
    }));
  }

  // Get model distribution
  getModelDistribution(): ModelDistribution[] {
    const models = new Map<string, { count: number; totalDuration: number }>();

    this.runs.forEach((run) => {
      const model = models.get(run.model) || {
        count: 0,
        totalDuration: 0,
      };
      model.count++;
      model.totalDuration += run.duration;
      models.set(run.model, model);
    });

    const total = this.runs.length;

    return Array.from(models.entries())
      .map(([model, data]) => ({
        model,
        count: data.count,
        percentage: Math.round((data.count / total) * 100),
        avgDuration: Math.round(data.totalDuration / data.count),
      }))
      .sort((a, b) => b.count - a.count);
  }

  // Get failure analysis
  getFailureAnalysis(): FailureAnalysis[] {
    const failures = new Map<string, string[]>();

    this.runs
      .filter((r) => !r.success)
      .forEach((run) => {
        const category = run.errorCategory || 'Unknown';
        if (!failures.has(category)) {
          failures.set(category, []);
        }
        failures.get(category)!.push(run.id);
      });

    const total = this.runs.filter((r) => !r.success).length;

    return Array.from(failures.entries())
      .map(([category, ids]) => ({
        category,
        count: ids.length,
        percentage: Math.round((ids.length / Math.max(total, 1)) * 100),
        examples: ids.slice(0, 3),
      }))
      .sort((a, b) => b.count - a.count);
  }

  // Compare this week vs last week
  getWeekComparison(): {
    thisWeek: number;
    lastWeek: number;
    improvement: number;
  } {
    const now = Date.now();
    const oneWeek = 7 * 24 * 60 * 60 * 1000;

    const thisWeek = this.runs.filter(
      (r) => r.timestamp > now - oneWeek
    ).length;
    const lastWeek = this.runs.filter(
      (r) =>
        r.timestamp > now - 2 * oneWeek && r.timestamp <= now - oneWeek
    ).length;

    const improvement =
      lastWeek > 0 ? Math.round(((thisWeek - lastWeek) / lastWeek) * 100) : 0;

    return { thisWeek, lastWeek, improvement };
  }

  // Get all runs
  getAllRuns(): RunMetrics[] {
    return [...this.runs];
  }

  // Get runs by date range
  getRunsByDateRange(start: number, end: number): RunMetrics[] {
    return this.runs.filter((r) => r.timestamp >= start && r.timestamp <= end);
  }

  // Clear analytics data
  clear(): void {
    this.runs = [];
    this.saveToStorage();
  }

  // Private helpers
  private saveToStorage(): void {
    try {
      localStorage.setItem('kudbee_analytics', JSON.stringify(this.runs));
    } catch (err) {
      console.error('Failed to save analytics:', err);
    }
  }

  private loadFromStorage(): void {
    try {
      const stored = localStorage.getItem('kudbee_analytics');
      if (stored) {
        this.runs = JSON.parse(stored);
      }
    } catch (err) {
      console.error('Failed to load analytics:', err);
    }
  }
}

// Global instance
let analyticsService: AnalyticsService | null = null;

export function getAnalyticsService(): AnalyticsService {
  if (!analyticsService) {
    analyticsService = new AnalyticsService();
  }
  return analyticsService;
}
