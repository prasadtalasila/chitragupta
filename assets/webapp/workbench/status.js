/* What the placeholder workbench shows (#1262): the project and version
   from GET /api/status, or how to get a working URL.

   Built from elements and textContent only, never from markup strings:
   a project directory named `<img onerror=...>` must show as those
   characters. Tested without a DOM by tests/webapp/workbench_status.test.js. */
"use strict";

(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.CHITRAGUPTA_WORKBENCH = Object.assign(root.CHITRAGUPTA_WORKBENCH || {}, api);
  }
})(typeof self !== "undefined" ? self : this, function () {
  var HINT = "Open the URL printed in the terminal where you ran chitragupta webapp.";

  function element(doc, tag, text) {
    var node = doc.createElement(tag);
    node.textContent = text;
    return node;
  }

  function show(doc, root, lines) {
    var nodes = [element(doc, "h1", "chitragupta workbench")];
    lines.forEach(function (line) {
      nodes.push(element(doc, "p", line));
    });
    root.replaceChildren.apply(root, nodes);
  }

  function renderStatus(doc, root, status) {
    show(doc, root, [
      "Project: " + status.project,
      "Version: " + status.version,
      "Connected. The corpus, paper and agent panes arrive with WA-1.",
    ]);
  }

  function renderNoToken(doc, root) {
    show(doc, root, ["This page has no token. " + HINT]);
  }

  function renderRefused(doc, root, code) {
    show(doc, root, ["The server refused this page (" + code + "). " + HINT]);
  }

  return { renderStatus: renderStatus, renderNoToken: renderNoToken, renderRefused: renderRefused };
});
