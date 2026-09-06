/* assets/webapp/graph.js: cutting the stored merge tree into groups,
   and drawing those groups collapsed (#671, #672).

   The tree is not re-fitted here and nothing is stored: the app cuts
   the `hierarchy` the topic-graph stage already wrote, at a distance
   the reader drags. So the properties worth pinning are the ones that
   make that honest -- the same threshold always yields the same
   groups, a cut at zero groups nothing, a cut past the last merge
   groups everything, and an internal merge id is resolved to its
   leaves rather than treated as a topic. */
"use strict";

const test = require("node:test");
const assert = require("node:assert");

const graph = require("../../assets/webapp/graph.js");
const { DATA } = require("./fixture.js");

// digital twin + machine learning merge at 0.31; topic-7 joins them at
// 0.52 (naming the merge, not a topic); the hostile label never merges,
// so it is the ungrouped-leaf case in every assertion below.
const TREE = [
  { id: "node-0", a: "digital twin", b: "machine learning", distance: 0.31 },
  { id: "node-1", a: "topic-7", b: "node-0", distance: 0.52 },
];
const TOPICS = DATA.topics;
const LABELS = TOPICS.map((t) => t.label);

function groupsAt(threshold) {
  return graph.cutTree(TREE, TOPICS, threshold);
}

test("a cut below every merge leaves each topic in its own group", () => {
  const cut = groupsAt(0);
  assert.equal(cut.groups.length, LABELS.length);
  assert.equal(cut.groups.every((g) => g.members.length === 1), true);
});

test("a cut above one merge joins exactly that pair", () => {
  const cut = groupsAt(0.4);
  const joined = cut.groups.find((g) => g.members.length > 1);
  assert.deepEqual(joined.members.slice().sort(), ["digital twin", "machine learning"]);
  assert.equal(cut.groups.length, 3);
});

test("a merge naming an earlier merge is resolved to its leaves", () => {
  // node-1 joins topic-7 to node-0, which is *not* a topic label. A cut
  // that treated "node-0" as a member would put a phantom on the canvas
  // and leave the two real topics behind.
  const cut = groupsAt(0.6);
  const joined = cut.groups.find((g) => g.members.length > 1);
  assert.deepEqual(joined.members.slice().sort(), [
    "digital twin", "machine learning", "topic-7",
  ]);
  assert.ok(!JSON.stringify(cut.groups).includes("node-0"));
});

test("a topic the tree never mentions still gets a group of its own", () => {
  const cut = groupsAt(1);
  const alone = cut.groups.find((g) => g.members.length === 1);
  assert.deepEqual(alone.members, ['__proto__ <"hostile">']);
});

test("every topic lands in exactly one group, at any threshold", () => {
  [0, 0.2, 0.31, 0.4, 0.52, 5].forEach((t) => {
    const cut = groupsAt(t);
    const seen = cut.groups.flatMap((g) => g.members);
    assert.equal(seen.length, LABELS.length, "threshold " + t);
    assert.deepEqual(seen.slice().sort(), LABELS.slice().sort(), "threshold " + t);
    LABELS.forEach((label) => assert.ok(cut.groupOf[label], label + " at " + t));
  });
});

test("the cut is inclusive of the threshold, so a slider can sit on a merge", () => {
  assert.equal(groupsAt(0.31).groups.length, 3);
  assert.equal(groupsAt(0.3099).groups.length, 4);
});

test("the same threshold always yields the same groups, ids included", () => {
  assert.deepEqual(groupsAt(0.52), groupsAt(0.52));
});

test("group ids follow payload order, so they do not shuffle between cuts", () => {
  const cut = groupsAt(0.4);
  assert.equal(cut.groupOf["digital twin"], cut.groups[0].id);
  assert.match(cut.groups[0].id, /^cluster-/);
});

test("the group table has a null prototype", () => {
  assert.equal(Object.getPrototypeOf(groupsAt(0.4).groupOf), null);
});

test("a group is labelled from its own members, never invented", () => {
  const cut = groupsAt(0.6);
  const joined = cut.groups.find((g) => g.members.length > 1);
  // The largest member leads (machine learning has 3 papers), and the
  // rest are counted rather than listed -- a label is a summary of real
  // topic labels, not a name the app made up.
  assert.equal(joined.label, "machine learning +2");
  const alone = cut.groups.find((g) => g.members.length === 1);
  assert.equal(alone.label, alone.members[0]);
});

test("the default cut aims at a readable number of groups", () => {
  // 131 topics is the real corpus; the app opens at roughly eight
  // groups rather than at the hairball.
  const threshold = graph.thresholdForGroups(TREE, TOPICS, 2);
  assert.equal(graph.cutTree(TREE, TOPICS, threshold).groups.length, 2);
});

test("asking for more groups than there are topics gives every topic its own", () => {
  const threshold = graph.thresholdForGroups(TREE, TOPICS, 99);
  assert.equal(graph.cutTree(TREE, TOPICS, threshold).groups.length, LABELS.length);
});

test("asking for one group collapses the tree as far as it goes", () => {
  const threshold = graph.thresholdForGroups(TREE, TOPICS, 1);
  // This tree never joins the hostile label, so two is as far as it goes:
  // the target is a target, not a promise.
  assert.equal(graph.cutTree(TREE, TOPICS, threshold).groups.length, 2);
});

test("an empty tree cuts to one group per topic and needs no threshold", () => {
  const cut = graph.cutTree([], TOPICS, 0.5);
  assert.equal(cut.groups.length, LABELS.length);
  assert.equal(graph.thresholdForGroups([], TOPICS, 8), 0);
});

// ---------- drawing the cut ----------

test("an expanded group draws its topics inside a compound parent", () => {
  const cut = groupsAt(0.4);
  const els = graph.elementsFor(DATA, new Set(LABELS), [], { cut: cut, collapsed: new Set() });
  const child = els.find((e) => e.data.id === "digital twin");
  assert.equal(child.data.parent, cut.groupOf["digital twin"]);
});

test("a group of one draws bare, with no box around a single topic", () => {
  // Three groups at this cut, but only one of them has anything to
  // group: a compound parent around a lone topic is a box that says
  // nothing and costs the reader a nesting level to read past.
  const cut = groupsAt(0.4);
  const els = graph.elementsFor(DATA, new Set(LABELS), [], { cut: cut, collapsed: new Set() });
  assert.equal(cut.groups.length, 3);
  assert.equal(els.filter((e) => e.data.isGroup).length, 1);
  assert.equal(els.find((e) => e.data.id === "topic-7").data.parent, undefined);
});

test("a collapsed group draws as one node carrying its member count", () => {
  const cut = groupsAt(0.4);
  const gid = cut.groupOf["digital twin"];
  const els = graph.elementsFor(DATA, new Set(LABELS), [], {
    cut: cut, collapsed: new Set([gid]),
  });
  const ids = els.filter((e) => e.group === "nodes").map((e) => e.data.id);
  assert.ok(ids.includes(gid));
  assert.ok(!ids.includes("digital twin"));
  assert.ok(!ids.includes("machine learning"));
  const meta = els.find((e) => e.data.id === gid);
  assert.equal(meta.data.collapsed, 1);
  assert.equal(meta.data.count, 2);
  assert.match(meta.data.label, /machine learning \+1/);
});

test("an edge inside a collapsed group is not drawn at all", () => {
  const cut = groupsAt(0.4);
  const gid = cut.groupOf["digital twin"];
  const els = graph.elementsFor(DATA, new Set(LABELS), [], {
    cut: cut, collapsed: new Set([gid]),
  });
  // The one overlap edge joins the two topics now inside this group.
  assert.equal(els.filter((e) => e.group === "edges").length, 1);
  assert.equal(els.find((e) => e.group === "edges").data.family, "semantic");
});

test("an edge leaving a collapsed group is bundled onto the meta-node", () => {
  const cut = groupsAt(0.4);
  const gid = cut.groupOf["machine learning"];
  const els = graph.elementsFor(DATA, new Set(LABELS), [], {
    cut: cut, collapsed: new Set([gid]),
  });
  const bundle = els.find((e) => e.group === "edges" && e.data.family === "semantic");
  assert.equal(bundle.data.source, gid);
  assert.equal(bundle.data.target, "topic-7");
  assert.equal(bundle.data.bundled, 1);
  assert.equal(bundle.data.count, 1);
  // The constituents stay reachable, so a bundle can be explained by
  // naming the pairs it stands for.
  assert.deepEqual(bundle.data.pairs, [{ family: "semantic", index: 0 }]);
});

test("bundles are never fused across the two edge families", () => {
  const wide = {
    topics: DATA.topics,
    edges_overlap: [
      { a: "digital twin", b: "topic-7", jaccard: 0.2, overlap_coeff: 0.4, p_value: 0.01, shared: ["dt2022"] },
    ],
    edges_semantic: [
      { a: "machine learning", b: "topic-7", similarity: 0.61, bridge: ["ml2020", "rv2018"] },
    ],
  };
  const cut = graph.cutTree(TREE, TOPICS, 0.4);
  const gid = cut.groupOf["digital twin"];
  const edges = graph
    .elementsFor(wide, new Set(LABELS), [], { cut: cut, collapsed: new Set([gid]) })
    .filter((e) => e.group === "edges");
  assert.equal(edges.length, 2);
  assert.deepEqual(edges.map((e) => e.data.family).sort(), ["overlap", "semantic"]);
  edges.forEach((e) => assert.equal(e.data.count, 1));
});

test("two edges of one family between the same pair of groups bundle into one", () => {
  const twice = {
    topics: DATA.topics,
    edges_overlap: [
      { a: "digital twin", b: "topic-7", jaccard: 0.2, overlap_coeff: 0.4, p_value: 0.01, shared: ["dt2022"] },
      { a: "machine learning", b: "topic-7", jaccard: 0.1, overlap_coeff: 0.2, p_value: 0.02, shared: ["ml2020"] },
    ],
    edges_semantic: [],
  };
  const cut = graph.cutTree(TREE, TOPICS, 0.4);
  const gid = cut.groupOf["digital twin"];
  const edges = graph
    .elementsFor(twice, new Set(LABELS), [], { cut: cut, collapsed: new Set([gid]) })
    .filter((e) => e.group === "edges");
  assert.equal(edges.length, 1);
  assert.equal(edges[0].data.count, 2);
  assert.equal(edges[0].data.pairs.length, 2);
  // Width tracks the strongest constituent, not their sum: a bundle of
  // two weak links must not outdraw one strong one.
  assert.equal(edges[0].data.width, 1.5 + 6 * 0.4);
});

test("with no cut at all the elements are exactly what they were before grouping", () => {
  const all = new Set(LABELS);
  assert.deepEqual(
    graph.elementsFor(DATA, all, []),
    graph.elementsFor(DATA, all, [], { cut: null, collapsed: new Set() })
  );
});

test("a bundle between two collapsed groups joins meta-node to meta-node", () => {
  const paired = [
    { id: "node-0", a: "digital twin", b: "machine learning", distance: 0.31 },
    { id: "node-1", a: "topic-7", b: '__proto__ <"hostile">', distance: 0.35 },
  ];
  const cut = graph.cutTree(paired, TOPICS, 0.4);
  const a = cut.groupOf["machine learning"];
  const b = cut.groupOf["topic-7"];
  const els = graph.elementsFor(DATA, new Set(LABELS), [], {
    cut: cut, collapsed: new Set([a, b]),
  });
  const semantic = els.find((e) => e.group === "edges" && e.data.family === "semantic");
  assert.equal(semantic.data.source, a);
  assert.equal(semantic.data.target, b);
  assert.equal(els.filter((e) => e.group === "nodes").length, 2);
});

test("a collapsed group holding one visible topic draws that topic, not a meta-node", () => {
  // Collapsing is a legibility move; wrapping a single topic in a
  // meta-node labelled "+0" would cost the reader a click to reach
  // something already on the canvas.
  const cut = groupsAt(0);
  const gid = cut.groupOf["digital twin"];
  const els = graph.elementsFor(DATA, new Set(LABELS), [], {
    cut: cut, collapsed: new Set([gid]),
  });
  const ids = els.filter((e) => e.group === "nodes").map((e) => e.data.id);
  assert.ok(ids.includes("digital twin"));
  assert.ok(!ids.includes(gid));
});

test("a collapsed group hides a topic that is not in the visible set", () => {
  // Selection filtering still applies underneath the grouping: a group
  // whose members are all filtered out must not appear as a meta-node.
  const cut = groupsAt(0.4);
  const gid = cut.groupOf["digital twin"];
  const els = graph.elementsFor(DATA, new Set(["topic-7"]), ["topic-7"], {
    cut: cut, collapsed: new Set([gid]),
  });
  assert.deepEqual(els.filter((e) => e.group === "nodes").map((e) => e.data.id), ["topic-7"]);
});

test("a collapsed meta-node reports the count of its visible members only", () => {
  const cut = groupsAt(0.6);
  const gid = cut.groupOf["digital twin"];
  const els = graph.elementsFor(DATA, new Set(["digital twin", "topic-7"]), [], {
    cut: cut, collapsed: new Set([gid]),
  });
  assert.equal(els.find((e) => e.data.id === gid).data.count, 2);
});

// ---------- the panel for a group and for a bundle ----------

const panel = require("../../assets/webapp/panel.js");

test("a group panel lists its member topics and says the grouping is the reader's view", () => {
  const cut = groupsAt(0.6);
  const group = cut.groups.find((g) => g.members.length > 1);
  const html = panel.groupHtml(group);
  assert.match(html, /3 topics/);
  assert.match(html, /data-goto="digital twin"/);
  assert.match(html, /data-goto="topic-7"/);
  // The honesty line: this grouping was computed in this browser from
  // the stored tree, and `--json` will not report it.
  assert.match(html, /in your browser/i);
  assert.match(html, /merge tree/i);
});

test("a group panel escapes a hostile member label", () => {
  const cut = groupsAt(0);
  const alone = cut.groups.find((g) => g.members[0].startsWith("__proto__"));
  const html = panel.groupHtml(alone);
  assert.ok(!html.includes('<"hostile">'));
});

test("a bundle panel names every link it stands for, with its evidence", () => {
  const html = panel.bundleHtml(DATA, [
    { family: "overlap", index: 0 },
    { family: "semantic", index: 0 },
  ]);
  assert.match(html, /2 links/);
  assert.match(html, /digital twin/);
  assert.match(html, /machine learning/);
  assert.match(html, /shares 1 paper/);
  assert.match(html, /0\.61/);
  assert.match(html, /data-edge="overlap:0"/);
  assert.match(html, /data-edge="semantic:0"/);
});

test("a bundle panel keeps the two families apart rather than totalling them", () => {
  const html = panel.bundleHtml(DATA, [
    { family: "overlap", index: 0 },
    { family: "semantic", index: 0 },
  ]);
  assert.match(html, /1 over shared papers/);
  assert.match(html, /1 over semantic nearness/);
});

// ---------- laying the cut out ----------

test("every drawable node gets a position, and children sit inside their group", () => {
  const cut = groupsAt(0.6);
  const gid = cut.groupOf["digital twin"];
  const els = graph.elementsFor(DATA, new Set(LABELS), [], { cut: cut, collapsed: new Set() });
  const at = graph.positionsFor(els);
  els.filter((e) => e.group === "nodes" && !e.data.isGroup).forEach((n) => {
    assert.ok(at[n.data.id], "no position for " + n.data.id);
  });
  // A compound parent is positioned by cytoscape from its children, so
  // it must not be given one of its own.
  assert.equal(at[gid], undefined);
  const centre = graph.groupCentre(els, at, gid);
  ["digital twin", "machine learning", "topic-7"].forEach((label) => {
    const d = Math.hypot(at[label].x - centre.x, at[label].y - centre.y);
    assert.ok(d < centre.radius + 1, label + " is outside its own group");
  });
});

test("the same elements always land in the same places", () => {
  const cut = groupsAt(0.6);
  const els = graph.elementsFor(DATA, new Set(LABELS), [], { cut: cut, collapsed: new Set() });
  assert.deepEqual(graph.positionsFor(els), graph.positionsFor(els));
});

test("two groups are laid out far enough apart not to overlap", () => {
  const paired = [
    { id: "node-0", a: "digital twin", b: "machine learning", distance: 0.31 },
    { id: "node-1", a: "topic-7", b: '__proto__ <"hostile">', distance: 0.35 },
  ];
  const cut = graph.cutTree(paired, TOPICS, 0.4);
  const els = graph.elementsFor(DATA, new Set(LABELS), [], { cut: cut, collapsed: new Set() });
  const at = graph.positionsFor(els);
  const one = graph.groupCentre(els, at, cut.groupOf["digital twin"]);
  const two = graph.groupCentre(els, at, cut.groupOf["topic-7"]);
  const gap = Math.hypot(one.x - two.x, one.y - two.y);
  assert.ok(gap > one.radius + two.radius, "groups overlap: " + gap);
});

test("a lone node is placed rather than left at the origin with everything else", () => {
  const els = graph.elementsFor(DATA, new Set(LABELS), []);
  const at = graph.positionsFor(els);
  const seen = new Set(Object.keys(at).map((id) => at[id].x + "," + at[id].y));
  assert.equal(seen.size, LABELS.length);
});
