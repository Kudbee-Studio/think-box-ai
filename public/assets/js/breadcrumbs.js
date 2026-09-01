/**
 * Think Box AI — Breadcrumb Generator
 * Auto-generates breadcrumb navigation based on URL path
 */

function generateBreadcrumbs() {
  const path = window.location.pathname;
  const parts = path.split('/').filter(Boolean);

  const crumbs = [{ name: 'Home', url: '/' }];
  let currentPath = '';

  const nameMap = {
    'collections': 'Collections',
    'tokens': 'DRC-20 Tokens',
    'activity': 'Activity',
    'tracker': 'Tracker',
    'inscribe': 'Inscribe',
    'wallet': 'Wallet',
    'security': 'Security',
    'about': 'About',
    'blog': 'Blog',
    'search': 'Search',
    'detail': 'Detail',
  };

  parts.forEach((part, i) => {
    currentPath += '/' + part;
    const name = nameMap[part] || part.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    const isLast = i === parts.length - 1;
    crumbs.push({ name, url: isLast ? null : currentPath + '/' });
  });

  return crumbs;
}

function renderBreadcrumbs() {
  const container = document.getElementById('breadcrumbs');
  if (!container) return;

  const crumbs = generateBreadcrumbs();
  container.innerHTML = crumbs.map((crumb, i) => {
    if (i === crumbs.length - 1) {
      return `<span class="current">${crumb.name}</span>`;
    }
    return `<a href="${crumb.url}">${crumb.name}</a><span class="separator">/</span>`;
  }).join('');
}

document.addEventListener("DOMContentLoaded", renderBreadcrumbs);
