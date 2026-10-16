// Sound, made in the browser (no audio files). One short tone per kind of event. Nothing is created until the player presses a key or taps (browsers insist on that),
// the same sound is thinned out so a burst cannot turn into noise, and with no audio support everything is a quiet no-op.
const SOUNDS = {
  'fire-laser': { type: 'square', from: 760, to: 480, dur: 0.05, vol: 0.05, gap: 90 },
  'fire-spread': { type: 'square', from: 560, to: 330, dur: 0.07, vol: 0.06, gap: 110 },
  'fire-missile': { type: 'sawtooth', from: 280, to: 170, dur: 0.14, vol: 0.09, gap: 160 },
  'fire-rail': { type: 'sawtooth', from: 1100, to: 140, dur: 0.16, vol: 0.12, gap: 200 },
  weapon: { type: 'triangle', from: 480, to: 720, dur: 0.14, vol: 0.16, gap: 80 },
  'weapon-up': { type: 'sine', from: 600, to: 1500, dur: 0.5, vol: 0.22, gap: 500 },
  'hit-enemy': { type: 'triangle', from: 420, to: 300, dur: 0.05, vol: 0.1, gap: 40 },
  kill: { type: 'triangle', from: 340, to: 120, dur: 0.14, vol: 0.2, gap: 30 },
  hit: { type: 'sawtooth', from: 220, to: 50, dur: 0.5, vol: 0.28, gap: 200 },
  'shield-break': { type: 'square', from: 600, to: 150, dur: 0.25, vol: 0.2, gap: 200 },
  pickup: { type: 'sine', from: 520, to: 1040, dur: 0.22, vol: 0.2, gap: 80 },
  'pickup-token': { type: 'sine', from: 1250, to: 1650, dur: 0.07, vol: 0.1, gap: 40 },
  wave: { type: 'triangle', from: 380, to: 700, dur: 0.35, vol: 0.2, gap: 400 },
  boss: { type: 'sawtooth', from: 110, to: 70, dur: 0.9, vol: 0.28, gap: 800 },
  'boss-down': { type: 'sawtooth', from: 180, to: 1500, dur: 0.9, vol: 0.28, gap: 800 },
  combo: { type: 'sine', from: 880, to: 1200, dur: 0.1, vol: 0.14, gap: 60 },
  'enemy-fire': { type: 'square', from: 240, to: 160, dur: 0.08, vol: 0.07, gap: 150 },
  bomb: { type: 'sawtooth', from: 520, to: 50, dur: 0.6, vol: 0.3, gap: 300 },
  'boss-enrage': { type: 'sawtooth', from: 95, to: 55, dur: 0.8, vol: 0.28, gap: 1000 },
  perfect: { type: 'sine', from: 660, to: 1320, dur: 0.45, vol: 0.2, gap: 600 },
  summon: { type: 'triangle', from: 200, to: 420, dur: 0.3, vol: 0.18, gap: 800 },
  over: { type: 'sawtooth', from: 260, to: 40, dur: 1.1, vol: 0.28, gap: 800 },
};

export function createSound(AudioCtor, now = () => (typeof performance !== 'undefined' ? performance.now() : Date.now())) {
  let ctx = null; let broken = !AudioCtor; const last = {};
  const api = {
    muted: false,
    get available() { return !broken; },
    unlock() {
      if (broken) return;
      try {
        if (!ctx) ctx = new AudioCtor();
        if (ctx.state === 'suspended') void ctx.resume();
      } catch { broken = true; ctx = null; }
    },
    setMuted(m) { api.muted = !!m; },
    play(e) {
      const key = e?.type === 'fire' && e.weapon ? `fire-${e.weapon}` : e?.type === 'pickup' && e.kind === 'token' ? 'pickup-token' : e?.type;
      const s = SOUNDS[key];
      if (!s || !ctx || api.muted || broken) return;
      const t = now();
      if (t - (last[key] ?? -Infinity) < s.gap) return;
      last[key] = t;
      try {
        const osc = ctx.createOscillator(); const gain = ctx.createGain(); const at = ctx.currentTime;
        const power = 1;
        osc.type = s.type;
        const bend = e.type === 'combo' ? Math.min(8, Math.floor((e.combo ?? 3) / 5)) * 60 : 0; // a longer combo sounds higher
        osc.frequency.setValueAtTime(s.from + bend, at); osc.frequency.exponentialRampToValueAtTime(s.from + bend + (s.to - s.from) * power, at + s.dur);
        gain.gain.setValueAtTime(s.vol, at); gain.gain.exponentialRampToValueAtTime(0.0001, at + s.dur);
        osc.connect(gain); gain.connect(ctx.destination);
        osc.start(at); osc.stop(at + s.dur + 0.02);
      } catch { broken = true; }
    },
  };
  return api;
}
