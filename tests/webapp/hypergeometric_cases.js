/* The contract between two runtimes computing one number.

   `assets/webapp/absence.js` recomputes, in the browser, the same
   hypergeometric tail `chitragupta/enrich/topic_graph.py` used to
   decide whether an overlap edge was worth drawing. If the two ever
   disagree the app is telling the reader something the pipeline did not
   do, which is worse than telling them nothing.

   Every row below is `scipy.stats.hypergeom.sf(k - 1, docs, a, b)` --
   the exact call the stage makes -- recorded to full double precision.
   `tests/webapp/absence.test.js` asserts the JavaScript reproduces
   them; `tests/test_webapp_hypergeometric.py` asserts scipy still does.
   Neither suite needs the other's runtime, and neither side can drift
   without one of them going red.

   The rows are chosen for the readings the feature exists to tell
   apart: the documented worked example (one shared paper between topics
   of size 2 and 3 in a 4-paper corpus, p = 1.0, edge withheld), a
   corpus-sized pair that clearly is not chance, and the boundaries in
   between. */
"use strict";

const HYPERGEOMETRIC_CASES = [
  { k: 1, docs: 4, a: 2, b: 3, p: 1 },
  { k: 1, docs: 100, a: 10, b: 10, p: 0.6695237889132748 },
  { k: 2, docs: 100, a: 10, b: 10, p: 0.2615284665839846 },
  { k: 5, docs: 100, a: 10, b: 10, p: 0.00067162774826505023 },
  { k: 8, docs: 497, a: 25, b: 40, p: 0.00034129734962228984 },
  { k: 1, docs: 497, a: 2, b: 3, p: 0.012048095021743364 },
  { k: 3, docs: 50, a: 12, b: 9, p: 0.36825690498215946 },
  { k: 10, docs: 500, a: 60, b: 80, p: 0.50185230870101627 },
  { k: 1, docs: 10, a: 1, b: 1, p: 0.10000000000000001 },
  { k: 2, docs: 6, a: 3, b: 4, p: 0.79999999999999993 },
  { k: 25, docs: 500, a: 25, b: 25, p: 9.5793434076996702e-43 },
];

module.exports = { HYPERGEOMETRIC_CASES };
