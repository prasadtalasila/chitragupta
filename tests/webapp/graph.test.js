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
  assert.equal(index['__proto__ <"hostile">'].origin, "both");
});

test("adjacency unions both edge families, in both directions", () => {
  const near = graph.adjacency(DATA);
  assert.deepEqual([...near["digital twin"]], ["machine learning"]);
  assert.deepEqual([...near["machine learning"]].sort(), ["digital twin", "topic-7"]);
  assert.deepEqual([...near["topic-7"]], ["machine learning"]);
  assert.equal(Object.getPrototypeOf(near), null);
});

test("a topic on no edge has no adjacency entry", () => {
  const near = graph.adjacency(DATA);
  assert.equal(near['__proto__ <"hostile">'], undefined);
});

test("no selection shows every topic", () => {
  const near = graph.adjacency(DATA);
  const visible = graph.visibleLabels(DATA, [], near);
  assert.equal(visible.size, DATA.topics.length);
});

test("a selection shows itself and its neighbours over both families", () => {
  const near = graph.adjacency(DATA);
  const visible = graph.visibleLabels(DATA, ["machine learning"], near);
  assert.deepEqual([...visible].sort(), ["digital twin", "machine learning", "topic-7"]);
});

test("selecting a topic with no edges shows only itself", () => {
  const near = graph.adjacency(DATA);
  const visible = graph.visibleLabels(DATA, ['__proto__ <"hostile">'], near);
  assert.deepEqual([...visible], ['__proto__ <"hostile">']);
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
