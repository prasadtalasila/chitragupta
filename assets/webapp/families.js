/* The two edge families as two graphs: clustered separately, walked
   separately, and compared where they disagree.

   The design's bet is that overlap and semantic nearness answer
   different questions and that their disagreement is itself a discovery
   cue. Two topics in one semantic cluster that share no papers are a
   literature that has not met itself; two that share papers and land in
   different semantic clusters are usually a terminology split. Until
   this module those readings existed only as a sentence in the
   documentation.

   Everything here is view-derived, and that is what makes it allowed at
   all: `docs/TOPIC-DISCOVERY-GRAPH.md` §2 sends a *stored* community
   assignment to the builder, because a partition the terminal cannot
   confirm would be a new claim about the corpus. Computed in the
   reader's browser, at an inflation they can move, labelled as the
   view's own and written back nowhere, it is not that claim.

   Never fused. One partition over a merged graph, or one path over a
   combined weight, destroys the disagreement this module exists to
   surface. Tested without a DOM by tests/webapp/families.test.js. */
"use strict";

(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.CHITRAGUPTA_APP = Object.assign(root.CHITRAGUPTA_APP || {}, api);
  }
})(typeof self !== "undefined" ? self : this, function () {
  var MAX_ITERATIONS = 40;
  var EPSILON = 1e-6;
  // The disagreement lists are pairs, so they grow with the square of a
  // cluster: a cap is needed, and a silent one would read as "that is
  // all there is". Whatever is dropped is counted and reported.
  var MAX_PAIRS = 200;

  function edgesOf(data, family) {
    return family === "overlap" ? data.edges_overlap : data.edges_semantic;
  }

  function weightOf(family, edge) {
    return family === "overlap" ? edge.overlap_coeff : edge.similarity;
  }

  function evidenceOf(family, edge) {
    return family === "overlap" ? edge.shared : edge.bridge;
  }

  /* ---------- Markov clustering, one family at a time ----------

     Expand, inflate, renormalise, until the matrix stops moving. Written
     out rather than taken from cytoscape's own `markovClustering`
     because that call needs a live canvas: this way the clustering runs
     in a test with no browser at all, which is the only way the numbers
     the reader is shown can be checked.

     MCL is deterministic given the same input and inflation -- so the
     view is reproducible from the page alone, provided the page shows
     the inflation it used. It does. */
  function cluster(data, family, inflation) {
    var labels = data.topics.map(function (t) { return t.label; });
    var n = labels.length;
    var index = Object.create(null);
    labels.forEach(function (label, i) { index[label] = i; });

    var m = new Float64Array(n * n);
    // Self-loops: without them a node's own mass leaks away entirely on
    // the first expansion and single-edge chains dissolve.
    for (var i = 0; i < n; i++) { m[i * n + i] = 1; }
    edgesOf(data, family).forEach(function (edge) {
      var a = index[edge.a], b = index[edge.b];
      if (a === undefined || b === undefined) { return; }
      var w = weightOf(family, edge);
      m[a * n + b] = w;
      m[b * n + a] = w;
    });

    normalise(m, n);
    for (var step = 0; step < MAX_ITERATIONS; step++) {
      var next = inflate(multiply(m, m, n), n, inflation);
      normalise(next, n);
      var moved = 0;
      for (var k = 0; k < next.length; k++) {
        moved = Math.max(moved, Math.abs(next[k] - m[k]));
      }
      m = next;
      if (moved < EPSILON) { break; }
    }
    return readClusters(m, n, labels);
  }

  function multiply(a, b, n) {
    var out = new Float64Array(n * n);
    for (var i = 0; i < n; i++) {
      for (var k = 0; k < n; k++) {
        var left = a[i * n + k];
        if (!left) { continue; }
        for (var j = 0; j < n; j++) { out[i * n + j] += left * b[k * n + j]; }
      }
    }
    return out;
  }

  function inflate(m, n, power) {
    for (var k = 0; k < m.length; k++) { m[k] = Math.pow(m[k], power); }
    return m;
  }

  // Column-stochastic: each column is where one topic's mass goes.
  function normalise(m, n) {
    for (var j = 0; j < n; j++) {
      var sum = 0;
      for (var i = 0; i < n; i++) { sum += m[i * n + j]; }
      if (!sum) { continue; }
      for (i = 0; i < n; i++) { m[i * n + j] /= sum; }
    }
  }

  /* After convergence a row with mass in it is an attractor, and the
     columns it holds are its cluster. A column can be held by more than
     one attractor -- MCL does not promise a partition -- so the first
     attractor by payload order takes it, and anything unclaimed stands
     alone. Deterministic, and every topic lands in exactly one place. */
  function readClusters(m, n, labels) {
    var clusterOf = Object.create(null);
    var clusters = [];
    for (var i = 0; i < n; i++) {
      var members = [];
      for (var j = 0; j < n; j++) {
        if (m[i * n + j] > EPSILON && clusterOf[labels[j]] === undefined) {
          members.push(labels[j]);
        }
      }
      if (!members.length) { continue; }
      var id = "mcl-" + clusters.length;
      members.forEach(function (label) { clusterOf[label] = id; });
      clusters.push({ id: id, members: members });
    }
    labels.forEach(function (label) {
      if (clusterOf[label] !== undefined) { return; }
      var id = "mcl-" + clusters.length;
      clusterOf[label] = id;
      clusters.push({ id: id, members: [label] });
    });
    return { clusters: clusters, clusterOf: clusterOf };
  }

  /* ---------- where the two partitions disagree ---------- */

  function sharedCount(data, a, b) {
    var topics = Object.create(null);
    data.topics.forEach(function (t) { topics[t.label] = t; });
    var mine = new Set((topics[a].members || []).map(function (m) { return m.citekey; }));
    return (topics[b].members || []).filter(function (m) {
      return mine.has(m.citekey);
    }).length;
  }

  /* The co-membership grid, in both directions:

     - `semanticOnly` -- one semantic cluster, different paper-sharing
       clusters. Where these share *no* papers at all, that is a
       literature which has not met itself.
     - `overlapOnly` -- one paper-sharing cluster, different semantic
       clusters. Usually a terminology split worth naming in a draft.

     Sorted so the sharpest disagreement is first, and capped, with what
     was dropped reported rather than silently cut. */
  function disagreement(data, inflation) {
    var overlap = cluster(data, "overlap", inflation);
    var semantic = cluster(data, "semantic", inflation);
    var labels = data.topics.map(function (t) { return t.label; });
    var semanticOnly = [];
    var overlapOnly = [];
    labels.forEach(function (a, i) {
      labels.slice(i + 1).forEach(function (b) {
        var sameOverlap = overlap.clusterOf[a] === overlap.clusterOf[b];
        var sameSemantic = semantic.clusterOf[a] === semantic.clusterOf[b];
        if (sameOverlap === sameSemantic) { return; }
        var pair = { a: a, b: b, shared: sharedCount(data, a, b) };
        (sameSemantic ? semanticOnly : overlapOnly).push(pair);
      });
    });
    semanticOnly.sort(function (x, y) { return x.shared - y.shared; });
    overlapOnly.sort(function (x, y) { return y.shared - x.shared; });
    return {
      inflation: inflation,
      overlap: overlap,
      semantic: semantic,
      semanticOnly: semanticOnly.slice(0, MAX_PAIRS),
      overlapOnly: overlapOnly.slice(0, MAX_PAIRS),
      dropped: Math.max(0, semanticOnly.length - MAX_PAIRS) +
        Math.max(0, overlapOnly.length - MAX_PAIRS),
    };
  }

  /* ---------- walking one family ----------

     Dijkstra with weight `1 - strength`, so the strong route wins over
     the short one, and every hop arrives with the citekeys or the
     bridging pair that justify it: a hop the reader cannot check is not
     worth drawing.

     One family per call, deliberately. A single fused distance over
     both would be a number nobody can interpret, and the design refuses
     it. `labels: null` means no path in *this* family -- which is an
     answer, and often the interesting one. */
  function path(data, family, from, to) {
    var known = new Set(data.topics.map(function (t) { return t.label; }));
    if (!known.has(from) || !known.has(to)) { return null; }
    var near = Object.create(null);
    edgesOf(data, family).forEach(function (edge, i) {
      (near[edge.a] = near[edge.a] || []).push({ to: edge.b, edge: edge, index: i });
      (near[edge.b] = near[edge.b] || []).push({ to: edge.a, edge: edge, index: i });
    });

    var best = Object.create(null);
    var cameFrom = Object.create(null);
    var settled = new Set();
    best[from] = 0;
    while (true) {
      var here = null;
      Object.keys(best).forEach(function (label) {
        if (settled.has(label)) { return; }
        if (here === null || best[label] < best[here]) { here = label; }
      });
      if (here === null || here === to) { break; }
      settled.add(here);
      (near[here] || []).forEach(function (step) {
        var cost = best[here] + (1 - weightOf(family, step.edge));
        if (best[step.to] === undefined || cost < best[step.to]) {
          best[step.to] = cost;
          cameFrom[step.to] = { from: here, step: step };
        }
      });
    }
    if (best[to] === undefined) { return { labels: null, hops: [], family: family }; }

    var labels = [to];
    var hops = [];
    var cursor = to;
    while (cursor !== from) {
      var back = cameFrom[cursor];
      hops.unshift({
        a: back.from,
        b: cursor,
        family: family,
        strength: weightOf(family, back.step.edge),
        index: back.step.index,
        evidence: evidenceOf(family, back.step.edge),
      });
      cursor = back.from;
      labels.unshift(cursor);
    }
    return { labels: labels, hops: hops, family: family };
  }

  return { cluster: cluster, disagreement: disagreement, path: path };
});
