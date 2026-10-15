// Keys and touch buttons to the three things pinball needs: left flipper, right flipper, plunger. Pure, so it is tested without a browser.
const LEFT = new Set(['ArrowLeft', 'KeyZ', 'KeyA', 'ShiftLeft']);
const RIGHT = new Set(['ArrowRight', 'KeyM', 'KeyD', 'ShiftRight', 'Slash']);
const PLUNGER = new Set(['Space', 'ArrowDown']);

export function createInput() {
  const held = new Set();
  const any = (set, name) => [...held].some((c) => set.has(c) || c === `touch:${name}`);
  return {
    key(code, down) { if (down) held.add(code); else held.delete(code); },
    /** A touch button: 'left', 'right' or 'plunger'. */
    touch(name, down) { const c = `touch:${name}`; if (down) held.add(c); else held.delete(c); },
    read() { return { left: any(LEFT, 'left'), right: any(RIGHT, 'right'), plunger: any(PLUNGER, 'plunger') }; },
    clear() { held.clear(); },
  };
}

/** Keys that must not scroll the page while playing. */
export const GAME_KEYS = new Set([...LEFT, ...RIGHT, ...PLUNGER, 'KeyP', 'KeyS', 'KeyT', 'Enter']);
