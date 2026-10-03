// P3.20: Run eval set on all three models, 2 reps each. Measure pass rate, latency, memory, fallbacks.

import { EVAL_SET } from './local-model-eval-p3.20.ts';
import { spawn } from 'node:child_process';
import { execSync } from 'node:child_process';

interface RunResult {
  model: string;
  goal: string;
  passed: boolean;
  latency_ms: number;
  gpu_vram_pct: number;
  fell_back_to_mercury: boolean;
  answer: string;
}

const MODELS = ['smollm2:360m', 'qwen2.5:1.5b', 'qwen2.5:3b'];
const REPS = 2;

async function queryModel(model: string, goal: string): Promise<{ answer: string; latency_ms: number; fallback: boolean }> {
  const start = Date.now();
  try {
    // For MVP: use curl to the local ollama API directly
    const response = await fetch('http://127.0.0.1:11434/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model,
        stream: false,
        messages: [{ role: 'user', content: goal }],
        options: { num_predict: 512, num_ctx: 2048 },
      }),
    });
    const json = (await response.json()) as any;
    const latency = Date.now() - start;
    return { answer: json.message?.content ?? '', latency_ms: latency, fallback: false };
  } catch (e) {
    return { answer: `[Error: ${e}]`, latency_ms: Date.now() - start, fallback: true };
  }
}

function getGpuPercent(model: string): number {
  try {
    const ps = execSync('curl -s http://127.0.0.1:11434/api/ps').toString();
    const models = JSON.parse(ps).models ?? [];
    const m = models.find((x: any) => x.name === model);
    return m ? Math.round((100 * (m.size_vram ?? 0)) / (m.size ?? 1)) : 0;
  } catch {
    return 0;
  }
}

function checkPass(goal: string, answer: string, expectedKey: string): boolean {
  // Answer passes if it contains the expected key (evidence)
  return new RegExp(expectedKey, 'i').test(answer);
}

async function runBakeoff() {
  const results: RunResult[] = [];

  console.log('🔬 P3.20 Local Model Bake-off\n');
  console.log(`Models: ${MODELS.join(', ')}`);
  console.log(`Reps: ${REPS} per model`);
  console.log(`Goals: ${EVAL_SET.length} local-routable + escalate mix\n`);

  for (const model of MODELS) {
    console.log(`\n▶ ${model} (${REPS} reps)`);
    const modelResults: RunResult[] = [];

    for (let rep = 0; rep < REPS; rep++) {
      for (const goal of EVAL_SET) {
        const { answer, latency_ms, fallback } = await queryModel(model, goal.goal);
        const passed = !fallback && checkPass(goal.goal, answer, goal.expectedKey);
        modelResults.push({
          model,
          goal: goal.goal,
          passed,
          latency_ms,
          gpu_vram_pct: getGpuPercent(model),
          fell_back_to_mercury: fallback,
          answer: answer.slice(0, 120),
        });
        results.push(modelResults[modelResults.length - 1]!);
      }
    }

    const passRate = (modelResults.filter((r) => r.passed).length / modelResults.length) * 100;
    const latencies = modelResults.map((r) => r.latency_ms).sort((a, b) => a - b);
    const p95 = latencies[Math.floor(latencies.length * 0.95)];
    console.log(`  Pass rate: ${passRate.toFixed(0)}%`);
    console.log(`  Latency (p50/p95): ${latencies[Math.floor(latencies.length * 0.5)]}ms / ${p95}ms`);
    console.log(`  GPU: ${modelResults[0]!.gpu_vram_pct}%`);
    console.log(`  Fallbacks: ${modelResults.filter((r) => r.fell_back_to_mercury).length}`);
  }

  // Determine winner: highest pass rate, p95 ≤ 5s, smaller model breaks ties
  const modelStats = MODELS.map((model) => {
    const modelRuns = results.filter((r) => r.model === model);
    const passRate = (modelRuns.filter((r) => r.passed).length / modelRuns.length) * 100;
    const p95 = modelRuns.map((r) => r.latency_ms).sort((a, b) => a - b)[Math.floor(modelRuns.length * 0.95)] ?? 999999;
    const eligible = p95 <= 5000; // p95 ≤ 5s
    return { model, passRate, p95, eligible };
  });

  console.log('\n📊 Summary\n');
  modelStats.forEach((s) => {
    console.log(`${s.model.padEnd(20)} | ${s.passRate.toFixed(0)}% pass | p95 ${s.p95}ms | ${s.eligible ? '✓' : '✗'}`);
  });

  const eligible = modelStats.filter((s) => s.eligible).sort((a, b) => b.passRate - a.passRate);
  const winner = eligible[0];

  if (winner) {
    console.log(`\n🏆 Winner: ${winner.model} (${winner.passRate.toFixed(0)}% pass rate)`);
  } else {
    console.log('\n⚠️ No model met p95 ≤ 5s threshold; using smollm2:360m as fallback.');
  }

  // Save results
  const report = {
    timestamp: new Date().toISOString(),
    models: MODELS,
    reps: REPS,
    eval_set_size: EVAL_SET.length,
    results,
    modelStats,
    winner: winner?.model || 'smollm2:360m',
  };

  const fs = await import('node:fs/promises');
  await fs.writeFile('docs/evidence/p320-local-bakeoff-results.json', JSON.stringify(report, null, 2));
  console.log(`\n✅ Results saved to docs/evidence/p320-local-bakeoff-results.json`);
}

runBakeoff().catch(console.error);
