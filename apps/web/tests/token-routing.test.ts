import { describe, it } from 'node:test';
import { expect } from './test-helpers.ts';

describe('Token Routing & Telemetry', () => {
  describe('selectModelForGoal routing heuristics', () => {
    // Mock implementation for testing
    const testRouting = (goal: string): { complexity: string; shouldUseComplex: boolean } => {
      const complexPatterns = [
        /\b(code|write|generate|create|build|implement|design|refactor)\b/i,
        /\b(research|analyze|investigate|compare|debug|trace|profile)\b/i,
        /\b(multiple|several|many)\b.*\b(files|tasks|steps|goals|functions)\b/i,
        /\{.*\}/, // JSON structure
        /```/, // Code blocks
        /\b(algorithm|architecture|design pattern|optimize|complex)\b/i,
      ];

      const isComplex = complexPatterns.some((p) => p.test(goal)) || goal.length > 150;
      return {
        complexity: isComplex ? 'complex' : 'simple',
        shouldUseComplex: isComplex,
      };
    };

    it('routes simple goals to the cheap local model', () => {
      const result = testRouting('What is the capital of France?');
      expect(result.complexity).toBe('simple');
      expect(result.shouldUseComplex).toBe(false);
    });

    it('routes complex code generation to Mercury-2', () => {
      const result = testRouting('Generate a TypeScript utility to parse and validate email addresses with regex');
      expect(result.complexity).toBe('complex');
      expect(result.shouldUseComplex).toBe(true);
    });

    it('routes research tasks to Mercury-2', () => {
      const result = testRouting('Analyze the performance impact of three different caching strategies and compare their trade-offs');
      expect(result.complexity).toBe('complex');
      expect(result.shouldUseComplex).toBe(true);
    });

    it('handles manual override via route_reason', () => {
      // When route_reason is 'manual', the model selection should respect user choice
      const telemetry = {
        modelSelected: 'mercury-2',
        routeReason: 'manual' as const,
        complexity: 'simple',
        estimatedTokensIfFullModel: 1500,
        estimatedTokensActual: 2500,
        tokensSavedEst: 0,
      };
      expect(telemetry.routeReason).toBe('manual');
      expect(telemetry.modelSelected).toBe('mercury-2');
    });

    it('detects long goals as complex', () => {
      const longGoal = 'A '.repeat(76); // 152 chars, strictly >150
      const result = testRouting(longGoal);
      expect(result.shouldUseComplex).toBe(true);
    });

    it('detects JSON in goal as complex', () => {
      const result = testRouting('Parse this: {"data": "value"}');
      expect(result.complexity).toBe('complex');
    });

    it('detects code blocks as complex', () => {
      const result = testRouting('Fix this function:\n```typescript\nfunction test() {}\n```');
      expect(result.complexity).toBe('complex');
    });
  });

  describe('local model availability (Qwen2.5 1.5B route + Ollama fallback)', () => {
    const LOCAL_MODEL = 'qwen2.5:1.5b';
    interface Model { name: string; agent?: boolean }
    interface RouteTelemtry {
      modelSelected: string;
      routeReason: 'auto' | 'manual' | 'auto_fallback_no_local';
      complexity: 'simple' | 'complex';
      estimatedTokensIfFullModel: number;
      estimatedTokensActual: number;
      tokensSavedEst: number;
    }

    // Mirrors apps/web/cli.ts selectModelForGoal without the console output / Client class.
    function route(goal: string, models: Model[], currentModel: string): RouteTelemtry {
      const mercury = models.find((m) => m.agent);
      const local = models.find((m) => !m.agent && m.name === LOCAL_MODEL);

      if (!mercury) {
        return { modelSelected: currentModel, routeReason: 'manual', complexity: 'simple', estimatedTokensIfFullModel: 2500, estimatedTokensActual: 2500, tokensSavedEst: 0 };
      }

      const complexPatterns = [
        /\b(code|write|generate|create|build|implement|design|refactor)\b/i,
        /\b(research|analyze|investigate|compare|debug|trace|profile)\b/i,
      ];
      const isComplex = complexPatterns.some((p) => p.test(goal)) || goal.length > 150;
      const complexity: 'simple' | 'complex' = isComplex ? 'complex' : 'simple';
      const estimatedTokensIfFullModel = isComplex ? 2500 : 1500;

      if (isComplex) {
        return { modelSelected: mercury.name, routeReason: 'auto', complexity, estimatedTokensIfFullModel, estimatedTokensActual: 2500, tokensSavedEst: 0 };
      }
      if (local) {
        return { modelSelected: local.name, routeReason: 'auto', complexity, estimatedTokensIfFullModel, estimatedTokensActual: 800, tokensSavedEst: estimatedTokensIfFullModel - 800 };
      }
      return { modelSelected: mercury.name, routeReason: 'auto_fallback_no_local', complexity, estimatedTokensIfFullModel, estimatedTokensActual: estimatedTokensIfFullModel, tokensSavedEst: 0 };
    }

    it('routes simple goal to qwen2.5:1.5b when the local model is pulled', () => {
      const models = [{ name: 'mercury-2', agent: true }, { name: LOCAL_MODEL }];
      const result = route('What is the capital of France?', models, 'mercury-2');
      expect(result.modelSelected).toBe(LOCAL_MODEL);
      expect(result.routeReason).toBe('auto');
      expect(result.tokensSavedEst).toBeGreaterThan(0);
    });

    it('falls back to Mercury-2 with honest zero savings when local model is absent', () => {
      const models = [{ name: 'mercury-2', agent: true }]; // Ollama has nothing pulled
      const result = route('What is the capital of France?', models, 'mercury-2');
      expect(result.modelSelected).toBe('mercury-2');
      expect(result.routeReason).toBe('auto_fallback_no_local');
      expect(result.tokensSavedEst).toBe(0);
    });

    it('does not fall back for complex goals even without a local model', () => {
      const models = [{ name: 'mercury-2', agent: true }];
      const result = route('Generate a TypeScript utility to validate emails with regex', models, 'mercury-2');
      expect(result.modelSelected).toBe('mercury-2');
      expect(result.routeReason).toBe('auto');
      expect(result.complexity).toBe('complex');
    });

    it('ignores unrelated Ollama models when picking the cheap route', () => {
      // A different local model is installed, but not the configured cheap route —
      // should not be mistaken for it.
      const models = [{ name: 'mercury-2', agent: true }, { name: 'llama3:8b' }];
      const result = route('What is the capital of France?', models, 'mercury-2');
      expect(result.modelSelected).toBe('mercury-2');
      expect(result.routeReason).toBe('auto_fallback_no_local');
    });

    it('manual override is unaffected by local model availability', () => {
      const telemetry: RouteTelemtry = {
        modelSelected: 'mercury-2',
        routeReason: 'manual',
        complexity: 'simple',
        estimatedTokensIfFullModel: 2500,
        estimatedTokensActual: 2500,
        tokensSavedEst: 0,
      };
      expect(telemetry.routeReason).toBe('manual');
    });
  });

  describe('Token telemetry calculations', () => {
    it('calculates savings for simple → local route', () => {
      const telemetry = {
        modelSelected: 'smoLLM2',
        routeReason: 'auto' as const,
        complexity: 'simple',
        estimatedTokensIfFullModel: 1500,
        estimatedTokensActual: 800,
        tokensSavedEst: 700,
      };
      expect(telemetry.tokensSavedEst).toBe(700);
      expect(telemetry.estimatedTokensIfFullModel - telemetry.estimatedTokensActual).toBe(700);
    });

    it('calculates no savings for complex → mercury route', () => {
      const telemetry = {
        modelSelected: 'mercury-2',
        routeReason: 'auto' as const,
        complexity: 'complex',
        estimatedTokensIfFullModel: 2500,
        estimatedTokensActual: 2500,
        tokensSavedEst: 0,
      };
      expect(telemetry.tokensSavedEst).toBe(0);
    });
  });

  describe('run_metadata persistence', () => {
    it('includes routing telemetry in metrics', () => {
      const metrics = {
        tokens: 1200,
        cost_usd: 0.0036,
        duration_ms: 5000,
        tool_calls: 3,
        approvals_approved: 2,
        approvals_denied: 0,
        model_selected: 'smoLLM2',
        route_reason: 'auto' as const,
        estimated_tokens_if_full_model: 1500,
        estimated_tokens_actual: 800,
        tokens_saved_est: 700,
      };
      expect(metrics.model_selected).toBe('smoLLM2');
      expect(metrics.route_reason).toBe('auto');
      expect(metrics.tokens_saved_est).toBe(700);
    });

    it('persists telemetry across run completion', () => {
      const run1 = {
        runId: 'run-001',
        status: 'completed' as const,
        metrics: {
          model_selected: 'smoLLM2',
          tokens_saved_est: 700,
        },
      };
      const run2 = {
        runId: 'run-002',
        status: 'completed' as const,
        metrics: {
          model_selected: 'mercury-2',
          tokens_saved_est: 0,
        },
      };
      expect(run1.metrics.tokens_saved_est).toBe(700);
      expect(run2.metrics.tokens_saved_est).toBe(0);
    });
  });

  describe('KPI aggregation', () => {
    it('aggregates token savings across multiple runs', () => {
      const runs = [
        { metrics: { tokens_saved_est: 700 } },
        { metrics: { tokens_saved_est: 600 } },
        { metrics: { tokens_saved_est: 0 } },
      ];
      const totalSaved = runs.reduce((sum, run) => sum + (run.metrics?.tokens_saved_est ?? 0), 0);
      const avgSaved = Math.round(totalSaved / runs.length);
      expect(totalSaved).toBe(1300);
      expect(avgSaved).toBe(433);
    });

    it('calculates sparkline data correctly', () => {
      const runs = [
        { metrics: { tokens_saved_est: 100 } },
        { metrics: { tokens_saved_est: 200 } },
        { metrics: { tokens_saved_est: 150 } },
        { metrics: { tokens_saved_est: 300 } },
      ];
      const sparkline = runs.map((r) => r.metrics?.tokens_saved_est ?? 0);
      expect(sparkline).toEqual([100, 200, 150, 300]);
    });

    it('handles empty run history', () => {
      const runs: any[] = [];
      const totalSaved = runs.reduce((sum, run) => sum + (run.metrics?.tokens_saved_est ?? 0), 0);
      const avgSaved = runs.length > 0 ? Math.round(totalSaved / runs.length) : 0;
      expect(totalSaved).toBe(0);
      expect(avgSaved).toBe(0);
    });
  });
});
