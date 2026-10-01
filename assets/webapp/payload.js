/* What the app needs of data.js, and the one place that knows which
   edge list, weight and evidence belong to which family.

   The check is the first thing app.js runs. Before it, a missing,
   truncated or hand-edited data.js threw on the first dereference,
   before any handler was wired, and the reader saw the help text
   describing controls that did nothing -- the only evidence was in the
   console (#855). `REQUIRED_KEYS` is what the exporter cannot do
   without, measured from `_page.build_payload` by
   tests/test_discover_app.py rather than listed twice by hand; a key the
   exporter reads with `.get` (communities, paths, edges_withheld) is
   one an older artefact may lack, and is the reading module's to
   default, not this one's to refuse.

   The accessors were three copies, in ego.js, families.js and graph.js,
   one of them with a `|| []` the others lacked (#860). Loaded ahead of
   every module that reads an edge, and tested without a DOM by
   tests/webapp/payload.test.js. */
"use strict";

(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.CHITRAGUPTA_APP = Object.assign(root.CHITRAGUPTA_APP || {}, api);
  }
})(typeof self !== "undefined" ? self : this, function () {
  var REQUIRED_KEYS = ["topics", "edges_overlap", "edges_semantic", "hierarchy", "n_docs"];
  var NUMBERS = new Set(["n_docs"]);

  /* Every problem at once, in REQUIRED_KEYS order, rather than the
     first: a reader repairing data.js by hand should not have to reload
     once per key to learn what else is wrong. */
  function payloadProblems(data) {
    var held = data !== null && typeof data === "object" ? data : {};
    var problems = [];
    REQUIRED_KEYS.forEach(function (key) {
      if (held[key] === undefined) {
        problems.push(key + " (missing)");
      } else if (NUMBERS.has(key) && typeof held[key] !== "number") {
        problems.push(key + " (not a number)");
      } else if (!NUMBERS.has(key) && !Array.isArray(held[key])) {
        problems.push(key + " (not a list)");
      }
    });
    return problems;
  }

  function edgesOf(data, family) {
    return family === "overlap" ? data.edges_overlap : data.edges_semantic;
  }

  function weightOf(family, edge) {
    return family === "overlap" ? edge.overlap_coeff : edge.similarity;
  }

  /* The citekeys that justify an edge: the papers both topics hold, or
     the closest pair of papers that bridges two semantically near ones. */
  function evidenceOf(family, edge) {
    return family === "overlap" ? edge.shared : edge.bridge;
  }

  return {
    REQUIRED_KEYS: REQUIRED_KEYS,
    payloadProblems: payloadProblems,
    edgesOf: edgesOf,
    weightOf: weightOf,
    evidenceOf: evidenceOf,
  };
});
