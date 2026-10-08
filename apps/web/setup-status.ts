// The "Get started" checklist. Pure: the route gathers the facts (environment, is Ollama answering, how many runs) and this decides what is done and what to do next.
// It reports whether a key is set, never the key.
export interface SetupInput { env: Record<string, string | undefined>; ollamaReachable: boolean; runs: number }
export interface SetupStep { id: string; title: string; done: boolean; required: boolean; hint: string }

const KEYS = ['INCEPTION_API_KEY', 'DEEPSEEK_API_KEY', 'XAI_API_KEY'];
const PLACEHOLDER = /your[-_ ]?key|changeme|^<.*>$/i;
const hasKey = (v: string | undefined): boolean => typeof v === 'string' && v.trim().length > 0 && !PLACEHOLDER.test(v.trim());

export function setupSteps(i: SetupInput): { ready: boolean; steps: SetupStep[] } {
  const model = KEYS.some((k) => hasKey(i.env[k])) || i.ollamaReachable;
  const budget = Number(i.env.KUDBEE_DAILY_BUDGET_USD) > 0;
  const steps: SetupStep[] = [
    { id: 'model', title: 'Connect a model', done: model, required: true, hint: model ? 'A model is connected.' : 'Run "kudbee init", then put one key in .env (INCEPTION_API_KEY, DEEPSEEK_API_KEY or XAI_API_KEY), or start Ollama for a local model. Restart the dashboard afterwards.' },
    { id: 'first-goal', title: 'Run your first goal', done: i.runs > 0, required: false, hint: i.runs > 0 ? `${i.runs} runs so far.` : 'Type a goal in the terminal, for example "List the files in my workspace and say what each is for".' },
    { id: 'spend-limit', title: 'Set a daily spend limit', done: budget, required: false, hint: budget ? 'Runs stop at your daily limit.' : 'Set KUDBEE_DAILY_BUDGET_USD in .env (for example 2) so a runaway run cannot cost more than that.' },
    { id: 'health', title: 'Check this machine', done: false, required: false, hint: 'Open Tools > Health check, or run "kudbee doctor".' },
  ];
  return { ready: model, steps };
}
