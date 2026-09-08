/* assets/webapp/graph.js: the egocentric view (#673, #674).

   Selecting a topic used to delete everything else from the canvas.
   Now the context stays, dimmed, and the selection is laid out as
   concentric rings by hop distance -- with the two edge families kept
   apart, because a neighbour reached only through a shared paper is a
   different object from one reached only through cosine nearness.

   The brokerage numbers are the first genuinely *derived* things this
   app shows: everything before them was read from the payload or cut
   from a stored tree. "Labelled view-derived" is no protection against
   a wrong formula, so they are tested against a graph small enough to
   work out by hand, and the arithmetic is written down beside them. */
"use strict";

const test = require("node:test");
const assert = require("node:assert");

const graph = require("../../assets/webapp/graph.js");
const ego = require("../../assets/webapp/ego.js");

/* The worked example, four topics:

       A --- B          E is the ego. Its alters are A, B and C.
        \   /           A and B are joined to each other; C is joined
         \ /            to nobody but E. D is two hops away, through A.
    D --- E --- C

   All overlap edges, all of weight 1, so every figure below can be
   checked with a pencil. */
const EGO = {
  n_docs: 9,
  topics: ["E", "A", "B", "C", "D"].map((label) => ({
    label: label,
    origin: "seed",
    terms: [],
    members: [{ citekey: label.toLowerCase() + "2020", title: label, score: 0.5 }],
  })),
  edges_overlap: [
    ["E", "A"], ["E", "B"], ["E", "C"], ["A", "B"], ["A", "D"],
  ].map(([a, b]) => ({
    a: a, b: b, jaccard: 0.5, overlap_coeff: 1, p_value: 0.01, shared: ["x2020"],
  })),
  edges_semantic: [],
};

const BOTH = ["overlap", "semantic"];

// ---------- hop distance ----------

test("hop distance is zero at the roots and grows outward", () => {
  const hops = ego.hopsFrom(EGO, ["E"], BOTH);
  assert.equal(hops["E"], 0);
  assert.equal(hops["A"], 1);
  assert.equal(hops["C"], 1);
  assert.equal(hops["D"], 2);
});

test("an unreachable topic has no hop distance rather than a large one", () => {
  const island = { topics: EGO.topics.concat([{ label: "Z", origin: "seed", terms: [], members: [] }]),
    edges_overlap: EGO.edges_overlap, edges_semantic: [] };
  assert.equal(ego.hopsFrom(island, ["E"], BOTH)["Z"], undefined);
});

test("two roots each measure from themselves", () => {
  const hops = ego.hopsFrom(EGO, ["E", "D"], BOTH);
  assert.equal(hops["D"], 0);
  assert.equal(hops["A"], 1);
});

test("hop distance is measured only over the enabled families", () => {
  const mixed = {
    topics: EGO.topics,
    edges_overlap: [{ a: "E", b: "A", jaccard: 0.5, overlap_coeff: 1, p_value: 0.01, shared: ["x"] }],
    edges_semantic: [{ a: "E", b: "C", similarity: 0.7, bridge: ["x", "y"] }],
  };
  assert.equal(ego.hopsFrom(mixed, ["E"], ["overlap"])["C"], undefined);
  assert.equal(ego.hopsFrom(mixed, ["E"], ["semantic"])["A"], undefined);
  assert.equal(ego.hopsFrom(mixed, ["E"], BOTH)["C"], 1);
});

test("the hop table has a null prototype", () => {
  assert.equal(Object.getPrototypeOf(ego.hopsFrom(EGO, ["E"], BOTH)), null);
});

// ---------- how a neighbour was reached ----------

test("a neighbour is typed by which families reach it, never averaged", () => {
  const mixed = {
    topics: EGO.topics,
    edges_overlap: [
      { a: "E", b: "A", jaccard: 0.5, overlap_coeff: 1, p_value: 0.01, shared: ["x"] },
      { a: "E", b: "B", jaccard: 0.5, overlap_coeff: 1, p_value: 0.01, shared: ["x"] },
    ],
    edges_semantic: [
      { a: "E", b: "B", similarity: 0.7, bridge: ["x", "y"] },
      { a: "E", b: "C", similarity: 0.6, bridge: ["x", "y"] },
    ],
  };
  const via = ego.reachedVia(mixed, ["E"]);
  assert.equal(via["A"], "overlap");
  assert.equal(via["B"], "both");
  assert.equal(via["C"], "semantic");
  assert.equal(via["E"], undefined);
});

// ---------- ego statistics ----------

test("ego density is the alters' own edges over the pairs they could have", () => {
  // Three alters (A, B, C) could hold three edges between them; they
  // hold one, A--B. 1/3.
  const stats = ego.egoStats(EGO, "E", "overlap");
  assert.equal(stats.alters, 3);
  assert.ok(Math.abs(stats.density - 1 / 3) < 1e-12);
});

test("a topic whose neighbours all know each other reads as a theme", () => {
  const triangle = {
    topics: EGO.topics,
    edges_overlap: [["E", "A"], ["E", "B"], ["A", "B"]].map(([a, b]) => ({
      a: a, b: b, jaccard: 0.5, overlap_coeff: 1, p_value: 0.01, shared: ["x"],
    })),
    edges_semantic: [],
  };
  assert.equal(ego.egoStats(triangle, "E", "overlap").density, 1);
});

test("effective size and constraint match Burt, worked by hand", () => {
  /* p_Ej = 1/3 for each of A, B, C (equal weights, three alters).

     Effective size = sum over alters j of (1 - sum over other alters q
     of p_Eq * m_jq), where m_jq is q's share of j's strongest tie:
       j = A: p_EB * m_AB = 1/3        -> 2/3
       j = B: p_EA * m_BA = 1/3        -> 2/3
       j = C: C touches neither A nor B -> 1
     Effective size = 2/3 + 2/3 + 1 = 7/3.

     Constraint c_Ej = (p_Ej + sum_q p_Eq p_qj)^2, and here A and B are
     *not* symmetric even though the picture looks it: A spends its ties
     three ways (E, B and D), B only two (E and A). D is not in the ego
     network at all and still changes the answer, which is the whole
     point of the measure -- an alter with somewhere else to be
     constrains the ego less.
       c_A = (1/3 + 1/3 * 1/2)^2 = 1/4        (B gives A half of itself)
       c_B = (1/3 + 1/3 * 1/3)^2 = 16/81      (A gives B a third)
       c_C = (1/3)^2 = 1/9
     Constraint = 1/4 + 16/81 + 1/9 = 181/324. */
  const stats = ego.egoStats(EGO, "E", "overlap");
  assert.ok(Math.abs(stats.effectiveSize - 7 / 3) < 1e-9, "ES " + stats.effectiveSize);
  assert.ok(Math.abs(stats.constraint - 181 / 324) < 1e-9, "constraint " + stats.constraint);
});

test("an alter with ties outside the ego network constrains the ego less", () => {
  // The same shape as EGO but with D removed, so A now spends its ties
  // two ways instead of three: A's hold on the ego goes up.
  const tighter = {
    topics: EGO.topics,
    edges_overlap: [["E", "A"], ["E", "B"], ["E", "C"], ["A", "B"]].map(([a, b]) => ({
      a: a, b: b, jaccard: 0.5, overlap_coeff: 1, p_value: 0.01, shared: ["x"],
    })),
    edges_semantic: [],
  };
  assert.ok(
    ego.egoStats(tighter, "E", "overlap").constraint >
      ego.egoStats(EGO, "E", "overlap").constraint
  );
});

test("a broker's effective size is its whole neighbourhood", () => {
  // No alter touches another, so nothing is redundant: effective size
  // equals the number of alters, and that is the bridge reading.
  const star = {
    topics: EGO.topics,
    edges_overlap: [["E", "A"], ["E", "B"], ["E", "C"]].map(([a, b]) => ({
      a: a, b: b, jaccard: 0.5, overlap_coeff: 1, p_value: 0.01, shared: ["x"],
    })),
    edges_semantic: [],
  };
  const stats = ego.egoStats(star, "E", "overlap");
  assert.equal(stats.effectiveSize, 3);
  assert.equal(stats.density, 0);
});

test("a topic with one neighbour has no density to report, and is fully constrained", () => {
  const pair = {
    topics: EGO.topics,
    edges_overlap: [{ a: "E", b: "A", jaccard: 0.5, overlap_coeff: 1, p_value: 0.01, shared: ["x"] }],
    edges_semantic: [],
  };
  const stats = ego.egoStats(pair, "E", "overlap");
  assert.equal(stats.alters, 1);
  assert.equal(stats.density, null, "one alter forms no pair, so density is undefined");
  assert.equal(stats.effectiveSize, 1);
  assert.equal(stats.constraint, 1);
});

test("a topic with no neighbours in a family reports nothing rather than NaN", () => {
  // NaN satisfies no comparison and every guard reads it as a number,
  // so an isolated topic has to answer with null, not arithmetic.
  const stats = ego.egoStats(EGO, "E", "semantic");
  assert.equal(stats.alters, 0);
  assert.equal(stats.density, null);
  assert.equal(stats.constraint, null);
  assert.equal(stats.effectiveSize, 0);
});

test("the two families are measured separately, never pooled", () => {
  const mixed = {
    topics: EGO.topics,
    edges_overlap: [["E", "A"], ["E", "B"], ["A", "B"]].map(([a, b]) => ({
      a: a, b: b, jaccard: 0.5, overlap_coeff: 1, p_value: 0.01, shared: ["x"],
    })),
    edges_semantic: [
      { a: "E", b: "C", similarity: 0.7, bridge: ["x", "y"] },
      { a: "E", b: "D", similarity: 0.6, bridge: ["x", "y"] },
    ],
  };
  // A coherent theme over shared papers, and a brokerage position over
  // vocabulary: exactly the disagreement the design is built around,
  // and a pooled figure would show neither.
  assert.equal(ego.egoStats(mixed, "E", "overlap").density, 1);
  assert.equal(ego.egoStats(mixed, "E", "semantic").density, 0);
  assert.equal(ego.egoStats(mixed, "E", "semantic").effectiveSize, 2);
});

test("weights count: a strong tie constrains more than a weak one", () => {
  const weighted = (strong) => ({
    topics: EGO.topics,
    edges_overlap: [
      { a: "E", b: "A", jaccard: 0.5, overlap_coeff: strong, p_value: 0.01, shared: ["x"] },
      { a: "E", b: "B", jaccard: 0.5, overlap_coeff: 0.1, p_value: 0.01, shared: ["x"] },
    ],
    edges_semantic: [],
  });
  assert.ok(
    ego.egoStats(weighted(1), "E", "overlap").constraint >
      ego.egoStats(weighted(0.1), "E", "overlap").constraint
  );
});

// ---------- dimming the context ----------

test("with context shown, everything is drawn and the far side is dimmed", () => {
  const els = graph.elementsFor(EGO, new Set(["E", "A", "B", "C"]), ["E"], {
    context: "dim", all: new Set(["E", "A", "B", "C", "D"]),
  });
  const ids = els.filter((e) => e.group === "nodes").map((e) => e.data.id);
  assert.equal(ids.length, 5, "the context left the canvas");
  assert.equal(els.find((e) => e.data.id === "D").data.dim, 1);
  assert.equal(els.find((e) => e.data.id === "A").data.dim, 0);
});

test("an edge is dimmed when either end is", () => {
  const els = graph.elementsFor(EGO, new Set(["E", "A", "B", "C"]), ["E"], {
    context: "dim", all: new Set(["E", "A", "B", "C", "D"]),
  });
  const edges = els.filter((e) => e.group === "edges");
  const inside = edges.find((e) => e.data.source === "E" && e.data.target === "A");
  const outside = edges.find((e) => e.data.source === "A" && e.data.target === "D");
  assert.equal(inside.data.dim, 0);
  assert.equal(outside.data.dim, 1);
});

test("hiding the context is still available, and drops the far side entirely", () => {
  const els = graph.elementsFor(EGO, new Set(["E", "A", "B", "C"]), ["E"], {
    context: "hide", all: new Set(["E", "A", "B", "C", "D"]),
  });
  assert.equal(els.filter((e) => e.group === "nodes").length, 4);
});

test("with nothing pinned nothing is dimmed", () => {
  const all = new Set(["E", "A", "B", "C", "D"]);
  const els = graph.elementsFor(EGO, all, [], { context: "dim", all: all });
  els.forEach((e) => assert.ok(!e.data.dim, e.data.id + " dimmed with no selection"));
});

// ---------- concentric rings ----------

test("the pinned topic sits at the centre and its neighbours on a ring", () => {
  const hops = ego.hopsFrom(EGO, ["E"], BOTH);
  const at = ego.ringPositions(EGO, ["E"], hops, 2);
  assert.deepEqual(at["E"], { x: 0, y: 0 });
  const radii = ["A", "B", "C"].map((l) => Math.hypot(at[l].x, at[l].y));
  radii.forEach((r) => assert.ok(Math.abs(r - radii[0]) < 1e-9, "hop 1 is not one ring"));
  assert.ok(Math.hypot(at["D"].x, at["D"].y) > radii[0], "hop 2 is not further out");
});

test("a topic beyond maxHops is not placed on any ring", () => {
  const hops = ego.hopsFrom(EGO, ["E"], BOTH);
  assert.equal(ego.ringPositions(EGO, ["E"], hops, 1)["D"], undefined);
});

test("overlap-only and semantic-only neighbours sit on different arcs", () => {
  /* The refusal made geometric: a ring whose radius or angle averaged
     the two strengths would be the fusion this design turns down, so
     the families get their own halves of the ring instead. */
  const mixed = {
    topics: EGO.topics,
    edges_overlap: [{ a: "E", b: "A", jaccard: 0.5, overlap_coeff: 1, p_value: 0.01, shared: ["x"] }],
    edges_semantic: [{ a: "E", b: "C", similarity: 0.7, bridge: ["x", "y"] }],
  };
  const hops = ego.hopsFrom(mixed, ["E"], BOTH);
  const at = ego.ringPositions(mixed, ["E"], hops, 2);
  assert.ok(at["A"].x > 0, "overlap neighbour is not on the overlap side");
  assert.ok(at["C"].x < 0, "semantic neighbour is not on the semantic side");
});

test("rings are deterministic", () => {
  const hops = ego.hopsFrom(EGO, ["E"], BOTH);
  assert.deepEqual(ego.ringPositions(EGO, ["E"], hops, 2), ego.ringPositions(EGO, ["E"], hops, 2));
});

test("two pinned topics share the centre rather than fighting over it", () => {
  const hops = ego.hopsFrom(EGO, ["E", "D"], BOTH);
  const at = ego.ringPositions(EGO, ["E", "D"], hops, 2);
  assert.notDeepEqual(at["E"], at["D"]);
  assert.ok(Math.hypot(at["E"].x, at["E"].y) < Math.hypot(at["A"].x, at["A"].y));
  assert.ok(Math.hypot(at["D"].x, at["D"].y) < Math.hypot(at["A"].x, at["A"].y));
});

test("pinning suspends the grouping rather than drawing rings inside boxes", () => {
  /* Two layout regimes competing for one canvas is a picture nobody can
     read and a test matrix nobody can hold. Grouping is for browsing
     the corpus; the ego view is for reading one neighbourhood. The cut
     is suspended while anything is pinned, and comes back when the last
     chip goes. */
  const all = new Set(["E", "A", "B", "C", "D"]);
  const cut = graph.cutTree(
    [{ id: "node-0", a: "A", b: "B", distance: 0.1 }],
    EGO.topics,
    0.5
  );
  const els = graph.elementsFor(EGO, new Set(["E", "A", "B", "C"]), ["E"], {
    context: "dim", all: all, cut: cut, collapsed: new Set(cut.groups.map((g) => g.id)),
  });
  assert.equal(els.filter((e) => e.data.isGroup || e.data.collapsed).length, 0);
  assert.equal(els.filter((e) => e.group === "nodes").length, 5);
  assert.equal(els.filter((e) => e.data.bundled).length, 0);
});

test("with nothing pinned the grouping is in force as before", () => {
  const all = new Set(["E", "A", "B", "C", "D"]);
  const cut = graph.cutTree(
    [{ id: "node-0", a: "A", b: "B", distance: 0.1 }],
    EGO.topics,
    0.5
  );
  const els = graph.elementsFor(EGO, all, [], {
    context: "dim", all: all, cut: cut, collapsed: new Set(cut.groups.map((g) => g.id)),
  });
  assert.equal(els.filter((e) => e.data.collapsed).length, 1);
});

// ---------- the panel ----------

const panel = require("../../assets/webapp/panel.js");

test("the ego panel reports both families side by side, and says they are the view's", () => {
  const html = panel.egoHtml("E", {
    overlap: ego.egoStats(EGO, "E", "overlap"),
    semantic: ego.egoStats(EGO, "E", "semantic"),
  });
  assert.match(html, /shared papers/i);
  assert.match(html, /semantic nearness/i);
  assert.match(html, /0\.33/);            // ego density over shared papers
  assert.match(html, /2\.33/);            // effective size
  assert.match(html, /in your browser/i); // view-derived, not a corpus claim
});

test("the ego panel says what the numbers mean, not just what they are", () => {
  const html = panel.egoHtml("E", {
    overlap: ego.egoStats(EGO, "E", "overlap"),
    semantic: ego.egoStats(EGO, "E", "semantic"),
  });
  assert.match(html, /theme|bridge/i);
});

test("a family with no neighbours reads as such rather than as a zero", () => {
  const html = panel.egoHtml("E", {
    overlap: ego.egoStats(EGO, "E", "overlap"),
    semantic: ego.egoStats(EGO, "E", "semantic"),
  });
  assert.match(html, /no neighbours/i);
  assert.ok(!html.includes("NaN"));
});

test("the ego panel escapes the topic label", () => {
  const hostile = { topics: [{ label: '<"x">', origin: "seed", terms: [], members: [] }],
    edges_overlap: [], edges_semantic: [] };
  const stats = ego.egoStats(hostile, '<"x">', "overlap");
  const html = panel.egoHtml('<"x">', { overlap: stats, semantic: stats });
  assert.ok(!html.includes('<"x">'));
  assert.match(html, /&lt;&quot;x&quot;&gt;/);
});

// ---------- the dimmed context ----------

test("the context is parked outside the rings, not deleted", () => {
  const hops = ego.hopsFrom(EGO, ["E"], BOTH);
  const rings = ego.ringPositions(EGO, ["E"], hops, 1);
  const outer = ego.contextRing(["E", "A", "B", "C", "D"], hops, 1);
  // D is two hops away, so it is context at maxHops = 1 ...
  assert.ok(outer["D"], "the context was dropped");
  assert.ok(
    Math.hypot(outer["D"].x, outer["D"].y) > Math.hypot(rings["A"].x, rings["A"].y),
    "the context is drawn inside the ego rings"
  );
  // ... and everything the rings placed is left alone.
  ["E", "A", "B", "C"].forEach((label) => assert.equal(outer[label], undefined));
});

test("a topic the selection cannot reach at all is context too", () => {
  const island = {
    topics: EGO.topics.concat([{ label: "Z", origin: "seed", terms: [], members: [] }]),
    edges_overlap: EGO.edges_overlap,
    edges_semantic: [],
  };
  const hops = ego.hopsFrom(island, ["E"], BOTH);
  assert.ok(ego.contextRing(["Z"], hops, 2)["Z"]);
});

test("the context ring is deterministic whatever order the labels arrive in", () => {
  const hops = ego.hopsFrom(EGO, ["E"], BOTH);
  assert.deepEqual(
    ego.contextRing(["D", "C", "B"], hops, 1),
    ego.contextRing(["B", "C", "D"], hops, 1)
  );
});

// ---------- what the hop control emphasises ----------

test("the emphasis set is everything within maxHops, roots included", () => {
  const hops = ego.hopsFrom(EGO, ["E"], BOTH);
  assert.deepEqual([...ego.withinHops(hops, 1)].sort(), ["A", "B", "C", "E"]);
  assert.deepEqual([...ego.withinHops(hops, 2)].sort(), ["A", "B", "C", "D", "E"]);
});

test("emphasis and rings agree, so nothing is placed on a ring but drawn faint", () => {
  /* The bug this pins: the rings were laid out to maxHops while the
     emphasis was fixed at one hop, so a two-hop topic sat on ring two
     dimmed to 12% -- drawn as important and as background at once. */
  const hops = ego.hopsFrom(EGO, ["E"], BOTH);
  [1, 2, 99].forEach((limit) => {
    const emphasised = ego.withinHops(hops, limit);
    const placed = ego.ringPositions(EGO, ["E"], hops, limit);
    assert.deepEqual([...emphasised].sort(), Object.keys(placed).sort(), "at " + limit);
  });
});

test("an unreachable topic is never emphasised, however far the control is opened", () => {
  const island = {
    topics: EGO.topics.concat([{ label: "Z", origin: "seed", terms: [], members: [] }]),
    edges_overlap: EGO.edges_overlap,
    edges_semantic: [],
  };
  assert.ok(!ego.withinHops(ego.hopsFrom(island, ["E"], BOTH), 99).has("Z"));
});

test("a lopsided ring gives each kind of neighbour room in proportion", () => {
  /* The bug this pins: fixed quadrants gave "reached by both families"
     a 40-degree wedge, and a real corpus put twenty neighbours in it
     stacked on one another while two-thirds of the ring stood empty. */
  const many = {
    topics: [{ label: "E", origin: "seed", terms: [], members: [] }].concat(
      Array.from({ length: 12 }, (_, i) => ({
        label: "n" + i, origin: "seed", terms: [], members: [],
      }))
    ),
    edges_overlap: Array.from({ length: 12 }, (_, i) => ({
      a: "E", b: "n" + i, jaccard: 0.5, overlap_coeff: 1, p_value: 0.01, shared: ["x"],
    })),
    edges_semantic: Array.from({ length: 10 }, (_, i) => ({
      a: "E", b: "n" + i, similarity: 0.7, bridge: ["x", "y"],
    })),
  };
  const hops = ego.hopsFrom(many, ["E"], BOTH);
  const at = ego.ringPositions(many, ["E"], hops, 1);
  const angles = Object.keys(at)
    .filter((k) => k !== "E")
    .map((k) => Math.atan2(at[k].y, at[k].x))
    .sort((x, y) => x - y);
  const gaps = angles.slice(1).map((a, i) => a - angles[i]);
  const biggest = Math.max(...gaps);
  // No two neighbours on top of each other, and no third of the ring
  // left empty while another third is stacked.
  assert.ok(Math.min(...gaps) > 0.01, "two neighbours share an angle");
  assert.ok(biggest < 1.2, "the ring has a hole of " + biggest.toFixed(2) + " radians");
});

test("hiding the context suspends the grouping too, not just dimming it", () => {
  /* The gap this pins: the cut was suspended on the dim path only, so
     "hide the rest of the corpus" with a cut in force emitted group
     boxes that the ring layout had no positions for -- every one of
     them stacked at the origin. */
  const cut = graph.cutTree(
    [{ id: "node-0", a: "A", b: "B", distance: 0.1 }],
    EGO.topics,
    0.5
  );
  const els = graph.elementsFor(EGO, new Set(["E", "A", "B", "C"]), ["E"], {
    context: "hide", all: new Set(["E", "A", "B", "C", "D"]),
    cut: cut, collapsed: new Set(cut.groups.map((g) => g.id)),
  });
  assert.equal(els.filter((e) => e.data.isGroup || e.data.collapsed).length, 0);
  assert.equal(els.filter((e) => e.group === "nodes").length, 4);
});

test("a ring grows with what is on it, and never shrinks inside the one before", () => {
  /* Twenty-two neighbours on a fixed 240-pixel ring get 68 pixels of
     arc each, and a node with its label is wider than that -- the real
     corpus drew them touching. */
  const crowd = {
    topics: [{ label: "E", origin: "seed", terms: [], members: [] }].concat(
      Array.from({ length: 30 }, (_, i) => ({
        label: "n" + i, origin: "seed", terms: [], members: [],
      }))
    ),
    edges_overlap: Array.from({ length: 30 }, (_, i) => ({
      a: "E", b: "n" + i, jaccard: 0.5, overlap_coeff: 1, p_value: 0.01, shared: ["x"],
    })),
    edges_semantic: [],
  };
  const at = ego.ringPositions(crowd, ["E"], ego.hopsFrom(crowd, ["E"], BOTH), 1);
  const placed = Object.keys(at).filter((k) => k !== "E");
  const gaps = placed.map((k) => at[k]).map((p, i, all) => {
    const next = all[(i + 1) % all.length];
    return Math.hypot(p.x - next.x, p.y - next.y);
  });
  assert.ok(Math.min(...gaps) > 80, "neighbours are " + Math.min(...gaps).toFixed(0) + "px apart");
});

test("an outer ring stays outside the ring it follows, however crowded that is", () => {
  // A hop-1 ring big enough to swallow a fixed-radius hop-2 ring: the
  // outer one has to be pushed out, not drawn through the inner.
  const hops = { E: 0, D: 2 };
  Array.from({ length: 40 }, (_, i) => { hops["m" + i] = 1; });
  const at = ego.ringPositions(EGO, ["E"], hops, 2);
  const inner = Math.hypot(at["m0"].x, at["m0"].y);
  assert.ok(inner > 2 * 240, "the crowded inner ring did not grow");
  assert.ok(Math.hypot(at["D"].x, at["D"].y) > inner, "hop 2 fell inside hop 1");
});

// ---------- the cross-runtime hop contract (#716) ----------

/* hop_cases.json holds hopsFrom/reachedVia and the terminal port
   (chitragupta/discover/_hops.py) to the same answers: this block
   asserts the browser side, tests/test_discover_hops.py the Python
   side. */
const HOP_CASES = require("./hop_cases.json").cases;

test("every shared hop case matches the browser's own walk", () => {
  assert.ok(HOP_CASES.length >= 2, "the table is read at all");
  /* A row naming its families is what pins the per-family walk to the
     terminal's. Without one the table would only ever check the union,
     and the two surfaces could disagree the moment either narrowed. */
  assert.ok(HOP_CASES.some((row) => row.families), "no single-family row");
  HOP_CASES.forEach((row) => {
    const data = {
      edges_overlap: row.edges_overlap,
      edges_semantic: row.edges_semantic,
    };
    const families = row.families || BOTH;
    const hops = ego.hopsFrom(data, row.roots, families);
    assert.deepEqual({ ...hops }, row.expected_hops, row.name);
    const via = ego.reachedVia(data, row.roots, families);
    assert.deepEqual({ ...via }, row.expected_via, row.name);
  });
});
// ---------- the cross-runtime brokerage contract (#713) ----------

/* brokerage_cases.json holds egoStats and the builder's networkx twin
   (chitragupta/enrich/topic_brokerage.py) to the same answers: this
   block asserts the browser side, tests/test_enrich_topic_brokerage.py
   the Python side. */
const BROKERAGE_CASES = require("./brokerage_cases.json").cases;

function caseData(row) {
  return {
    topics: row.labels.map((label) => ({ label, members: [] })),
    edges_overlap: row.edges.overlap,
    edges_semantic: row.edges.semantic,
  };
}

test("every shared brokerage case matches the browser's own arithmetic", () => {
  assert.ok(BROKERAGE_CASES.length >= 3, "the table is read at all");
  BROKERAGE_CASES.forEach((row) => {
    ["overlap", "semantic"].forEach((family) => {
      const got = ego.egoStats(caseData(row), row.ego, family);
      const want = row.expected[family];
      assert.equal(got.alters, want.degree, row.name + " " + family);
      assert.equal(got.density, want.ego_density, row.name + " " + family);
      assert.equal(Number(got.effectiveSize.toFixed(6)), want.effective_size,
        row.name + " " + family);
      const constraint = got.constraint === null
        ? null : Number(got.constraint.toFixed(6));
      assert.equal(constraint, want.constraint, row.name + " " + family);
    });
  });
});

test("stored analysis is preferred, and its absence falls back with a flag", () => {
  const row = BROKERAGE_CASES[0];
  const data = caseData(row);
  const topic = {
    label: row.ego,
    analysis: {
      overlap: { degree: 9, ego_density: 0.5, effective_size: 4.2, constraint: 0.1 },
    },
  };
  const stored = ego.statsFor(data, topic, "overlap");
  assert.deepEqual(stored, {
    alters: 9, density: 0.5, effectiveSize: 4.2, constraint: 0.1, stored: true,
  });
  const fallback = ego.statsFor(data, { label: row.ego }, "overlap");
  assert.equal(fallback.stored, false);
  assert.equal(fallback.alters, row.expected.overlap.degree);
});

// ---------- one family at a time ----------

/* The defect this block exists for: the rings used to be walked over
   the union of both families whatever the reader wanted, so a topic
   reached by one shared-paper hop followed by one cosine hop sat on
   ring 2 beside a topic two shared papers out. The placement was never
   fused -- ring 1 has always been typed by family -- but which topics
   are on the rings, and how far out, was decided by whichever family
   got there first.

       E --overlap-- A --semantic-- C

   Over shared papers alone, C is not two hops from E. It is not
   anywhere: nothing reaches it. */
const CHAIN = {
  n_docs: 4,
  topics: ["E", "A", "C"].map((label) => ({
    label: label, origin: "seed", terms: [],
    members: [{ citekey: label.toLowerCase() + "2020", title: label, score: 0.5 }],
  })),
  edges_overlap: [
    { a: "E", b: "A", jaccard: 0.5, overlap_coeff: 1, p_value: 0.01, shared: ["x2020"] },
  ],
  edges_semantic: [{ a: "A", b: "C", similarity: 0.7, bridge: ["x2020", "c2020"] }],
};

test("a semantic-only neighbour leaves the rings when the semantic family is off", () => {
  const hops = ego.hopsFrom(CHAIN, ["E"], ["overlap"]);
  const at = ego.ringPositions(CHAIN, ["E"], hops, 2, ["overlap"]);
  assert.ok(at["A"], "the shared-paper neighbour is still on ring 1");
  assert.equal(at["C"], undefined);
});

test("a two-hop path alternating families is not on ring 2 under one family", () => {
  // Both on: C is two hops out, which is today's behaviour and stays.
  const union = ego.hopsFrom(CHAIN, ["E"], BOTH);
  assert.equal(union["C"], 2);
  assert.ok(ego.ringPositions(CHAIN, ["E"], union, 2, BOTH)["C"]);
  // Shared papers alone: the question is "how far is this over shared
  // papers", and the answer for C is not two.
  assert.equal(ego.hopsFrom(CHAIN, ["E"], ["overlap"])["C"], undefined);
});

test("ring 1 is typed over the enabled families, not the payload's", () => {
  /* Without this, a neighbour reached over overlap that also happens to
     have a semantic edge still types as "both" and lands in the middle
     arc -- ring-1 placement consulting a family the reader switched
     off, which is the same defect one layer down. */
  const mixed = {
    topics: EGO.topics,
    edges_overlap: [
      { a: "E", b: "A", jaccard: 0.5, overlap_coeff: 1, p_value: 0.01, shared: ["x"] },
      { a: "E", b: "B", jaccard: 0.5, overlap_coeff: 1, p_value: 0.01, shared: ["x"] },
    ],
    edges_semantic: [
      { a: "E", b: "B", similarity: 0.7, bridge: ["x", "y"] },
      { a: "E", b: "C", similarity: 0.6, bridge: ["x", "y"] },
    ],
  };
  assert.equal(ego.reachedVia(mixed, ["E"], BOTH)["B"], "both");
  assert.equal(ego.reachedVia(mixed, ["E"], ["overlap"])["B"], "overlap");
  assert.equal(ego.reachedVia(mixed, ["E"], ["overlap"])["C"], undefined);
});

test("the families are both when the walk is asked without them", () => {
  /* Every caller before the picker existed passed four arguments to
     ringPositions and two to reachedVia. Absent must mean both, or the
     canvas those callers describe loses half its edges. */
  const hops = ego.hopsFrom(CHAIN, ["E"], BOTH);
  assert.deepEqual(ego.ringPositions(CHAIN, ["E"], hops, 2),
    ego.ringPositions(CHAIN, ["E"], hops, 2, BOTH));
  assert.deepEqual({ ...ego.reachedVia(CHAIN, ["E"]) },
    { ...ego.reachedVia(CHAIN, ["E"], BOTH) });
});
