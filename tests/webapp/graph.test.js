/* assets/webapp/graph.js: the payload logic behind the canvas -- which
   topics are visible, what cytoscape is handed, and what the type-ahead
   offers.

   These functions were extracted from app.js so they could be tested at
   all: everything here runs without a DOM and without cytoscape, which
   is the whole reason the split happened. The properties under test are
   the ones a reader would notice if they broke -- an empty selection
   showing everything, a selection pulling in its neighbours over *both*
   edge families, and a data-derived label never reaching through to
   Object.prototype. */
"use strict";

const test = require("node:test");
const assert = require("node:assert");

const graph = require("../../assets/webapp/graph.js");
const { DATA } = require("./fixture.js");

test("byLabel indexes every topic, on a null prototype", () => {
  const index = graph.byLabel(DATA.topics);
  assert.equal(index["digital twin"].origin, "seed");
  // The #636 crash: on a plain object this reads Object.prototype --
  // truthy, so it slips past a `||` fallback and has no .add.
  assert.equal(Object.getPrototypeOf(index), null);
  assert.equal(index['__proto__ <"hostile">'].origin, "corroborated");
});

test("elementsFor emits only nodes inside the visible set", () => {
  const els = graph.elementsFor(DATA, new Set(["digital twin"]), []);
  assert.deepEqual(els.map((e) => e.data.id), ["digital twin"]);
});

test("an edge is emitted only when both endpoints are visible", () => {
  const both = new Set(["digital twin", "machine learning"]);
  const edges = graph
    .elementsFor(DATA, both, [])
    .filter((e) => e.group === "edges");
  assert.equal(edges.length, 1);
  assert.equal(edges[0].data.family, "overlap");
  // The index is how the panel finds the edge again in the payload.
  assert.equal(edges[0].data.index, 0);
});

test("the two edge families keep their own id space and their own width scale", () => {
  const all = new Set(DATA.topics.map((t) => t.label));
  const edges = graph.elementsFor(DATA, all, []).filter((e) => e.group === "edges");
  const overlap = edges.find((e) => e.data.family === "overlap");
  const semantic = edges.find((e) => e.data.family === "semantic");
  assert.equal(overlap.data.id, "ov-0");
  assert.equal(semantic.data.id, "se-0");
  assert.equal(overlap.data.width, 1.5 + 6 * 0.5);
  assert.equal(semantic.data.width, 1 + 3 * 0.61);
});

test("a selected topic is marked picked, an unselected one is not", () => {
  const all = new Set(DATA.topics.map((t) => t.label));
  const nodes = graph
    .elementsFor(DATA, all, ["digital twin"])
    .filter((e) => e.group === "nodes");
  assert.equal(nodes.find((n) => n.data.id === "digital twin").data.picked, 1);
  assert.equal(nodes.find((n) => n.data.id === "topic-7").data.picked, 0);
});

test("node size grows with member count", () => {
  const [small, large] = [{ members: [1] }, { members: [1, 2, 3, 4] }];
  assert.ok(graph.nodeSize(large) > graph.nodeSize(small));
});

test("an unknown origin still gets a colour", () => {
  const odd = { label: "x", origin: "not-an-origin", members: [], terms: [] };
  const els = graph.elementsFor(
    { topics: [odd], edges_overlap: [], edges_semantic: [] },
    new Set(["x"]),
    []
  );
  assert.equal(els[0].data.color, graph.ORIGIN_COLORS.emergent);
});

test("the type-ahead matches labels and top terms, and says which", () => {
  assert.deepEqual(graph.candidatesFor(DATA, [], "digital"), [
    { label: "digital twin", why: "seed topic" },
  ]);
  assert.deepEqual(graph.candidatesFor(DATA, [], "neural"), [
    { label: "machine learning", why: "term: neural" },
  ]);
});

test("the type-ahead is case-insensitive and ignores surrounding space", () => {
  assert.deepEqual(graph.candidatesFor(DATA, [], "  DIGITAL "), [
    { label: "digital twin", why: "seed topic" },
  ]);
});

test("an empty query offers nothing, and an already-pinned topic is not re-offered", () => {
  assert.deepEqual(graph.candidatesFor(DATA, [], "   "), []);
  assert.deepEqual(graph.candidatesFor(DATA, ["digital twin"], "digital"), []);
});

test("the type-ahead offers at most twelve topics", () => {
  const many = {
    topics: Array.from({ length: 20 }, (_, i) => ({
      label: "topic-" + i,
      origin: "emergent",
      terms: [],
      members: [],
    })),
  };
  assert.equal(graph.candidatesFor(many, [], "topic").length, 12);
});

test("findMember reaches a paper in any topic, and reports a miss", () => {
  assert.equal(graph.findMember(DATA, "rv2018").title, "Runtime verification");
  assert.equal(graph.findMember(DATA, "nosuchkey2099"), null);
});

test("nextLatch latches an unlatched node", () => {
  assert.equal(graph.nextLatch(null, "digital twin"), "digital twin");
});

test("nextLatch releases on a second click of the same node", () => {
  assert.equal(graph.nextLatch("digital twin", "digital twin"), null);
});

test("nextLatch moves the latch to a different node", () => {
  assert.equal(graph.nextLatch("digital twin", "machine learning"), "machine learning");
});

test("nextLatch releases on a background tap regardless of what was latched", () => {
  assert.equal(graph.nextLatch("digital twin", null), null);
  assert.equal(graph.nextLatch(null, null), null);
});

test("escapeAction closes an open type-ahead ahead of releasing a latch", () => {
  assert.equal(graph.escapeAction(true, "digital twin"), "closeSuggestions");
});

test("escapeAction releases the latch once the type-ahead is closed", () => {
  assert.equal(graph.escapeAction(false, "digital twin"), "releaseLatch");
});

test("escapeAction does nothing with no list open and nothing latched", () => {
  assert.equal(graph.escapeAction(false, null), "none");
});

test("escapeAction shuts an open picker before it releases a latch", () => {
  /* Both landed in the same release and Esc means "back out of the
     thing that is open" for each of them. The latch is the wider
     gesture, so it goes last: a reader whose only reason for pressing
     Esc was the open panel would otherwise lose the neighbourhood they
     were reading as well. The type-ahead still outranks both. */
  assert.equal(graph.escapeAction(false, "digital twin", true), "closePicker");
  assert.equal(graph.escapeAction(false, null, true), "closePicker");
  assert.equal(graph.escapeAction(true, null, true), "closeSuggestions");
  // And with no panel open the two existing answers are unchanged.
  assert.equal(graph.escapeAction(false, "digital twin", false), "releaseLatch");
  assert.equal(graph.escapeAction(false, null, false), "none");
});

// ---------- the canvas moves with the family picker ----------

test("with both families on the canvas is unchanged", () => {
  /* The picker's first frame. `elementsFor` gained a families carrier,
     and every caller that does not pass one -- including the ones in
     this file written before it existed -- must get today's canvas. */
  const all = new Set(DATA.topics.map((t) => t.label));
  const before = graph.elementsFor(DATA, all, []);
  const both = graph.elementsFor(DATA, all, [], { families: ["overlap", "semantic"] });
  assert.deepEqual(both, before);
});

test("a switched-off family's edges leave the canvas", () => {
  const all = new Set(DATA.topics.map((t) => t.label));
  const edges = graph
    .elementsFor(DATA, all, [], { families: ["overlap"] })
    .filter((e) => e.group === "edges");
  assert.ok(edges.length);
  edges.forEach((e) => assert.equal(e.data.family, "overlap"));
  // The topics stay: the filter is about the lines, not the nodes.
  const nodes = graph
    .elementsFor(DATA, all, [], { families: ["overlap"] })
    .filter((e) => e.group === "nodes");
  assert.equal(nodes.length, DATA.topics.length);
});

test("filtering a family does not re-index the other one's edges", () => {
  /* The plain-edge id is "se-" plus an index into `edges_semantic`, and
     the panel resolves a clicked edge through it. Filtering by
     rebuilding the array would silently repoint every edge to its
     neighbour's evidence. */
  const two = {
    ...DATA,
    edges_semantic: [
      { a: "digital twin", b: "machine learning", similarity: 0.2, bridge: ["dt2022"] },
      { a: "machine learning", b: "topic-7", similarity: 0.61, bridge: ["ml2020", "rv2018"] },
    ],
  };
  const all = new Set(two.topics.map((t) => t.label));
  const edges = graph
    .elementsFor(two, all, [], { families: ["semantic"] })
    .filter((e) => e.group === "edges");
  assert.deepEqual(edges.map((e) => e.data.id).sort(), ["se-0", "se-1"]);
  const outer = edges.find((e) => e.data.id === "se-1");
  assert.equal(outer.data.index, 1);
  assert.equal(outer.data.width, 1 + 3 * 0.61);
});
