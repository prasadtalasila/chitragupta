/* DOM wiring: node never loads it; workbench_smoke.test.js runs it. */
"use strict";
(function () {
  var api = window.CHITRAGUPTA_WORKBENCH;
  var root = document.getElementById("status");

  function storage() {
    try {
      return window.sessionStorage;
    } catch (e) {
      return { getItem: function () { return null; }, setItem: function () {} };
    }
  }

  var token = api.takeToken(window.location, window.history, storage());
  if (!token) {
    api.renderNoToken(document, root);
    return;
  }
  fetch("/api/status", { headers: api.authHeaders(token), cache: "no-store" })
    .then(function (response) {
      if (!response.ok) {
        api.renderRefused(document, root, response.status);
        return null;
      }
      return response.json().then(function (status) {
        api.renderStatus(document, root, status);
      });
    })
    .catch(function () {
      api.renderRefused(document, root, "no answer");
    });
})();
