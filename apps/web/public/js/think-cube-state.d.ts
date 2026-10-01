export interface CubeCell {
  index: number;
  face: number;
  role: string;
  active: boolean;
  locked: boolean;
  disrupted: boolean;
  shared: boolean;
  value: number;
}

export interface CubeState {
  stage: string;
  tokenId: string | null;
  thinkBoxIds: string[];
  specialistIds: string[];
  verdict: 'pass' | 'fail' | null;
  stable: boolean;
  cells: CubeCell[];
  history: string[];
}

export interface RenderProp {
  index: number;
  face: number;
  role: string;
  className: string;
  title: string;
  opacity: number;
}

export const STAGES: readonly string[];
export const ROLES: readonly string[];
export const CELL_COUNT: number;
export function createInitialCubeState(): CubeState;
export function applyEvent(state: CubeState, event: { stage: string; payload?: Record<string, unknown> }): CubeState;
export function cellsToRenderProps(state: CubeState): RenderProp[];
export function summarize(state: CubeState): {
  stage: string;
  tokenId: string | null;
  verdict: 'pass' | 'fail' | null;
  stable: boolean;
  thinkBoxIds: string[];
  specialistIds: string[];
  activeCount: number;
  lockedCount: number;
  disruptedCount: number;
  sharedCount: number;
  historyLength: number;
};