// Keyboard (and touch buttons) to the three things the game cares about: left, right, fire. Pure, so it can be tested without a browser.
const LEFT = new Set(['ArrowLeft', 'KeyA']);
const RIGHT = new Set(['ArrowRight', 'KeyD']);
const FIRE = new Set(['Space', 'ArrowUp', 'KeyW']);

export function createInput() {
  const held = new Set();
  return {
    key(code, down) { if (down) held.add(code); else held.delete(code); },
    /** A button on a touch screen: 'left', 'right' or 'fire'. */
    touch(name, down) { const code = `touch:${name}`; if (down) held.add(code); else held.delete(code); },
    read() {
      const any = (set, name) => [...held].some((c) => set.has(c) || c === `touch:${name}`);
      return { left: any(LEFT, 'left'), right: any(RIGHT, 'right'), fire: any(FIRE, 'fire') };
    },
    clear() { held.clear(); },
  };
}

/** Keys that should not scroll the page or press a focused button while playing. */
export const GAME_KEYS = new Set([...LEFT, ...RIGHT, ...FIRE, 'KeyP', 'KeyM', 'Enter']);
