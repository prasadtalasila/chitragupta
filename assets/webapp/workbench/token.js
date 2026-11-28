/* The token arrives in the URL fragment, which no server receives. It is
   kept in sessionStorage, scoped to this port, never in a cookie, which
   every port on 127.0.0.1 would receive. */
"use strict";

(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.CHITRAGUPTA_WORKBENCH = Object.assign(root.CHITRAGUPTA_WORKBENCH || {}, api);
  }
})(typeof self !== "undefined" ? self : this, function () {
  var STORAGE_KEY = "chitragupta.token";

  function fragmentToken(location) {
    var params = new URLSearchParams((location.hash || "").replace(/^#/, ""));
    return params.has("token") ? params.get("token") : null;
  }

  function remember(storage, value) {
    try {
      storage.setItem(STORAGE_KEY, value);
    } catch (e) {
      return;
    }
  }

  function recall(storage) {
    try {
      return storage.getItem(STORAGE_KEY) || null;
    } catch (e) {
      return null;
    }
  }

  function takeToken(location, history, storage) {
    var fromUrl = fragmentToken(location);
    if (fromUrl === null) return recall(storage);
    history.replaceState(null, "", location.pathname);
    if (!fromUrl) return null;
    remember(storage, fromUrl);
    return fromUrl;
  }

  function authHeaders(token) {
    return { Authorization: "Bearer " + token };
  }

  return { STORAGE_KEY: STORAGE_KEY, takeToken: takeToken, authHeaders: authHeaders };
});
