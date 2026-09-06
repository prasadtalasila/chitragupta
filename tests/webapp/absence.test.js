/* assets/webapp/absence.js: explaining an edge that is *not* there
   (#675), and surfacing what the drawn edges already carry (#678).

   The most instructive moment in this pipeline's own worked session is
   the hypergeometric gate computing p = 1.0 and withholding an edge
   between two topics that *do* share a paper. Every view hides that
   reasoning today: the reader sees no edge and cannot tell "these have
   nothing in common" from "these share a paper and the gate judged it
   unsurprising".

   `docs/TOPIC-DISCOVERY-GRAPH.md` §7.7 solves it by storing an
   `edges_withheld` list. Under #670's decision that field is out of
   scope -- and unnecessary, because the payload already carries every
   input the test needs: each topic's `members`, and `n_docs`.

   The arithmetic must agree with `chitragupta/enrich/topic_graph.py`,
   which calls `scipy.stats.hypergeom.sf(k - 1, n_docs, |A|, |B|)`. A
   browser-side number that disagreed with the stage that drew the
   edges would be worse than no number at all, so the expectations
   below are scipy's own output, and `tests/test_webapp_hypergeometric.py`
   re-derives this same table from scipy so neither side can drift. */
"use strict";

const test = require("node:test");
const assert = require("node:assert");

const absence = require("../../assets/webapp/absence.js");
const { HYPERGEOMETRIC_CASES } = require("./hypergeometric_cases.js");

test("the survival function matches scipy on every recorded case", () => {
  HYPERGEOMETRIC_CASES.forEach((c) => {
    const got = absence.survival(c.k, c.docs, c.a, c.b);
    const relative = c.p === 0 ? Math.abs(got) : Math.abs(got - c.p) / c.p;
    assert.ok(
      relative < 1e-9,
      `sf(${c.k - 1}, ${c.docs}, ${c.a}, ${c.b}) = ${got}, scipy says ${c.p}`
    );
  });
});

test("the tail is bounded to a probability at both ends", () => {
  // Every draw must contain at least this many, and no draw can.
  assert.equal(absence.survival(0, 10, 4, 5), 1);
  assert.equal(absence.survival(5, 10, 4, 5), 0);
});

test("sharing everything is certain when the corpus is that small", () => {
  assert.equal(absence.survival(1, 2, 2, 2), 1);
});

// ---------- explaining a pair the graph did not join ----------

const { DATA } = require("./fixture.js");

/* The fixture's corpus: 4 papers, "digital twin" holds 2 of them,
   "machine learning" 3, and they share dt2022 -- the documented worked
   example, where the gate computes p = 1.0 and withholds the edge. The
   fixture *does* carry an overlap edge between them (it is a payload
   fixture, not a gate fixture), so the pairs below are chosen to be the
   ones it leaves unjoined. */

test("two topics that share nothing are told so, without a probability", () => {
  const verdict = absence.explain(DATA, "digital twin", "topic-7");
  assert.deepEqual(verdict.shared, []);
  assert.equal(verdict.p, null, "an empty set has no tail to compute");
});

test("a shared paper the gate found unremarkable is explained by its arithmetic", () => {
  const verdict = absence.explain(DATA, "machine learning", "topic-7");
  assert.deepEqual(verdict.shared, []);
  // ... and the same call on a pair that does share reports the tail.
  const sharing = absence.explain(DATA, "digital twin", "machine learning");
  assert.deepEqual(sharing.shared, ["dt2022"]);
  assert.equal(sharing.p, absence.survival(1, DATA.n_docs, 2, 3));
  assert.equal(sharing.p, 1, "one shared paper here is exactly what chance predicts");
  assert.deepEqual(sharing.sizes, { a: 2, b: 3 });
  assert.equal(sharing.docs, 4);
});

test("the verdict knows whether the graph actually carries an edge", () => {
  assert.equal(absence.explain(DATA, "digital twin", "machine learning").drawn, true);
  assert.equal(absence.explain(DATA, "digital twin", "topic-7").drawn, false);
});

test("the pair is read in either order", () => {
  assert.deepEqual(
    absence.explain(DATA, "machine learning", "digital twin").shared,
    absence.explain(DATA, "digital twin", "machine learning").shared
  );
});

test("an unknown label is refused rather than answered with zero", () => {
  assert.equal(absence.explain(DATA, "digital twin", "no such topic"), null);
});

// ---------- how surprising a drawn edge is ----------

test("a more surprising overlap is drawn more solidly", () => {
  assert.ok(absence.surpriseOpacity(1e-8) > absence.surpriseOpacity(0.005));
});

test("opacity stays inside a legible band whatever the p-value", () => {
  [1, 0.01, 1e-4, 1e-30, 0].forEach((p) => {
    const o = absence.surpriseOpacity(p);
    assert.ok(o >= 0.35 && o <= 1, "p = " + p + " gave " + o);
  });
});

test("an impossible-by-chance overlap saturates rather than running away", () => {
  assert.equal(absence.surpriseOpacity(1e-30), absence.surpriseOpacity(1e-60));
});

// ---------- naming the containment reading ----------

test("a topic sitting inside a larger one is named, not left as two numbers", () => {
  // The documented case: a rank-truncated seed topic entirely inside a
  // large emergent cluster scores 1.0 on overlap coefficient and low on
  // Jaccard, and that gap *is* the sub-topic reading.
  assert.equal(absence.containment({ overlap_coeff: 1, jaccard: 0.15 }), true);
  assert.equal(absence.containment({ overlap_coeff: 0.85, jaccard: 0.4 }), true);
});

test("two topics that mostly coincide are not a containment", () => {
  assert.equal(absence.containment({ overlap_coeff: 0.95, jaccard: 0.9 }), false);
});

test("a weak overlap is not a containment either", () => {
  assert.equal(absence.containment({ overlap_coeff: 0.3, jaccard: 0.2 }), false);
});

// ---------- the sentences ----------

const panel = require("../../assets/webapp/panel.js");

test("a pair sharing nothing gets a plain sentence, not a probability", () => {
  const html = panel.absenceHtml("digital twin", "topic-7",
    absence.explain(DATA, "digital twin", "topic-7"));
  assert.match(html, /share no papers/i);
  assert.ok(!html.includes("p ="), "a probability about an empty set");
});

test("the refused edge is explained in the gate's own terms", () => {
  /* The sentence the whole feature exists for, from the pipeline's own
     worked example: two topics of size 2 and 3 in a 4-paper corpus
     sharing one paper is what chance predicts. */
  const verdict = absence.explain(DATA, "digital twin", "machine learning");
  const html = panel.absenceHtml("digital twin", "machine learning",
    Object.assign({}, verdict, { drawn: false }));
  assert.match(html, /dt2022/);
  assert.match(html, /size 2 and 3/);
  assert.match(html, /4-paper corpus/);
  assert.match(html, /p = 1\.00/);
  assert.match(html, /what chance predicts/i);
  assert.match(html, /no edge was drawn/i);
});

test("a surprising overlap with no edge does not blame the gate", () => {
  /* The stage's threshold is not in the payload. A corpus built with a
     stricter cut-off lands here, and the honest answer names the limit
     of what this page can see rather than inventing a threshold. */
  const html = panel.absenceHtml("a", "b", {
    shared: ["x2020", "y2021"], p: 0.0004, sizes: { a: 9, b: 11 }, docs: 400, drawn: false,
  });
  assert.match(html, /stricter/i);
  assert.ok(!html.includes("what chance predicts"));
  assert.match(html, /4\.0e-4/);
});

test("the absence panel escapes both labels and prints citekeys verbatim", () => {
  const html = panel.absenceHtml('<"a">', "b", {
    shared: ["x2020"], p: 0.5, sizes: { a: 2, b: 2 }, docs: 9, drawn: false,
  });
  assert.ok(!html.includes('<"a">'));
  assert.match(html, /<code>x2020<\/code>/);
});

test("an edge panel names the containment reading when the coefficients diverge", () => {
  const contained = {
    topics: DATA.topics,
    edges_overlap: [{
      a: "digital twin", b: "machine learning",
      jaccard: 0.15, overlap_coeff: 1, p_value: 0.0004, shared: ["dt2022"],
    }],
    edges_semantic: [],
  };
  const html = panel.edgeHtml(contained, "overlap", 0);
  assert.match(html, /contained/i);
  assert.match(html, /overlap 1\.00/);
  assert.match(html, /Jaccard 0\.15/);
  assert.match(html, /inside/i);
});

test("an ordinary overlap edge gets no containment badge", () => {
  assert.ok(!panel.edgeHtml(DATA, "overlap", 0).match(/contained/i));
});

// ---------- the encoding on the canvas ----------

const graph = require("../../assets/webapp/graph.js");

test("an overlap edge carries its surprise as an opacity", () => {
  const els = graph.elementsFor(DATA, new Set(DATA.topics.map((t) => t.label)), []);
  const edge = els.find((e) => e.data.family === "overlap");
  assert.equal(edge.data.surprise, absence.surpriseOpacity(DATA.edges_overlap[0].p_value));
});

test("a semantic edge is given no surprise it does not have", () => {
  const els = graph.elementsFor(DATA, new Set(DATA.topics.map((t) => t.label)), []);
  const edge = els.find((e) => e.data.family === "semantic");
  assert.equal(edge.data.surprise, undefined);
});

test("a bundle is as solid as its most surprising constituent", () => {
  // The same rule as width taking the strongest: a bundle drawn at the
  // average hides the very link the reader is looking for.
  const two = {
    topics: DATA.topics,
    edges_overlap: [
      { a: "digital twin", b: "topic-7", jaccard: 0.2, overlap_coeff: 0.4, p_value: 0.005, shared: ["dt2022"] },
      { a: "machine learning", b: "topic-7", jaccard: 0.1, overlap_coeff: 0.2, p_value: 1e-9, shared: ["ml2020"] },
    ],
    edges_semantic: [],
  };
  const labels = DATA.topics.map((t) => t.label);
  const cut = graph.cutTree(
    [{ id: "node-0", a: "digital twin", b: "machine learning", distance: 0.1 }],
    DATA.topics, 0.5
  );
  const gid = cut.groupOf["digital twin"];
  const bundle = graph
    .elementsFor(two, new Set(labels), [], { cut: cut, collapsed: new Set([gid]) })
    .find((e) => e.data.bundled);
  assert.equal(bundle.data.count, 2);
  assert.equal(bundle.data.surprise, absence.surpriseOpacity(1e-9));
});
