// Classic-script twin of escape-html.js (modules import that one). Defines window.escapeHtml for the panels that are not ES modules.
// Escape every value that reaches innerHTML / insertAdjacentHTML unless it is a number or a constant you wrote yourself.
window.escapeHtml = function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
};
