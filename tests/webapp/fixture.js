/* One small payload in the shape `corpus discover --app` writes into
   data.js, shared by every test in this directory.

   Hand-written rather than generated from the real corpus on purpose:
   these tests are about what the browser code does with a payload, and
   a fixture small enough to reason about is what lets an expectation be
   written by hand instead of copied from the code under test. The
   shapes are pinned by `chitragupta/discover/_page.py` (the join) and
   `_app.py` (the `origin` annotation) -- if either changes, this file
   is where the browser tests find out. */
"use strict";

// Deliberately hostile labels: `__proto__` reaches Object.prototype on
// a plain object (#636), and the quote/angle-bracket pair is what the
// five-character escape exists for. Both ride in through a PDF's
// extracted keywords in real life, so both belong in the fixture.
const DATA = {
  n_docs: 4,
  topics: [
    {
      label: "digital twin",
      provenance: "seed",
      origin: "seed",
      terms: ["twin", "simulation"],
      members: [
        { citekey: "dt2022", title: "A digital twin", score: 0.9 },
        { citekey: "sim2021", title: "Simulation", score: 0.4 },
      ],
      linked: [],
    },
    {
      label: "machine learning",
      provenance: "seed",
      origin: "keyword",
      terms: ["learning", "neural"],
      members: [
        { citekey: "dt2022", title: "A digital twin", score: 0.5 },
        { citekey: "ml2020", title: "Learning things", score: 0.8 },
        { citekey: "nn2019", title: "", score: 0.2 },
      ],
      linked: [],
    },
    {
      label: "topic-7",
      provenance: "emergent",
      origin: "emergent",
      terms: ["verification"],
      members: [{ citekey: "rv2018", title: "Runtime verification", score: 0.7 }],
      linked: [],
    },
    {
      label: '__proto__ <"hostile">',
      provenance: "seed",
      origin: "both",
      terms: ["hostile"],
      members: [{ citekey: "x2017", title: "Odd <one>", score: 0.1 }],
      linked: [],
    },
  ],
  edges_overlap: [
    {
      a: "digital twin",
      b: "machine learning",
      jaccard: 0.25,
      overlap_coeff: 0.5,
      p_value: 0.004,
      shared: ["dt2022"],
    },
  ],
  edges_semantic: [
    {
      a: "machine learning",
      b: "topic-7",
      similarity: 0.61,
      bridge: ["ml2020", "rv2018"],
    },
  ],
  hierarchy: [{ id: "node-0", a: "digital twin", b: "machine learning", distance: 0.31 }],
};

module.exports = { DATA };
