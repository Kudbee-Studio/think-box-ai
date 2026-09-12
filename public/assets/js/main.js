/**
 * Think Box AI — Frontend JavaScript
 * Wallet, tokens, NFTs, trading, agents, UI components
 */

document.addEventListener('DOMContentLoaded', () => {
  initScrollReveal();
  initMobileMenu();
  initKeyboardShortcuts();
  initWalletState();
  initTokenForm();
});

/* Scroll Reveal */
function initScrollReveal() {
  const elements = document.querySelectorAll('.reveal, .stagger-children');
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('revealed');
        if (entry.target.classList.contains('stagger-children')) {
          entry.target.querySelectorAll(':scope > *').forEach((child, i) => {
            setTimeout(() => child.classList.add('revealed'), i * 100);
          });
        }
      }
    });
  }, { threshold: 0.1 });
  elements.forEach(el => observer.observe(el));
}

/* Mobile Menu */
function toggleMobileMenu() {
  const menu = document.getElementById('mobileMenu');
  menu?.classList.toggle('active');
}

/* Keyboard Shortcuts */
function initKeyboardShortcuts() {
  document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      openCommandPalette();
    }
    if (e.key === 'Escape') {
      closeWalletModal();
      closeCommandPalette();
    }
  });
}

/* Wallet State */
let walletConnected = false;
let walletAddress = '';

function initWalletState() {
  const saved = localStorage.getItem('thinkbox_wallet');
  if (saved) {
    try {
      const data = JSON.parse(saved);
      walletConnected = true;
      walletAddress = data.address;
      updateWalletUI();
    } catch (e) {}
  }
}

function toggleWalletConnect() {
  const modal = document.getElementById('walletModal');
  modal?.classList.toggle('active');
}

function closeWalletModal(e) {
  if (!e || e.target === document.getElementById('walletModal')) {
    document.getElementById('walletModal')?.classList.remove('active');
  }
}

function connectWallet(wallet) {
  showToast(`Connecting to ${wallet}...`, 'info');
  setTimeout(() => {
    const mockAddress = '0x' + Array.from({length: 40}, () => Math.floor(Math.random() * 16).toString(16)).join('');
    walletConnected = true;
    walletAddress = mockAddress;
    localStorage.setItem('thinkbox_wallet', JSON.stringify({ address: mockAddress, wallet }));
    updateWalletUI();
    toggleWalletConnect();
    showToast(`${wallet} connected!`, 'success');
    if (typeof refreshBalance === 'function') refreshBalance();
  }, 1500);
}

function updateWalletUI() {
  const btn = document.getElementById('walletConnectBtn');
  if (btn && walletConnected) {
    btn.textContent = walletAddress.slice(0, 6) + '...' + walletAddress.slice(-4);
    btn.classList.remove('btn-primary');
    btn.classList.add('btn-success');
  }
}

function refreshBalance() {
  const balanceEl = document.getElementById('totalBalance');
  if (balanceEl) {
    balanceEl.innerHTML = '<span class="skeleton" style="width:120px;height:36px;display:inline-block;"></span>';
    setTimeout(() => {
      const sol = (Math.random() * 100 + 10).toFixed(2);
      balanceEl.innerHTML = `◎ ${sol} SOL`;
    }, 1000);
  }
  const priceEl = document.getElementById('solPrice');
  if (priceEl) priceEl.textContent = '$' + (Math.floor(Math.random() * 50) + 80) + '.00';
}

/* Token Form */
function initTokenForm() {
  const form = document.getElementById('tokenForm');
  if (!form) return;
  const inputs = form.querySelectorAll('input, textarea, select');
  inputs.forEach(input => {
    input.addEventListener('input', updateTokenPreview);
  });
}

function updateTokenPreview() {
  const name = document.getElementById('tokenName')?.value || 'Token Name';
  const symbol = document.getElementById('tokenSymbol')?.value || 'SYM';
  const supply = document.getElementById('tokenSupply')?.value || '--';
  const decimals = document.getElementById('tokenDecimals')?.value || '9';

  const previewName = document.getElementById('previewName');
  const previewSymbol = document.getElementById('previewSymbol');
  const previewIcon = document.getElementById('previewIcon');
  const previewSupply = document.getElementById('previewSupply');
  const previewDecimals = document.getElementById('previewDecimals');

  if (previewName) previewName.textContent = name;
  if (previewSymbol) previewSymbol.textContent = symbol.toUpperCase();
  if (previewIcon) previewIcon.textContent = symbol.slice(0, 2).toUpperCase() || '?';
  if (previewSupply) previewSupply.textContent = supply !== '--' ? Number(supply).toLocaleString() : '--';
  if (previewDecimals) previewDecimals.textContent = decimals;
}

function handleTokenCreate(e) {
  e.preventDefault();
  const name = document.getElementById('tokenName')?.value;
  if (!name) { showToast('Enter a token name', 'error'); return; }
  showToast('Token creation coming soon on devnet!', 'info');
}

/* Swap */
function updateSwapQuote() {
  const amount = parseFloat(document.getElementById('swapAmount')?.value) || 0;
  const rate = 100 + Math.random() * 50;
  const output = (amount / rate).toFixed(6);
  const outputEl = document.getElementById('swapOutput');
  const rateEl = document.getElementById('swapRate');
  if (outputEl) outputEl.value = output;
  if (rateEl) rateEl.textContent = `1 SOL ≈ ${rate.toFixed(2)} USDC`;
}

function swapDirection() {
  const fromBtn = document.getElementById('fromTokenSelect');
  const toBtn = document.getElementById('toTokenSelect');
  if (fromBtn && toBtn) {
    const tmp = fromBtn.textContent;
    fromBtn.textContent = toBtn.textContent;
    toBtn.textContent = tmp;
  }
  updateSwapQuote();
}

function executeSwap() {
  if (!walletConnected) { toggleWalletConnect(); return; }
  showToast('Swap execution coming soon!', 'info');
}

/* Toast */
function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span class="toast-message">${message}</span><span class="toast-close" onclick="this.parentElement.remove()">×</span>`;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

/* Command Palette */
function openCommandPalette() {
  const palette = document.getElementById('commandPalette');
  palette?.classList.add('active');
  const input = document.getElementById('commandInput');
  if (input) setTimeout(() => input.focus(), 100);
}

function closeCommandPalette(e) {
  if (!e || e.target === document.getElementById('commandPalette')) {
    document.getElementById('commandPalette')?.classList.remove('active');
  }
}

function navigateTo(path) {
  closeCommandPalette();
  window.location.href = path;
}

/* PWA Service Worker */
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  });
}
