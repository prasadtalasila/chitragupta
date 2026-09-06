/* assets/webapp/families.js: the two edge families as two graphs
   (#677, #679).

   The design's central bet is that overlap and semantic nearness answer
   different questions and that **their disagreement is itself a
   discovery cue**. Until now that cue existed only as a sentence in the
   documentation. Clustering each family separately and showing where
   the two partitions disagree is what turns it into a view; walking
   each family separately is what turns it into an answer about two
   named topics.

   Both are view-derived: computed in this browser at this moment, at a
   parameter the reader can move, and reported by no other view. What
   they must never do is fuse -- one partition over a merged graph, or
   one path over a combined weight, destroys exactly the signal they
   exist to surface. */
"use strict";

const test = require("node:test");
const assert = require("node:assert");

const families = require("../../assets/webapp/families.js");

/* Two clean clusters over shared papers: {A, B, C} and {X, Y, Z}, with
   one thin link between B and X. Over vocabulary the split runs the
   other way -- {A, B, X} talk alike, {C, Y, Z} talk alike -- which is
   the disagreement the grid exists to show. */
const TOPICS = ["A", "B", "C", "X", "Y", "Z"].map((label) => ({
  label: label, origin: "seed", terms: [], members: [],
}));

function overlap(a, b, w) {
  return { a: a, b: b, jaccard: w / 2, overlap_coeff: w, p_value: 0.001, shared: ["p" + a + b] };
}
function semantic(a, b, w) {
  return { a: a, b: b, similarity: w, bridge: ["p" + a, "p" + b] };
}

const TWO_WAYS = {
  n_docs: 20,
  topics: TOPICS,
  edges_overlap: [
    overlap("A", "B", 0.9), overlap("B", "C", 0.9), overlap("A", "C", 0.8),
    overlap("X", "Y", 0.9), overlap("Y", "Z", 0.9), overlap("X", "Z", 0.8),
    overlap("B", "X", 0.05),
  ],
  edges_semantic: [
    semantic("A", "B", 0.9), semantic("B", "X", 0.9), semantic("A", "X", 0.8),
    semantic("C", "Y", 0.9), semantic("Y", "Z", 0.9), semantic("C", "Z", 0.8),
  ],
};

function clusterOf(partition, label) {
  return partition.clusterOf[label];
}

// ---------- clustering, once per family ----------

test("clustering finds the paper-sharing groups", () => {
  const partition = families.cluster(TWO_WAYS, "overlap", 2);
  assert.equal(clusterOf(partition, "A"), clusterOf(partition, "B"));
  assert.equal(clusterOf(partition, "A"), clusterOf(partition, "C"));
  assert.equal(clusterOf(partition, "X"), clusterOf(partition, "Y"));
  assert.notEqual(clusterOf(partition, "A"), clusterOf(partition, "X"));
});

test("clustering the other family finds the other grouping", () => {
  const partition = families.cluster(TWO_WAYS, "semantic", 2);
  assert.equal(clusterOf(partition, "A"), clusterOf(partition, "X"));
  assert.equal(clusterOf(partition, "C"), clusterOf(partition, "Y"));
  assert.notEqual(clusterOf(partition, "A"), clusterOf(partition, "C"));
});

test("every topic lands in exactly one cluster, isolated ones included", () => {
  const lonely = {
    n_docs: 20,
    topics: TOPICS.concat([{ label: "alone", origin: "seed", terms: [], members: [] }]),
    edges_overlap: TWO_WAYS.edges_overlap,
    edges_semantic: TWO_WAYS.edges_semantic,
  };
  const partition = families.cluster(lonely, "overlap", 2);
  const seen = partition.clusters.flatMap((c) => c.members);
  assert.equal(seen.length, lonely.topics.length);
  assert.deepEqual(seen.slice().sort(), lonely.topics.map((t) => t.label).sort());
  assert.equal(partition.clusters.find((c) => c.members.includes("alone")).members.length, 1);
});

test("the same inflation always yields the same clusters", () => {
  assert.deepEqual(
    families.cluster(TWO_WAYS, "overlap", 2),
    families.cluster(TWO_WAYS, "overlap", 2)
  );
});

test("a higher inflation cuts finer, never coarser", () => {
  const coarse = families.cluster(TWO_WAYS, "overlap", 1.2).clusters.length;
  const fine = families.cluster(TWO_WAYS, "overlap", 4).clusters.length;
  assert.ok(fine >= coarse, coarse + " -> " + fine);
});

test("the cluster table has a null prototype", () => {
  assert.equal(Object.getPrototypeOf(families.cluster(TWO_WAYS, "overlap", 2).clusterOf), null);
});

test("a family with no edges at all gives every topic its own cluster", () => {
  const bare = { n_docs: 4, topics: TOPICS, edges_overlap: [], edges_semantic: [] };
  assert.equal(families.cluster(bare, "overlap", 2).clusters.length, TOPICS.length);
});

// ---------- where the two disagree ----------

test("the grid finds topics that talk alike and share no papers", () => {
  // A and X are in one semantic cluster; over shared papers they are in
  // different ones and their only link is a thin edge. That is a
  // literature that has not met itself, and it is the observation a
  // survey wants to open with.
  const grid = families.disagreement(TWO_WAYS, 2);
  const pair = grid.semanticOnly.find(
    (p) => (p.a === "A" && p.b === "X") || (p.a === "X" && p.b === "A")
  );
  assert.ok(pair, JSON.stringify(grid.semanticOnly));
  assert.equal(pair.shared, 0, "these two share no papers");
});

test("the grid finds topics that share papers and are split by vocabulary", () => {
  const grid = families.disagreement(TWO_WAYS, 2);
  const pair = grid.overlapOnly.find(
    (p) => (p.a === "B" && p.b === "C") || (p.a === "C" && p.b === "B")
  );
  assert.ok(pair, JSON.stringify(grid.overlapOnly));
});

test("a pair the two families agree on is in neither list", () => {
  const grid = families.disagreement(TWO_WAYS, 2);
  const agreed = grid.overlapOnly.concat(grid.semanticOnly).filter(
    (p) => (p.a === "A" && p.b === "B") || (p.a === "B" && p.b === "A")
  );
  assert.deepEqual(agreed, []);
});

test("the grid reports the two partitions it was computed from", () => {
  const grid = families.disagreement(TWO_WAYS, 2.5);
  assert.equal(grid.inflation, 2.5);
  assert.equal(grid.overlap.clusters.length >= 1, true);
  assert.equal(grid.semantic.clusters.length >= 1, true);
});

test("each pair is listed once, not once per direction", () => {
  const grid = families.disagreement(TWO_WAYS, 2);
  const keys = grid.semanticOnly.map((p) => [p.a, p.b].sort().join(" "));
  assert.equal(new Set(keys).size, keys.length);
});

// ---------- walking one family at a time ----------

test("a path over shared papers is found, and every hop is a real edge with evidence", () => {
  const path = families.path(TWO_WAYS, "overlap", "A", "Z");
  assert.equal(path.labels[0], "A");
  assert.equal(path.labels[path.labels.length - 1], "Z");
  assert.equal(path.hops.length, path.labels.length - 1);
  path.hops.forEach((hop, i) => {
    assert.equal(hop.family, "overlap");
    assert.deepEqual([hop.a, hop.b], [path.labels[i], path.labels[i + 1]]);
    assert.ok(hop.evidence.length, "a hop with no evidence is not worth drawing");
    // The hop points at a real edge in the payload, in either order.
    const edge = TWO_WAYS.edges_overlap[hop.index];
    assert.ok(
      (edge.a === hop.a && edge.b === hop.b) || (edge.a === hop.b && edge.b === hop.a),
      JSON.stringify(hop)
    );
  });
});

test("a hop over shared papers names the papers, and a semantic hop the bridge", () => {
  assert.deepEqual(families.path(TWO_WAYS, "overlap", "A", "B").hops[0].evidence, ["pAB"]);
  assert.deepEqual(families.path(TWO_WAYS, "semantic", "A", "B").hops[0].evidence, ["pA", "pB"]);
});

test("the two families are walked separately and can disagree about the route", () => {
  const overlapPath = families.path(TWO_WAYS, "overlap", "A", "Y");
  const semanticPath = families.path(TWO_WAYS, "semantic", "A", "Y");
  assert.notDeepEqual(overlapPath.labels, semanticPath.labels);
});

test("no path in a family is an answer, not an error", () => {
  const split = {
    n_docs: 20, topics: TOPICS,
    edges_overlap: [overlap("A", "B", 0.9)],
    edges_semantic: [semantic("Y", "Z", 0.9)],
  };
  const path = families.path(split, "overlap", "A", "Z");
  assert.equal(path.labels, null);
  assert.deepEqual(path.hops, []);
});

test("a path to itself is a path of no hops", () => {
  const path = families.path(TWO_WAYS, "overlap", "A", "A");
  assert.deepEqual(path.labels, ["A"]);
  assert.deepEqual(path.hops, []);
});

test("the strong route is preferred to the short one when it is stronger", () => {
  /* A--B--C at full strength against a single A--C thread: weighting by
     `1 - strength` is what makes the two-hop route the better answer,
     and hop count alone would get it wrong. */
  const detour = {
    n_docs: 20, topics: TOPICS,
    edges_overlap: [overlap("A", "B", 1), overlap("B", "C", 1), overlap("A", "C", 0.02)],
    edges_semantic: [],
  };
  assert.deepEqual(families.path(detour, "overlap", "A", "C").labels, ["A", "B", "C"]);
});

test("an unknown label is refused rather than answered with an empty path", () => {
  assert.equal(families.path(TWO_WAYS, "overlap", "A", "no such topic"), null);
});

// ---------- the panels ----------

const panel = require("../../assets/webapp/panel.js");

test("the grid names both disagreements and says which is which", () => {
  const html = panel.disagreementHtml(families.disagreement(TWO_WAYS, 2));
  assert.match(html, /talk alike/i);
  assert.match(html, /share papers/i);
  assert.match(html, /inflation/i);
  assert.match(html, /2/);
  assert.match(html, /in your browser/i);
});

test("the sharpest disagreement is called out in words", () => {
  const html = panel.disagreementHtml(families.disagreement(TWO_WAYS, 2));
  // A semantic pair sharing nothing is the headline reading.
  assert.match(html, /no shared papers/i);
});

test("a grid with nothing to report says so rather than showing empty lists", () => {
  const agreeing = {
    n_docs: 20, topics: TOPICS,
    edges_overlap: [overlap("A", "B", 0.9)],
    edges_semantic: [semantic("A", "B", 0.9)],
  };
  const html = panel.disagreementHtml(families.disagreement(agreeing, 2));
  assert.match(html, /agree/i);
});

test("a truncated grid says how much it dropped", () => {
  const html = panel.disagreementHtml({
    inflation: 2, overlap: { clusters: [] }, semantic: { clusters: [] },
    semanticOnly: [{ a: "A", b: "X", shared: 0 }], overlapOnly: [], dropped: 47,
  });
  assert.match(html, /47 more/);
});

test("the grid escapes hostile labels", () => {
  const html = panel.disagreementHtml({
    inflation: 2, overlap: { clusters: [] }, semantic: { clusters: [] },
    semanticOnly: [{ a: '<"x">', b: "y", shared: 0 }], overlapOnly: [], dropped: 0,
  });
  assert.ok(!html.includes('<"x">'));
});

test("a path panel names every hop and the evidence under it", () => {
  const html = panel.pathHtml(TWO_WAYS, families.path(TWO_WAYS, "overlap", "A", "C"));
  assert.match(html, /shared papers/i);
  assert.match(html, /<code>pAB<\/code>|<code>pAC<\/code>/);
  assert.ok(!html.includes("NaN"));
});

test("a semantic path panel names the bridging pair on each hop", () => {
  const html = panel.pathHtml(TWO_WAYS, families.path(TWO_WAYS, "semantic", "A", "X"));
  assert.match(html, /semantic nearness/i);
  assert.match(html, /<code>pA<\/code>/);
});

test("no path is reported as an answer, per family", () => {
  const split = {
    n_docs: 20, topics: TOPICS,
    edges_overlap: [overlap("A", "B", 0.9)],
    edges_semantic: [semantic("Y", "Z", 0.9)],
  };
  const html = panel.pathHtml(split, families.path(split, "overlap", "A", "Z"));
  assert.match(html, /no path/i);
  assert.match(html, /shared papers/i);
});

test("the path panel never reports one distance over both families", () => {
  const html = panel.pathHtml(TWO_WAYS, families.path(TWO_WAYS, "overlap", "A", "Z"));
  assert.ok(!html.match(/total (distance|strength|score)/i));
});
