/* The workbench page's DOM wiring (#1262): take the token, ask the
   server for its status, show the answer.

   Runs only in a browser; node never loads it. The headless-browser
   smoke test (tests/webapp/workbench_smoke.test.js) is what runs it. */
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
