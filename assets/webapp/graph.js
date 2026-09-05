/* The payload logic behind the canvas: which topics are visible, what
   cytoscape is handed, and what the type-ahead offers.

   Split out of app.js so it can be tested without a DOM and without
   cytoscape (tests/webapp/graph.test.js runs it under `node --test`).
   Nothing here derives an edge or a membership -- every number it reads
   was computed once by `chitragupta enrich` -- so the app still cannot
   disagree with the terminal views.

   Loaded as a classic script, not an ES module: `import` from file://
   is blocked as a cross-origin request, and the exported directory has
   to open with no server, forever. The tail below is what lets the same
   file be a browser global and a node require. */
"use strict";

(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.CHITRAGUPTA_APP = Object.assign(root.CHITRAGUPTA_APP || {}, api);
  }
})(typeof self !== "undefined" ? self : this, function () {
  /* Null prototypes on every table keyed by data-derived strings
     (topic labels, origins): on a plain object a topic literally
     labelled "__proto__" reads back Object.prototype -- truthy, so it
     slips past `||` fallbacks and has no .add -- which crashed the
     whole render (#636). */
  var ORIGIN_COLORS = Object.assign(Object.create(null), {
    seed: "#2e7d32",
    keyword: "#b8860b",
    both: "#00695c",
    emergent: "#1565c0",
  });
  var ORIGIN_LABELS = Object.assign(Object.create(null), {
    seed: "seed topic",
    keyword: "keyword topic",
    both: "seed + keyword topic",
    emergent: "emergent topic",
  });

  function byLabel(topics) {
    var index = Object.create(null);
    topics.forEach(function (t) { index[t.label] = t; });
    return index;
  }

  // Direct neighbours over both edge families, precomputed once: the
  // filter's "related" set is exactly this adjacency.
  function adjacency(data) {
    var neighbours = Object.create(null);
    function add(a, b) {
      (neighbours[a] = neighbours[a] || new Set()).add(b);
      (neighbours[b] = neighbours[b] || new Set()).add(a);
    }
    data.edges_overlap.forEach(function (e) { add(e.a, e.b); });
    data.edges_semantic.forEach(function (e) { add(e.a, e.b); });
    return neighbours;
  }

  function visibleLabels(data, selected, neighbours) {
    if (!selected.length) {
      return new Set(data.topics.map(function (t) { return t.label; }));
    }
    var visible = new Set(selected);
    selected.forEach(function (label) {
      (neighbours[label] || new Set()).forEach(function (n) { visible.add(n); });
    });
    return visible;
  }

  function nodeSize(topic) {
    return 22 + 9 * Math.sqrt(topic.members.length);
  }

  function elementsFor(data, visible, selected) {
    var els = [];
    data.topics.forEach(function (t) {
      if (!visible.has(t.label)) { return; }
      els.push({
        group: "nodes",
        data: {
          id: t.label,
          label: t.label,
          origin: t.origin,
          color: ORIGIN_COLORS[t.origin] || ORIGIN_COLORS.emergent,
          size: nodeSize(t),
          picked: selected.indexOf(t.label) >= 0 ? 1 : 0,
        },
      });
    });
    data.edges_overlap.forEach(function (e, i) {
      if (!visible.has(e.a) || !visible.has(e.b)) { return; }
      els.push({
        group: "edges",
        data: {
          id: "ov-" + i, source: e.a, target: e.b, family: "overlap",
          width: 1.5 + 6 * e.overlap_coeff, index: i,
        },
      });
    });
    data.edges_semantic.forEach(function (e, i) {
      if (!visible.has(e.a) || !visible.has(e.b)) { return; }
      els.push({
        group: "edges",
        data: {
          id: "se-" + i, source: e.a, target: e.b, family: "semantic",
          width: 1 + 3 * e.similarity, index: i,
        },
      });
    });
    return els;
  }

  function candidatesFor(data, selected, query) {
    var needle = query.trim().toLowerCase();
    if (!needle) { return []; }
    var out = [];
    data.topics.forEach(function (t) {
      if (selected.indexOf(t.label) >= 0) { return; }
      if (t.label.toLowerCase().indexOf(needle) >= 0) {
        out.push({ label: t.label, why: ORIGIN_LABELS[t.origin] || t.origin });
        return;
      }
      var term = t.terms.find(function (word) {
        return word.toLowerCase().indexOf(needle) >= 0;
      });
      if (term) { out.push({ label: t.label, why: "term: " + term }); }
    });
    return out.slice(0, 12);
  }

  function findMember(data, citekey) {
    for (var i = 0; i < data.topics.length; i++) {
      var members = data.topics[i].members;
      for (var j = 0; j < members.length; j++) {
        if (members[j].citekey === citekey) { return members[j]; }
      }
    }
    return null;
  }

  return {
    ORIGIN_COLORS: ORIGIN_COLORS,
    ORIGIN_LABELS: ORIGIN_LABELS,
    byLabel: byLabel,
    adjacency: adjacency,
    visibleLabels: visibleLabels,
    nodeSize: nodeSize,
    elementsFor: elementsFor,
    candidatesFor: candidatesFor,
    findMember: findMember,
  };
});
