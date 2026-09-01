/**
 * Think Box AI — Tokens Page JavaScript
 */

document.addEventListener('DOMContentLoaded', () => {
  initTokensPage();
});

function initTokensPage() {
  const form = document.getElementById('tokenForm');
  if (form) {
    form.addEventListener('submit', handleTokenCreate);
  }
}

function handleTokenCreate(e) {
  e.preventDefault();
  const name = document.getElementById('tokenName')?.value;
  const symbol = document.getElementById('tokenSymbol')?.value;
  const supply = document.getElementById('tokenSupply')?.value;

  if (!name || !symbol || !supply) {
    showToast('Please fill in all required fields', 'error');
    return;
  }

  showToast(`Token "${name}" (${symbol}) creation coming soon!`, 'info');
}
