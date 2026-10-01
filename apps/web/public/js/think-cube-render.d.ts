// Types for the plain-JS renderer so tests can import it under strict TypeScript.
export class ThinkCubeRenderer {
  constructor(container: any);
  container: any;
  state: any;
  cellEls: any[];
  statusEl: any;
  inspectEl: any;
  recordedEvents: Array<{ stage: string; payload: unknown }>;
  paused: boolean;
  pulseCount: number;
  _pulsing: boolean;
  render(): void;
  dispatch(stage: string, payload?: unknown): void;
  handleThought(thought: unknown): void;
  /** Display-only highlight for a real token event; returns false for an unknown kind. */
  pulse(kind: string, intensity?: number): boolean;
  pause(): void;
  resume(): void;
  reset(): void;
  replay(delayMs?: number): Promise<void>;
  runDeterministicDemo(): Promise<void>;
}
