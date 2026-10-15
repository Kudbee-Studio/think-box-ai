// The tuning panel: one slider per setting in tuning.js, plus a reset button. Builds plain elements (text only) and reports every change, so the page can save it.
import { RANGES, PRESETS, setTuning, resetTuning, applyPreset, presetOf } from './tuning.js';

export function buildTuningPanel(doc, game, onChange = () => {}) {
  const box = doc.createElement('div'); box.className = 'tuning-box';
  const title = doc.createElement('div'); title.className = 'tuning-title'; title.textContent = 'Table feel (T to close)'; box.appendChild(title);
  const inputs = {};
  const refresh = () => { for (const k of Object.keys(RANGES)) { inputs[k].slider.value = String(game.tuning[k]); inputs[k].out.textContent = String(game.tuning[k]); } };
  for (const [key, r] of Object.entries(RANGES)) {
    const row = doc.createElement('label'); row.className = 'tuning-row';
    const name = doc.createElement('span'); name.textContent = r.label;
    const slider = doc.createElement('input'); slider.type = 'range'; slider.min = String(r.min); slider.max = String(r.max); slider.step = String(r.step); slider.value = String(game.tuning[key]);
    const out = doc.createElement('span'); out.className = 'tuning-value'; out.textContent = String(game.tuning[key]);
    slider.addEventListener('input', () => { setTuning(game, key, slider.value); out.textContent = String(game.tuning[key]); onChange(game.tuning); });
    inputs[key] = { slider, out };
    row.appendChild(name); row.appendChild(slider); row.appendChild(out); box.appendChild(row);
  }
  const reset = doc.createElement('button'); reset.className = 'tuning-reset'; reset.textContent = 'Back to the defaults';
  reset.addEventListener('click', () => { resetTuning(game); refresh(); onChange(game.tuning); });
  box.appendChild(reset);
  return box;
}

/** Saved settings from storage text, checked value by value (anything wrong is ignored). */
export function loadTuning(game, text) {
  try { const saved = JSON.parse(text ?? 'null'); if (saved && typeof saved === 'object') for (const [k, v] of Object.entries(saved)) setTuning(game, k, v); } catch { /* unreadable: keep the defaults */ }
}

/** Easy / Normal / Hard buttons: one click sets every feel setting. The one that matches the current settings is shown as pressed (none when the settings are custom). */
export function buildPresetBar(doc, game, onChange = () => {}) {
  const bar = doc.createElement('div'); bar.className = 'preset-bar';
  const buttons = {};
  const refresh = () => { const now = presetOf(game.tuning); for (const [name, b] of Object.entries(buttons)) b.setAttribute('aria-pressed', String(name === now)); };
  for (const name of Object.keys(PRESETS)) {
    const b = doc.createElement('button'); b.type = 'button'; b.className = 'preset-button'; b.textContent = name[0].toUpperCase() + name.slice(1);
    b.addEventListener('click', () => { applyPreset(game, name); refresh(); onChange(game.tuning); });
    buttons[name] = b; bar.appendChild(b);
  }
  refresh();
  bar.refresh = refresh;
  return bar;
}
