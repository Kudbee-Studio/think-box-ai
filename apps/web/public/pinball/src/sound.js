// Sound, made in the browser (no audio files). One short tone per kind of event. Nothing is created until the player presses a key or taps (browsers insist on that),
// the same sound is thinned out so a burst cannot turn into noise, and with no audio support everything is a quiet no-op.
const SOUNDS = {
  bumper: { type: 'sine', from: 660, to: 990, dur: 0.14, vol: 0.25, gap: 40 },
  flip: { type: 'square', from: 150, to: 90, dur: 0.05, vol: 0.12, gap: 30 },
  'flipper-hit': { type: 'square', from: 220, to: 340, dur: 0.07, vol: 0.18, gap: 50 },
  wall: { type: 'triangle', from: 320, to: 200, dur: 0.05, vol: 0.12, gap: 80 },
  launch: { type: 'sawtooth', from: 180, to: 900, dur: 0.35, vol: 0.2, gap: 200 },
  drain: { type: 'sawtooth', from: 320, to: 60, dur: 0.7, vol: 0.25, gap: 300 },
  bonus: { type: 'triangle', from: 520, to: 780, dur: 0.3, vol: 0.2, gap: 200 },
  combo: { type: 'sine', from: 700, to: 1000, dur: 0.12, vol: 0.18, gap: 60 },
  multiplier: { type: 'square', from: 1040, to: 1560, dur: 0.25, vol: 0.14, gap: 200 },
  trap: { type: 'sine', from: 140, to: 90, dur: 0.2, vol: 0.28, gap: 200 },
  release: { type: 'square', from: 300, to: 620, dur: 0.15, vol: 0.2, gap: 200 },
  layer: { type: 'triangle', from: 400, to: 1200, dur: 0.4, vol: 0.2, gap: 300 },
  jackpot: { type: 'sawtooth', from: 600, to: 1800, dur: 0.7, vol: 0.25, gap: 500 },
  supercombo: { type: 'sine', from: 900, to: 1400, dur: 0.3, vol: 0.2, gap: 300 },
  multiball: { type: 'sawtooth', from: 500, to: 1500, dur: 0.5, vol: 0.22, gap: 400 },
  'extra-lost': { type: 'triangle', from: 260, to: 120, dur: 0.15, vol: 0.12, gap: 100 },
  over: { type: 'sawtooth', from: 240, to: 40, dur: 1.0, vol: 0.28, gap: 500 },
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
      const s = SOUNDS[e?.type];
      if (!s || !ctx || api.muted || broken) return;
      const t = now();
      if (t - (last[e.type] ?? -Infinity) < s.gap) return;
      last[e.type] = t;
      try {
        const osc = ctx.createOscillator(); const gain = ctx.createGain(); const at = ctx.currentTime;
        const power = e.type === 'launch' ? Math.max(0.3, Math.min(1, e.power ?? 1)) : 1;
        osc.type = s.type;
        const bend = e.type === 'combo' ? Math.min(8, e.combo ?? 3) * 40 : 0; // a longer combo sounds higher
        osc.frequency.setValueAtTime(s.from + bend, at); osc.frequency.exponentialRampToValueAtTime(s.from + bend + (s.to - s.from) * power, at + s.dur);
        gain.gain.setValueAtTime(s.vol, at); gain.gain.exponentialRampToValueAtTime(0.0001, at + s.dur);
        osc.connect(gain); gain.connect(ctx.destination);
        osc.start(at); osc.stop(at + s.dur + 0.02);
      } catch { broken = true; }
    },
  };
  return api;
}
