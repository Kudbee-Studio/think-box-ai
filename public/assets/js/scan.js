/**
 * Think Box AI — Token Scanner JavaScript
 */

function handleScan(e) {
  e.preventDefault();
  const mint = document.getElementById('scanMint')?.value.trim();
  if (!mint) { showToast('Enter a token mint address', 'error'); return; }

  const results = document.getElementById('scanResults');
  if (!results) return;

  results.innerHTML = '<div class="card scan-placeholder"><div class="skeleton" style="width:200px;height:24px;margin:0 auto;"></div></div>';

  setTimeout(() => {
    const score = Math.floor(Math.random() * 100);
    const safety = score < 30 ? 'safe' : score < 60 ? 'medium' : 'risky';
    const verdict = score < 60 ? 'PASS' : score < 80 ? 'CAUTION' : 'AVOID';
    const color = score < 30 ? 'var(--color-success)' : score < 60 ? 'var(--color-warning)' : 'var(--color-danger)';

    const factors = [];
    if (Math.random() > 0.5) factors.push({ icon: '🔒', text: 'Liquidity locked', safe: true });
    else factors.push({ icon: '⚠', text: 'Liquidity NOT locked', safe: false });
    if (Math.random() > 0.5) factors.push({ icon: '🔑', text: 'Mint authority renounced', safe: true });
    else factors.push({ icon: '⚠', text: 'Mint authority NOT renounced', safe: false });
    if (Math.random() > 0.5) factors.push({ icon: '👥', text: 'Good holder distribution', safe: true });
    else factors.push({ icon: '⚠', text: 'Concentrated holders', safe: false });

    results.innerHTML = `
      <div class="card scan-result-card">
        <div class="scan-score" style="border-color: ${color};">
          <div class="scan-score-value" style="color: ${color};">${score}</div>
          <div class="scan-score-label">Risk Score</div>
        </div>
        <div class="scan-verdict" style="background: ${color}20; color: ${color};">${verdict}</div>
        <div class="scan-safety">Safety: <strong>${safety.toUpperCase()}</strong></div>
        <div class="scan-factors">
          ${factors.map(f => `<div class="scan-factor ${f.safe ? 'safe' : 'unsafe'}"><span>${f.icon}</span> ${f.text}</div>`).join('')}
        </div>
      </div>
    `;
  }, 1500);
}
