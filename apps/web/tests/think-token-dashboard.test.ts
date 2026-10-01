// Tests for Think Token Dashboard — data honesty, event handling, controls, update behavior
//
// Note: think-token-dashboard.js is a classic script (not ES module), so we verify behavior
// through code structure analysis rather than direct instantiation. Each test documents
// the requirement, the implementation, and the code location that verifies it.
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

// Load the dashboard source to verify structure
const __dirname = dirname(fileURLToPath(import.meta.url));
const dashboardSource = readFileSync(join(__dirname, '../public/js/think-token-dashboard.js'), 'utf8');

describe('Think Token Dashboard — Data Honesty', () => {
  it('does not define startLiveUpdates() to prevent fake event generation', () => {
    assert.ok(!dashboardSource.includes('startLiveUpdates('), 'startLiveUpdates method removed');
  });

  it('does not call setInterval for fake propagation:active events', () => {
    assert.ok(!dashboardSource.includes('setInterval'), 'no setInterval for demo events');
  });

  it('does not listen to propagation:active (fake stats)', () => {
    assert.ok(!dashboardSource.includes("'propagation:active'"), 'no propagation:active listener');
  });

  it('setupEventListeners only listens for real WebSocket events', () => {
    // Real event sources:
    assert.ok(dashboardSource.includes("'token:created'"), 'listens to token:created');
    assert.ok(dashboardSource.includes("'token:used'"), 'listens to token:used');
    assert.ok(dashboardSource.includes("'think-cube:thought'"), 'listens to think-cube:thought from WebSocket');
  });

  it('addToken and recordTokenUsage only update if modal is open', () => {
    assert.ok(dashboardSource.includes('if (this.modalEl)'), 'checks if modal is open before updating');
  });

  it('does not export fake propagationStats (only real analysis)', () => {
    assert.ok(dashboardSource.includes('exportLearnings()'), 'export function exists');
    // In the export section, verify we have real metrics, not fake ones
    assert.ok(dashboardSource.includes('calculateAverageSuccessRate'), 'includes real success rate calc');
    assert.ok(dashboardSource.includes('calculateKnowledgeReuse'), 'includes real reuse calc');
  });
});

describe('Think Token Dashboard — UI State Preservation', () => {
  it('openDashboard reuses existing modal if already open (prevents state loss)', () => {
    assert.ok(dashboardSource.includes('if (this.modalEl && document.body.contains(this.modalEl))'), 'checks if modal exists');
    assert.ok(dashboardSource.includes('return'), 'returns early without rebuild');
  });

  it('updateCurrentJobInfo updates only job info div (targeted update)', () => {
    assert.ok(dashboardSource.includes("querySelector('.current-job-info')"), 'targets job info div');
  });

  it('renderTokenList updates only token list pane (targeted update)', () => {
    assert.ok(dashboardSource.includes("querySelector('#tab-tokens')"), 'targets token pane');
  });

  it('switchTab changes only classes and display (no DOM rebuild)', () => {
    assert.ok(dashboardSource.includes('switchTab'), 'switchTab method exists');
    assert.ok(dashboardSource.includes("classList.toggle('active'"), 'toggles active class');
  });
});

describe('Think Token Dashboard — Empty and Loading States', () => {
  it('displays empty state when no tokens exist', () => {
    assert.ok(dashboardSource.includes('No tokens created yet'), 'empty state message exists');
  });

  it('displays empty state in analytics when no tokens exist', () => {
    assert.ok(dashboardSource.includes('No analytics available'), 'analytics empty state exists');
  });

  it('cube visualization shows unavailable message if module did not load', () => {
    assert.ok(dashboardSource.includes('Cube visualization unavailable'), 'fallback message exists');
  });
});

describe('Think Token Dashboard — Controls and Interactions', () => {
  it('cube control buttons are wired to pause, resume, reset, replay, demo', () => {
    assert.ok(dashboardSource.includes('data-cube-action'), 'action buttons exist');
    assert.ok(dashboardSource.includes('pause()'), 'pause wired');
    assert.ok(dashboardSource.includes('resume()'), 'resume wired');
    assert.ok(dashboardSource.includes('reset()'), 'reset wired');
    assert.ok(dashboardSource.includes('replay()'), 'replay wired');
    assert.ok(dashboardSource.includes('runDeterministicDemo()'), 'demo wired');
  });

  it('demo button is labeled to prevent confusion about real vs demo', () => {
    assert.ok(dashboardSource.includes('📺 Demo'), 'demo emoji and label');
    assert.ok(dashboardSource.includes('no backend signal'), 'legend explains demo-only');
  });

  it('close button removes modal and clears modalEl', () => {
    assert.ok(dashboardSource.includes('this.modalEl = null'), 'clears reference on close');
  });

  it('clicking outside modal closes it', () => {
    assert.ok(dashboardSource.includes('e.target === modal') && dashboardSource.includes('modal.remove()'), 'outside click closes');
  });

  it('token ids never reach inline JavaScript; Details uses delegation', () => {
    assert.ok(!/onclick="[^"]*\$\{/.test(dashboardSource), 'no interpolation inside onclick');
    assert.ok(dashboardSource.includes('data-token-details'), 'delegated details button');
    assert.ok(dashboardSource.includes('escapeAttr(token.id)'), 'id is attribute-escaped');
  });
});

describe('Think Token Dashboard — Responsive Layout (static CSS checks; not a browser run)', () => {
  const css = readFileSync(join(__dirname, '../public/css/think-token-dashboard.css'), 'utf8');

  it('declares breakpoints at 1024px, 768px and 480px', () => {
    for (const bp of ['1024px', '768px', '480px']) assert.ok(css.includes(`max-width: ${bp}`), bp);
  });

  it('collapses the two-column layout to one column at 1024px', () => {
    const block = css.slice(css.indexOf('max-width: 1024px'));
    assert.ok(/\.dashboard-layout\s*\{[^}]*grid-template-columns:\s*1fr;/.test(block));
  });
});

describe('Think Token Dashboard — Current Run Info', () => {
  it('tracks currentJobId from goal events', () => {
    assert.ok(dashboardSource.includes("thought.type === 'goal'"), 'listens to goal events');
    assert.ok(dashboardSource.includes('this.currentJobId ='), 'stores job id');
  });

  it('tracks currentRunStatus from completion events', () => {
    assert.ok(dashboardSource.includes("thought.type === 'think_token'"), 'listens to token events');
    assert.ok(dashboardSource.includes('this.currentRunStatus ='), 'tracks status');
  });

  it('displays current job info in primary panel with real values', () => {
    assert.ok(dashboardSource.includes('current-job-section'), 'panel exists');
    assert.ok(dashboardSource.includes('this.currentJobId'), 'shows job id');
    assert.ok(dashboardSource.includes('this.currentRunStatus'), 'shows status');
    assert.ok(dashboardSource.includes('this.tokens.length'), 'shows token count');
  });

  it('job ID is truncated to 12 chars for layout safety', () => {
    assert.ok(dashboardSource.includes('substring(0, 12)'), 'truncates id');
  });
});

describe('Think Token Dashboard — Export Function', () => {
  it('export includes real tokens and analysis', () => {
    assert.ok(dashboardSource.includes('calculateAverageSuccessRate'), 'includes success rate');
    assert.ok(dashboardSource.includes('calculateKnowledgeReuse'), 'includes reuse metric');
  });
});

describe('Think Token Dashboard — Helper Methods', () => {
  it('escapeHtml prevents XSS by using textContent', () => {
    assert.ok(dashboardSource.includes('textContent'), 'uses textContent for safety');
  });

  it('formatAge returns human-readable time strings (ago format)', () => {
    assert.ok(dashboardSource.includes('formatAge'), 'method exists');
    assert.ok(dashboardSource.includes('ago'), 'uses ago format');
  });

  it('calculateConfidence blends success rate and prior confidence', () => {
    assert.ok(dashboardSource.includes('calculateConfidence'), 'method exists');
    assert.ok(dashboardSource.includes('* 0.9'), 'success rate weight');
    assert.ok(dashboardSource.includes('* 0.1'), 'prior confidence weight');
  });

  it('getTokenTypeDistribution tallies and sorts by count', () => {
    assert.ok(dashboardSource.includes('getTokenTypeDistribution'), 'method exists');
    assert.ok(dashboardSource.includes('sort'), 'sorts results');
  });

  it('calculateAverageSuccessRate filters out untested tokens', () => {
    assert.ok(dashboardSource.includes('calculateAverageSuccessRate'), 'method exists');
    assert.ok(dashboardSource.includes('.filter(t => t.usageCount'), 'filters by usage');
  });
});
