/**
 * Shared control-plane ETag store across tabs (PR #140).
 * Persists conditional GET cache to sessionStorage — hermetic only.
 */
(function (global) {
  var STORAGE_KEY = "thinkbox.control_plane.etag_store.v1";
  var SCHEMA_VERSION = 1;
  var MAX_ENTRIES = 256;
  var BODY_SUFFIX = ":body";

  function pruneStore(store) {
    var urlKeys = Object.keys(store).filter(function (k) {
      return k.indexOf(BODY_SUFFIX) < 0;
    });
    if (urlKeys.length <= MAX_ENTRIES) return;
    urlKeys.slice(0, urlKeys.length - MAX_ENTRIES).forEach(function (key) {
      delete store[key];
      delete store[key + BODY_SUFFIX];
    });
  }

  function deserialize(raw) {
    if (!raw) return {};
    try {
      var doc = JSON.parse(raw);
      if (!doc || doc.version !== SCHEMA_VERSION || !doc.entries) return {};
      var out = {};
      Object.keys(doc.entries).forEach(function (k) {
        out[k] = doc.entries[k];
      });
      pruneStore(out);
      return out;
    } catch (e) {
      return {};
    }
  }

  function serialize(store) {
    return JSON.stringify({
      version: SCHEMA_VERSION,
      entries: store,
    });
  }

  function persistStore(store) {
    if (typeof sessionStorage === "undefined") return;
    try {
      sessionStorage.setItem(STORAGE_KEY, serialize(store));
    } catch (e) {
      /* quota — hermetic degrade */
    }
  }

  function loadSharedBacking() {
    if (typeof sessionStorage === "undefined") return {};
    return deserialize(sessionStorage.getItem(STORAGE_KEY));
  }

  /**
   * Returns a plain object compatible with TBLoadPerf.fetchJsonConditional.
   * Mutations persist to sessionStorage for other control-plane tabs.
   */
  function getSharedEtagStore() {
    var backing = loadSharedBacking();
    backing.__tbShared = true;
    backing.__tbPersist = function () {
      persistStore(backing);
    };
    return backing;
  }

  function mergeIntoStore(target, source) {
    if (!source) return target;
    Object.keys(source).forEach(function (k) {
      if (k === "__tbShared" || k === "__tbPersist") return;
      target[k] = source[k];
    });
    pruneStore(target);
    if (target.__tbPersist) target.__tbPersist();
    return target;
  }

  global.TBControlPlaneEtag = {
    STORAGE_KEY: STORAGE_KEY,
    getSharedEtagStore: getSharedEtagStore,
    mergeIntoStore: mergeIntoStore,
    deserialize: deserialize,
    serialize: serialize,
    persistStore: persistStore,
  };
})(typeof window !== "undefined" ? window : globalThis);
