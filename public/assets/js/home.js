/**
 * Think Box AI — Home page rendering
 */

function renderCollections() {
  const grid = document.getElementById("featuredCollections");
  if (!grid) return;

  grid.innerHTML = LOCAL_DATA.collections.map(c => `
    <a href="collections/${c.slug}/" class="card collection-card" style="text-decoration: none; color: inherit;">
      <div class="collection-icon" style="width: 100%; aspect-ratio: 1; background: var(--color-bg); border-radius: var(--radius-lg); display: flex; align-items: center; justify-content: center; font-size: var(--text-5xl); margin-bottom: var(--space-4);">
        🐕
      </div>
      <h4 style="margin-bottom: var(--space-2);">${c.name}</h4>
      <div style="display: flex; justify-content: space-between; font-size: var(--text-sm);">
        <span class="text-muted">Floor</span>
        <span style="font-weight: var(--font-semibold);">◎ ${c.floor}</span>
      </div>
      <div style="display: flex; justify-content: space-between; font-size: var(--text-sm); margin-top: var(--space-1);">
        <span class="text-muted">24h Vol</span>
        <span>${c.volume24h.toLocaleString()}</span>
      </div>
    </a>
  `).join("");
}

function renderActivity() {
  const feed = document.getElementById("liveActivity");
  if (!feed) return;

  feed.innerHTML = LOCAL_DATA.activity.slice(0, 6).map(a => `
    <div class="activity-item">
      <div class="activity-icon ${a.type}">${a.type === 'sale' ? '💰' : a.type === 'list' ? '📋' : '↗️'}</div>
      <div style="flex: 1;">
        <span style="font-weight: var(--font-medium);">${a.inscription}</span>
        <span class="text-muted"> — ${a.type}</span>
      </div>
      <div style="text-align: right;">
        ${a.price > 0 ? `<span style="font-weight: var(--font-semibold);">◎ ${a.price}</span>` : '<span class="text-muted">—</span>'}
        <div class="text-muted" style="font-size: var(--text-xs);">${a.time}</div>
      </div>
    </div>
  `).join("");
}

function renderTokenTicker() {
  const ticker = document.getElementById("tokenTicker");
  if (!ticker) return;

  ticker.innerHTML = LOCAL_DATA.tokens.map(t => `
    <div class="token-row">
      <span class="token-ticker">${t.ticker.toUpperCase()}</span>
      <span class="token-name">${t.name}</span>
      <span style="font-weight: var(--font-semibold);">$${t.price.toFixed(4)}</span>
      <span style="color: ${t.change24h >= 0 ? 'var(--color-success)' : 'var(--color-danger)'};">
        ${t.change24h >= 0 ? '+' : ''}${t.change24h}%
      </span>
      <span class="text-muted">Vol $${t.volume24h.toLocaleString()}</span>
    </div>
  `).join("");
}

function connectWallet() {
  alert("Wallet connection coming soon! Use Woof Wallet or Unisat.");
}

document.addEventListener("DOMContentLoaded", () => {
  renderCollections();
  renderActivity();
  renderTokenTicker();
});
