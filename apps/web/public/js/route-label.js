// One short line saying who answered a goal and how (mirrors routeLabel() in route-decision.ts; the dashboard cannot import TypeScript).
(function (root) {
  'use strict';
  var PATH_LABEL = { recipe: 'recipe', local_chat: 'local chat', escalated: 'escalated', agent: 'worker agent', refused: 'refused' };
  function routeLabel(route) {
    if (!route || typeof route !== 'object' || !Object.prototype.hasOwnProperty.call(PATH_LABEL, route.path)) return '';
    var via = route.path === 'escalated' && route.requested_model ? route.requested_model + ' → ' + route.model : (route.model || 'no model');
    return 'route: ' + PATH_LABEL[route.path] + ' · ' + via + (route.recipe ? ' · ' + route.recipe : '');
  }
  root.routeLabel = routeLabel;
  if (typeof module !== 'undefined' && module.exports) module.exports = { routeLabel: routeLabel };
})(typeof window !== 'undefined' ? window : globalThis);
