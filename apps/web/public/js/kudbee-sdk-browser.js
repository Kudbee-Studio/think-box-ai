// Kudbee SDK browser helpers (PR #177) — hermetic URL + correlation defaults
(function (global) {
  const SDK_VERSION = '0.1.0';

  function loadConfig() {
    const loc = global.location;
    const proto = loc.protocol === 'https:' ? 'https' : 'http';
    const baseUrl = `${proto}://${loc.hostname}:${loc.port || (proto === 'https' ? '443' : '80')}`;
    const wsProto = loc.protocol === 'https:' ? 'wss' : 'ws';
    const wsUrl = `${wsProto}://${loc.hostname}:${loc.port || (wsProto === 'wss' ? '443' : '80')}/ws`;
    return { SDK_VERSION, baseUrl, wsUrl, correlationHeader: 'x-kudbee-correlation-id' };
  }

  function newCorrelationId() {
    const hex = () => Math.floor(Math.random() * 0xffff).toString(16).padStart(4, '0');
    return `kudbee-${hex()}${hex()}`;
  }

  global.KudbeeSdkBrowser = { loadConfig, newCorrelationId, SDK_VERSION };
})(window);
