/**
 * Think Box AI — Main JavaScript
 * Shared across all pages
 */

function toggleMobileMenu() {
  const menu = document.getElementById("mobileMenu");
  if (menu) menu.classList.toggle("active");
}

function connectWallet() {
  showToast("Wallet connection coming soon! Use Woof Wallet or Unisat.", "info");
}

// Intersection Observer for scroll animations
function initScrollReveal() {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) entry.target.classList.add("visible");
    });
  }, { threshold: 0.1 });

  document.querySelectorAll(".reveal").forEach(el => observer.observe(el));
}

document.addEventListener("DOMContentLoaded", initScrollReveal);
