// The saved high-score list: read back from storage text with every entry checked (anything wrong is dropped), so a damaged or tampered save cannot break the game.
import { cleanInitials } from './game.js';

export function parseScores(text) {
  let raw; try { raw = JSON.parse(text ?? '[]'); } catch { return []; }
  if (!Array.isArray(raw)) return [];
  const list = raw.filter((e) => e && typeof e === 'object' && Number.isFinite(e.score) && e.score > 0 && e.score < 1e12).map((e) => ({ name: cleanInitials(e.name), score: Math.floor(e.score) }));
  list.sort((a, b) => b.score - a.score);
  return list.slice(0, 10);
}
