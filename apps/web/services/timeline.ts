// Workflow Timeline Service - Tool execution tracking

export interface TimelineStep {
  id: string;
  name: string;
  toolName: string;
  startTime: number;
  endTime?: number;
  duration?: number;
  status: 'pending' | 'running' | 'completed' | 'error' | 'approved';
  approvalWaitTime?: number;
  result?: string;
  error?: string;
  order: number;
}

export interface TimelineRun {
  id: string;
  startTime: number;
  endTime?: number;
  duration?: number;
  totalApprovalTime: number;
  steps: TimelineStep[];
}

export class TimelineService {
  private runs: Map<string, TimelineRun> = new Map();
  private currentStep: TimelineStep | null = null;

  constructor() {
    this.loadFromStorage();
  }

  // Start a new run
  startRun(runId: string): TimelineRun {
    const run: TimelineRun = {
      id: runId,
      startTime: Date.now(),
      totalApprovalTime: 0,
      steps: [],
    };
    this.runs.set(runId, run);
    return run;
  }

  // End a run
  endRun(runId: string): TimelineRun | null {
    const run = this.runs.get(runId);
    if (!run) return null;

    run.endTime = Date.now();
    run.duration = run.endTime - run.startTime;
    this.saveToStorage();
    return run;
  }

  // Add step to run
  addStep(runId: string, step: Omit<TimelineStep, 'startTime' | 'duration'>): TimelineStep {
    const run = this.runs.get(runId);
    if (!run) throw new Error(`Run ${runId} not found`);

    const fullStep: TimelineStep = {
      ...step,
      startTime: Date.now(),
      order: run.steps.length,
    };

    run.steps.push(fullStep);
    this.currentStep = fullStep;
    this.saveToStorage();
    return fullStep;
  }

  // Complete current step
  completeStep(
    stepId: string,
    result?: string,
    status: 'completed' | 'error' = 'completed'
  ): TimelineStep | null {
    const step = this.findStep(stepId);
    if (!step) return null;

    step.endTime = Date.now();
    step.duration = step.endTime - step.startTime;
    step.status = status;
    step.result = result;
    this.saveToStorage();
    return step;
  }

  // Request approval for step
  requestApproval(stepId: string): TimelineStep | null {
    const step = this.findStep(stepId);
    if (!step) return null;

    step.status = 'approved';
    step.approvalWaitTime = 0;
    this.saveToStorage();
    return step;
  }

  // Track approval wait time
  completeApproval(stepId: string): TimelineStep | null {
    const step = this.findStep(stepId);
    if (!step) return null;

    const approvalDuration = Date.now() - step.startTime;
    step.approvalWaitTime = approvalDuration;

    const run = this.findRunByStep(stepId);
    if (run) {
      run.totalApprovalTime += approvalDuration;
    }

    this.saveToStorage();
    return step;
  }

  // Get run timeline
  getRunTimeline(runId: string): TimelineRun | null {
    return this.runs.get(runId) || null;
  }

  // Get all runs
  getAllRuns(): TimelineRun[] {
    return Array.from(this.runs.values());
  }

  // Calculate step statistics
  getStepStats(runId: string): {
    totalSteps: number;
    completedSteps: number;
    errorSteps: number;
    avgDuration: number;
    totalApprovalTime: number;
    criticalPath: string[];
  } {
    const run = this.runs.get(runId);
    if (!run) {
      return {
        totalSteps: 0,
        completedSteps: 0,
        errorSteps: 0,
        avgDuration: 0,
        totalApprovalTime: 0,
        criticalPath: [],
      };
    }

    const completed = run.steps.filter((s) => s.status === 'completed').length;
    const errors = run.steps.filter((s) => s.status === 'error').length;
    const avgDuration =
      run.steps.filter((s) => s.duration).length > 0
        ? Math.round(
            run.steps.reduce((sum, s) => sum + (s.duration || 0), 0) /
              run.steps.filter((s) => s.duration).length
          )
        : 0;

    // Critical path: longest sequential steps
    const criticalPath = this.calculateCriticalPath(run.steps);

    return {
      totalSteps: run.steps.length,
      completedSteps: completed,
      errorSteps: errors,
      avgDuration,
      totalApprovalTime: run.totalApprovalTime,
      criticalPath,
    };
  }

  // Calculate critical path (longest chain of dependent steps)
  private calculateCriticalPath(steps: TimelineStep[]): string[] {
    if (steps.length === 0) return [];

    let longestPath: string[] = [];
    let maxDuration = 0;

    // Find path with maximum total duration
    steps.forEach((step, idx) => {
      const path = [step.id];
      let duration = step.duration || 0;

      for (let i = idx + 1; i < steps.length; i++) {
        path.push(steps[i].id);
        duration += steps[i].duration || 0;
      }

      if (duration > maxDuration) {
        maxDuration = duration;
        longestPath = path;
      }
    });

    return longestPath;
  }

  // Get tool execution summary
  getToolSummary(runId: string): Map<string, { count: number; totalDuration: number }> {
    const run = this.runs.get(runId);
    if (!run) return new Map();

    const summary = new Map<string, { count: number; totalDuration: number }>();

    run.steps.forEach((step) => {
      const existing = summary.get(step.toolName) || {
        count: 0,
        totalDuration: 0,
      };
      existing.count++;
      existing.totalDuration += step.duration || 0;
      summary.set(step.toolName, existing);
    });

    return summary;
  }

  // Clear run data
  clearRun(runId: string): void {
    this.runs.delete(runId);
    this.saveToStorage();
  }

  // Private helpers
  private findStep(stepId: string): TimelineStep | null {
    for (const run of this.runs.values()) {
      const step = run.steps.find((s) => s.id === stepId);
      if (step) return step;
    }
    return null;
  }

  private findRunByStep(stepId: string): TimelineRun | null {
    for (const run of this.runs.values()) {
      if (run.steps.some((s) => s.id === stepId)) {
        return run;
      }
    }
    return null;
  }

  private saveToStorage(): void {
    try {
      const data = Array.from(this.runs.entries());
      localStorage.setItem('kudbee_timeline', JSON.stringify(data));
    } catch (err) {
      console.error('Failed to save timeline:', err);
    }
  }

  private loadFromStorage(): void {
    try {
      const stored = localStorage.getItem('kudbee_timeline');
      if (stored) {
        const data = JSON.parse(stored);
        this.runs = new Map(data);
      }
    } catch (err) {
      console.error('Failed to load timeline:', err);
    }
  }
}

// Global instance
let timelineService: TimelineService | null = null;

export function getTimelineService(): TimelineService {
  if (!timelineService) {
    timelineService = new TimelineService();
  }
  return timelineService;
}
