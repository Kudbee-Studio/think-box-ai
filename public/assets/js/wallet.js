document.addEventListener('DOMContentLoaded', () => {
  initWalletPage();
});

function initWalletPage() {
  refreshBalance();
  loadTokenHoldings();
  simulateAIInsights();
}

function loadTokenHoldings() {
  const list = document.getElementById('tokenList');
  if (!list) return;
  const tokens = [
    { symbol: 'SOL', name: 'Solana', balance: '--', usd: '--', change: '+2.4%' },
    { symbol: 'USDC', name: 'USD Coin', balance: '--', usd: '--', change: '0.0%' },
  ];
  setTimeout(() => {
    list.innerHTML = tokens.map(t => `
      <div class="card token-item">
        <div class="token-icon">${t.symbol.slice(0, 3)}</div>
        <div class="token-info">
          <div class="token-name">${t.name}</div>
          <div class="token-balance">${t.balance}</div>
        </div>
        <div class="token-value">
          <div class="token-usd">${t.usd}</div>
          <div class="token-change ${t.change.startsWith('+') ? 'positive' : 'negative'}">${t.change}</div>
        </div>
      </div>
    `).join('');
  }, 1500);
}

function simulateAIInsights() {
  const scoreEl = document.querySelector('.insight-score');
  if (scoreEl) {
    setTimeout(() => {
      scoreEl.textContent = 'Low';
      scoreEl.className = 'insight-score score-low';
    }, 2000);
  }
}
