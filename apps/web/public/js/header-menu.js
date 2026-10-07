// The header Tools menu: a <details> that closes when a tool is chosen, when you click elsewhere, or on Escape. The buttons inside keep their ids and handlers.
(function () {
  'use strict';
  function init(doc) {
    var menu = doc.getElementById('tools-menu');
    if (!menu) return;
    function close() { menu.removeAttribute('open'); }
    menu.addEventListener('click', function (e) {
      var t = e.target;
      while (t && t !== menu) { if (t.tagName === 'BUTTON') { close(); return; } t = t.parentNode; }
    });
    doc.addEventListener('click', function (e) { if (menu.hasAttribute('open') && !menu.contains(e.target)) close(); });
    doc.addEventListener('keydown', function (e) { if (e.key === 'Escape' && menu.hasAttribute('open')) { close(); var s = menu.querySelector('summary'); if (s) s.focus(); } });
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = { init: init };
  if (typeof document !== 'undefined') init(document);
})();
