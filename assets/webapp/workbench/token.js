/* The launch token: from the URL fragment into sessionStorage, and out
   of the address bar (#1262).

   `chitragupta webapp` prints http://127.0.0.1:PORT/#token=... A fragment
   is never sent to the server, so the token stays out of its logs and of
   any Referer. On load the page keeps it in sessionStorage, which is
   scoped to this scheme, host *and port* -- unlike a cookie on
   127.0.0.1, which every port on the host would receive -- and removes it
   from the address bar so it is not left in history or a screenshot.

   Tested without a DOM by tests/webapp/workbench_token.test.js. */
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
      /* Private mode: this page load still has the token. */
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
