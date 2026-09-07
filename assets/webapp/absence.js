/* Why there is *no* edge here, and how surprising the ones there are.

   The most instructive moment in this pipeline's documented worked
   session is the hypergeometric gate computing p = 1.0 and withholding
   an edge between two topics that *do* share a paper. Every view hides
   that reasoning: the reader sees no edge and cannot tell "these have
   nothing in common" from "these share a paper, and the gate judged it
   unsurprising".

   `docs/TOPIC-DISCOVERY-GRAPH.md` §7.7 answers it with a stored
   `edges_withheld` list. #670 first kept that field out of scope; the
   §2 amendment (#707) reopened it, and #710 stores it -- so `explain`
   now prefers the stage's own stored p for a withheld pair, and only
   recomputes the tail for a payload from an older run, which the
   payload can always feed: each topic's `members`, and `n_docs`.

   The arithmetic has to agree with `chitragupta/enrich/topic_graph.py`,
   which calls `scipy.stats.hypergeom.sf(k - 1, n_docs, |A|, |B|)`. A
   browser-side p-value that disagreed with the stage that drew the
   edges would be worse than showing none, so
   `tests/webapp/hypergeometric_cases.js` holds scipy's own answers and
   both suites check against it -- node that this code matches, pytest
   that scipy still does.

   Tested without a DOM by tests/webapp/absence.test.js. */
"use strict";

(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.CHITRAGUPTA_APP = Object.assign(root.CHITRAGUPTA_APP || {}, api);
  }
})(typeof self !== "undefined" ? self : this, function () {
  /* Lanczos log-gamma. The factorials here run to the size of the
     corpus, and 171! overflows a double, so the tail is summed in log
     space and exponentiated per term. Measured against scipy on the
     recorded cases: worst relative error 5e-13, including a term of
     1e-43. */
  var LANCZOS = [
    0.99999999999980993, 676.5203681218851, -1259.1392167224028,
    771.32342877765313, -176.61502916214059, 12.507343278686905,
    -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7,
  ];

  function logGamma(z) {
    if (z < 0.5) {
      return Math.log(Math.PI / Math.sin(Math.PI * z)) - logGamma(1 - z);
    }
    z -= 1;
    var x = LANCZOS[0];
    for (var i = 1; i < LANCZOS.length; i++) { x += LANCZOS[i] / (z + i); }
    var t = z + LANCZOS.length - 1.5;
    return 0.5 * Math.log(2 * Math.PI) + (z + 0.5) * Math.log(t) - t + Math.log(x);
  }

  function logChoose(n, k) {
    if (k < 0 || k > n) { return -Infinity; }
    return logGamma(n + 1) - logGamma(k + 1) - logGamma(n - k + 1);
  }

  /* P(X >= k) for X hypergeometric over `docs` papers, a topic of size
     `a` and one of size `b`: the chance that two topics this size share
     at least this many papers by drawing at random. Small means the
     overlap is affinity; large means it is arithmetic. */
  function survival(k, docs, a, b) {
    var least = Math.max(0, a + b - docs);
    var most = Math.min(a, b);
    if (k <= least) { return 1; }
    if (k > most) { return 0; }
    var denominator = logChoose(docs, b);
    var total = 0;
    for (var i = k; i <= most; i++) {
      total += Math.exp(logChoose(a, i) + logChoose(docs - a, b - i) - denominator);
    }
    return Math.min(1, total);
  }

  /* Everything the reader needs to be told about a pair, computed from
     the payload: what they share, how surprising that is, and whether
     the graph carries an edge between them. `null` for a label the
     payload does not know -- answering a typo with a probability would
     be worse than refusing.

     `p` is null when nothing is shared: an empty intersection has no
     tail to compute, and a number there would be arithmetic about
     nothing. */
  function explain(data, a, b) {
    var topics = Object.create(null);
    data.topics.forEach(function (t) { topics[t.label] = t; });
    if (!topics[a] || !topics[b]) { return null; }
    var mine = new Set(topics[a].members.map(function (m) { return m.citekey; }));
    var shared = topics[b].members
      .map(function (m) { return m.citekey; })
      .filter(function (citekey) { return mine.has(citekey); })
      .sort();
    var sizes = { a: topics[a].members.length, b: topics[b].members.length };
    /* The stage's own number when the payload carries it (#710 stored
       §7.7's `edges_withheld`): reading it beats recomputing it, since
       the stored p is by definition the one the gate weighed. The
       recomputation stays as the fallback for a payload from an older
       run, still pinned to scipy by hypergeometric_cases.js. */
    var stored = (data.edges_withheld || []).filter(function (e) {
      return (e.a === a && e.b === b) || (e.a === b && e.b === a);
    })[0];
    return {
      shared: shared,
      p: stored ? stored.p_value
        : shared.length ? survival(shared.length, data.n_docs, sizes.a, sizes.b) : null,
      sizes: sizes,
      docs: data.n_docs,
      drawn: data.edges_overlap.some(function (e) {
        return (e.a === a && e.b === b) || (e.a === b && e.b === a);
      }),
    };
  }

  /* The gate, made visible on the edges that survived it. Width already
     means strength, so opacity is the free channel: a more surprising
     overlap draws more solidly.

     The stage's own threshold is not carried in the payload, but the
     documented default is p < 0.01, so -log10(p) starts at 2 by
     construction; six decades past that covers what a real corpus
     produces, and anything beyond saturates. Past a point "could not be
     chance" is one reading, not a scale. */
  function surpriseOpacity(p) {
    var decades = p > 0 ? -Math.log(p) / Math.LN10 : Infinity;
    var t = Math.max(0, Math.min(1, (decades - 2) / 6));
    return 0.35 + 0.65 * t;
  }

  /* Whether an edge is the *containment* reading rather than two topics
     that merely coincide. Both coefficients travel on every overlap
     edge for a documented reason: a rank-truncated seed topic sitting
     entirely inside a large emergent cluster scores 1.0 on overlap
     coefficient and low on Jaccard, and that gap is the sub-topic
     reading. Both conditions, because a high coefficient with a high
     Jaccard is two topics that mostly are each other -- a different
     thing, and not worth a badge. No third invented number. */
  function containment(edge) {
    return edge.overlap_coeff >= 0.8 && edge.jaccard <= 0.5;
  }

  return {
    survival: survival,
    explain: explain,
    surpriseOpacity: surpriseOpacity,
    containment: containment,
  };
});
