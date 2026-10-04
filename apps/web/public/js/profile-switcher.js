// Profile switcher — the dashboard header control for named profiles with isolated memory.
//
// The server owns the profiles (SQLite + per-profile memory folders and run files); this file only reads
// and switches them. `ProfileStore` is the pure part (no DOM) and is exercised by node tests; the
// `mountProfileSwitcher` half turns it into a dropdown.
//
// Loaded as a classic script (window.profileSwitcher). Escape every server value with textContent, never
// innerHTML (AGENTS.md hardening rule).
(function (root) {
  'use strict';

  var API = '/api/profiles';

  function fetchJson(url, init) {
    return fetch(url, Object.assign({ cache: 'no-store' }, init || {})).then(function (res) {
      return res.json().catch(function () { return {}; }).then(function (body) {
        if (!res.ok) throw new Error(body && body.error ? body.error : 'HTTP ' + res.status);
        return body;
      });
    });
  }

  /** Pure state holder: the profile list, the active id, and the API calls that change them. */
  function ProfileStore(options) {
    options = options || {};
    this.request = options.request || fetchJson;
    this.profiles = [];
    this.active = null;
    this.onChange = typeof options.onChange === 'function' ? options.onChange : function () {};
  }

  ProfileStore.prototype.refresh = function () {
    var self = this;
    return this.request(API).then(function (data) {
      self.profiles = Array.isArray(data.profiles) ? data.profiles : [];
      self.active = data.active || null;
      self.onChange(self.snapshot());
      return self.snapshot();
    });
  };

  ProfileStore.prototype.snapshot = function () {
    return { profiles: this.profiles.slice(), active: this.active };
  };

  ProfileStore.prototype.activeProfile = function () {
    var self = this;
    return this.profiles.filter(function (p) { return p.id === self.active; })[0] || null;
  };

  ProfileStore.prototype.create = function (name) {
    var self = this;
    return this.request(API, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: name }) })
      .then(function (profile) { return self.setActive(profile.id).then(function () { return profile; }); });
  };

  ProfileStore.prototype.setActive = function (id) {
    var self = this;
    return this.request(API + '/' + encodeURIComponent(id) + '/activate', { method: 'POST' })
      .then(function () { return self.refresh(); });
  };

  ProfileStore.prototype.rename = function (id, name) {
    return this.request(API + '/' + encodeURIComponent(id), { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: name }) })
      .then(this.refresh.bind(this));
  };

  ProfileStore.prototype.remove = function (id) {
    return this.request(API + '/' + encodeURIComponent(id), { method: 'DELETE' })
      .then(this.refresh.bind(this));
  };

  ProfileStore.prototype.exportProfile = function (id) {
    return this.request(API + '/' + encodeURIComponent(id) + '/export');
  };

  ProfileStore.prototype.importProfile = function (bundle) {
    var self = this;
    return this.request(API + '/import', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(bundle) })
      .then(function (profile) { return self.refresh().then(function () { return profile; }); });
  };

  /** Turn the DOM dropdown into a live control. `root` is where the element lives; `document` may be a stub in tests. */
  function mountProfileSwitcher(store, options) {
    options = options || {};
    var doc = options.document || (root && root.document);
    if (!doc) return null;
    var container = options.container || doc.getElementById('profile-switcher');
    if (!container) return null;
    var select = container.querySelector('#profile-select');
    var status = container.querySelector('#profile-status');
    if (!select) return null;

    function render() {
      var snapshot = store.snapshot();
      select.textContent = '';
      snapshot.profiles.forEach(function (profile) {
        var opt = doc.createElement('option');
        opt.value = profile.id;
        opt.textContent = profile.name + (profile.id === snapshot.active ? ' ✓' : '');
        if (profile.id === snapshot.active) opt.selected = true;
        select.appendChild(opt);
      });
      var addOpt = doc.createElement('option');
      addOpt.value = '__new__';
      addOpt.textContent = '＋ New profile';
      select.appendChild(addOpt);
      if (status) status.textContent = (store.activeProfile() || {}).name || '';
    }

    function notify(message, isError) {
      if (!status) return;
      status.textContent = message;
      status.className = 'profile-status' + (isError ? ' error' : '');
    }

    select.addEventListener('change', function () {
      var value = select.value;
      if (value === '__new__') {
        var name = (options.prompt ? options.prompt('New profile name', '') : root.prompt ? root.prompt('New profile name', '') : '');
        if (!name) { render(); return; }
        store.create(name).then(render).catch(function (err) { notify(String(err.message || err), true); render(); });
        return;
      }
      store.setActive(value).then(function () { render(); notify('Switched'); }).catch(function (err) { notify(String(err.message || err), true); render(); });
    });

    var priorOnChange = store.onChange;
    store.onChange = function (snapshot) { render(); priorOnChange(snapshot); };
    return store.refresh().then(render).catch(function (err) { notify(String(err.message || err), true); });
  }

  root.ProfileStore = ProfileStore;
  root.mountProfileSwitcher = mountProfileSwitcher;
  if (typeof module !== 'undefined' && module.exports) { module.exports = { ProfileStore: ProfileStore, mountProfileSwitcher: mountProfileSwitcher }; }
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
