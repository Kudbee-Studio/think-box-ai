// What a new customer sees in the kudbEE CLI: a short help, a welcome, and a model list that says what is measured (verified fixes, cost, speed) and what is not.
// Pure text builders (colour functions are passed in) so they are testable; the full command reference stays in cli.ts as `/help all`.
import { CLOUD_MEASUREMENTS, MEASUREMENT_ALIASES, estCostPerTask, type CloudMeasurement } from './cloud-measurements.ts';

export interface Colors { bold(s: string): string; dim(s: string): string; cyan(s: string): string; yellow(s: string): string; green(s: string): string }

export function quickHelp(c: Colors): string {
  return `${c.bold('kudbEE')} ${c.dim('— tell an agent what to do. It proposes; you decide.')}

${c.bold('Just type a goal in plain English')}, for example:
  ${c.cyan('Read https://hnrss.org/frontpage and write top5.md with the 5 top stories')}
  ${c.cyan('Which files does this repository contain, and what does its README say?')}

${c.bold('Everyday commands')}
  /models            the models you can use, with what we measured for each
  /model NAME        switch model
  /files             the files in your workspace      /cat PATH   show one
  /runs              your recent runs                 /run ID     what happened in one
  /stop              cancel the current goal
  /open              the dashboard address
  /help all          every command (memory, convoys, plugins and more)
  /quit              exit

${c.dim('Anything that writes a file, runs a command or sends your data off this machine asks you first.')}`;
}

export function welcome(c: Colors, info: { session: string; model: string; host: string }): string {
  return `${c.yellow('🐝 kudbEE Agent OS')} ${c.dim(`— session ${info.session} · model ${info.model} · ${info.host}`)}
${c.dim('Type a goal in plain English. /help shows what you can do, /models lists the models, Ctrl+C exits.')}
${c.dim('Anything that writes a file, runs a command or sends your data off this machine asks you first.')}`;
}

const find = (model: string, table: CloudMeasurement[]): CloudMeasurement | undefined => table.find((m) => m.model === (MEASUREMENT_ALIASES[model] ?? model));

/** One line for a cloud agent in /models: measured results when there are some, otherwise plainly "not measured yet". */
export function cloudModelNote(model: string, provider: string | undefined, table: CloudMeasurement[] = CLOUD_MEASUREMENTS): string {
  const m = find(model, table);
  const where = `[${provider ?? 'cloud'}]`;
  if (!m) return `${where} cloud agent · not measured yet`;
  const basis = m.cost_basis === 'tokens at an estimated price' ? ' (estimated price)' : '';
  return `${where} ${m.success}/${m.tasks} verified fixes · about $${estCostPerTask(m).toFixed(4)} per task${basis} · ${(m.median_ms / 1000).toFixed(1)} s median`;
}

export function localModelNote(provider: string | undefined): string {
  return `[${provider ?? 'ollama'}] runs on your machine · nothing leaves it · simple goals only`;
}

export const MODELS_PRIVACY_NOTE = 'Cloud agents send your goal, and whatever the agent reads, to that provider. Local models keep everything on this machine.';
