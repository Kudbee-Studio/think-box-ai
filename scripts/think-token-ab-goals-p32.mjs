// P3.2: the P3.1 goals where the new retrieval ranking surfaces a hand-marked correct lesson in the top 3 (7 of 8; `three-files` does not).
import { GOALS as ALL } from './think-token-ab-goals-p31.mjs';
export const GOALS = ALL.filter((g) => g.id !== 'three-files');
