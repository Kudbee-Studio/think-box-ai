// Game flow helpers. After game over a restart is refused for a moment, so mashing the flipper or plunger keys does not skip the result screen.
export function createRestartGuard(ms) {
  let until = 0;
  return { arm(now) { until = now + ms; }, allowed(now) { return now >= until; } };
}
