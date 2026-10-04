/* assets/webapp/graph.js: papers as nodes on the canvas (#676).

   Membership is the most concrete fact this pipeline has -- a real
   citekey, parsed from a real PDF -- and the app has always rendered it
   as a list. A paper belonging to three topics is exactly the object a
   survey wants to notice, and noticing it meant reading three panels
   and remembering what was in them. Expanded onto the canvas, the
   bridge becomes a shape.

   Three properties carry the weight here. A paper node is a *third*
   kind of node and its membership lines are a *third* kind of edge --
   neither may be counted or styled as overlap or semantic, which are
   claims about topic pairs and say nothing about membership. Expansion
   is capped, and the cap is visible rather than silent. And a citekey
   on a canvas is still a citekey: read from `members`, printed
   verbatim, never constructed. */
"use strict";

const test = require("node:test");
const assert = require("node:assert");

const graph = require("../../assets/webapp/graph.js");
const { DATA } = require("./fixture.js");

const ALL = new Set(DATA.topics.map((t) => t.label));

function paperNodes(els) {
  return els.filter((e) => e.group === "nodes" && e.data.kind === "paper");
}

function membershipEdges(els) {
  return els.filter((e) => e.group === "edges" && e.data.family === "member");
}

test("with nothing expanded the canvas is exactly what it was", () => {
  assert.deepEqual(
    graph.elementsFor(DATA, ALL, []),
    graph.elementsFor(DATA, ALL, [], { expanded: new Set() })
  );
});

test("expanding a topic draws its papers as their own kind of node", () => {
  const els = graph.elementsFor(DATA, ALL, [], { expanded: new Set(["digital twin"]) });
  const papers = paperNodes(els);
  assert.deepEqual(
    papers.map((p) => p.data.id).sort(),
    [graph.paperId(DATA, "dt2022"), graph.paperId(DATA, "sim2021")].sort()
  );
  // The citekey is the label, verbatim, and the title travels for hover.
  const dt = papers.find((p) => p.data.id === graph.paperId(DATA, "dt2022"));
  assert.equal(dt.data.label, "dt2022");
  assert.equal(dt.data.title, "A digital twin");
});

test("a paper node is joined to its topic by a membership edge, not by either family", () => {
  const els = graph.elementsFor(DATA, ALL, [], { expanded: new Set(["digital twin"]) });
  const edges = membershipEdges(els);
  assert.equal(edges.length, 2);
  edges.forEach((edge) => {
    assert.equal(edge.data.source, "digital twin");
    assert.equal(graph.citekeyOf(DATA, edge.data.target) !== null, true);
    assert.equal(edge.data.bundled, undefined, "membership is not a bundle");
    assert.equal(edge.data.surprise, undefined, "membership ran through no gate");
  });
  // And the two real families are untouched by the expansion.
  const families = els.filter((e) => e.group === "edges" && e.data.family !== "member");
  assert.deepEqual(
    families.map((e) => e.data.family).sort(),
    graph.elementsFor(DATA, ALL, [])
      .filter((e) => e.group === "edges").map((e) => e.data.family).sort()
  );
});

test("a paper in two expanded topics is one node with two lines -- the bridge, visible", () => {
  /* dt2022 is in both "digital twin" and "machine learning". This is
     the whole feature: one node, two edges, and a shape a reader can
     see instead of a citekey repeated in two panels. */
  const els = graph.elementsFor(DATA, ALL, [], {
    expanded: new Set(["digital twin", "machine learning"]),
  });
  const shared = paperNodes(els).filter((p) => p.data.id === graph.paperId(DATA, "dt2022"));
  assert.equal(shared.length, 1, "the paper was drawn twice");
  const lines = membershipEdges(els).filter((e) => e.data.target === graph.paperId(DATA, "dt2022"));
  assert.deepEqual(lines.map((e) => e.data.source).sort(), ["digital twin", "machine learning"]);
  assert.equal(shared[0].data.topics, 2, "a bridging paper says how many topics hold it");
  assert.equal(shared[0].data.drawn, 2, "and how many of them are on the canvas");
});

test("a paper is only joined to topics that are expanded, not to every topic holding it", () => {
  const els = graph.elementsFor(DATA, ALL, [], { expanded: new Set(["digital twin"]) });
  const lines = membershipEdges(els).filter((e) => e.data.target === graph.paperId(DATA, "dt2022"));
  assert.deepEqual(lines.map((e) => e.data.source), ["digital twin"]);
});

test("bridging is judged on what is drawn, not on the whole corpus", () => {
  /* On a real corpus almost every paper belongs to several topics, so
     colouring by the corpus-wide count paints every paper the same and
     says nothing. The reading that means something is "joined to more
     than one of the topics you opened". */
  const one = graph.elementsFor(DATA, ALL, [], { expanded: new Set(["digital twin"]) });
  const dt = paperNodes(one).find((p) => p.data.id === graph.paperId(DATA, "dt2022"));
  assert.equal(dt.data.topics, 2, "it is in two topics in the corpus");
  assert.equal(dt.data.drawn, 1, "but only one of them is on the canvas");
});

test("expanding a topic outside the visible set draws nothing", () => {
  const els = graph.elementsFor(DATA, new Set(["topic-7"]), ["topic-7"], {
    expanded: new Set(["digital twin"]),
  });
  assert.deepEqual(paperNodes(els), []);
});

test("a paper node carries its match score for sizing, clamped like the panel's bar", () => {
  const els = graph.elementsFor(DATA, ALL, [], { expanded: new Set(["digital twin"]) });
  const scores = paperNodes(els).map((p) => p.data.score);
  scores.forEach((score) => assert.ok(score >= 0 && score <= 1, String(score)));
});

test("the expansion is capped, and the cap is a number the UI can quote", () => {
  assert.equal(typeof graph.EXPANSION_CAP, "number");
  assert.ok(graph.EXPANSION_CAP >= 1 && graph.EXPANSION_CAP <= 10);
});

test("expanding past the cap draws the first topics, not a partial mess", () => {
  const many = new Set(DATA.topics.map((t) => t.label));
  const els = graph.elementsFor(DATA, ALL, [], { expanded: many });
  const sources = new Set(membershipEdges(els).map((e) => e.data.source));
  assert.equal(sources.size, graph.EXPANSION_CAP);
  // Payload order decides, so the same request always draws the same
  // thing rather than depending on click order.
  assert.deepEqual(
    [...sources],
    DATA.topics.slice(0, graph.EXPANSION_CAP).map((t) => t.label)
  );
});

test("a hostile citekey cannot collide with a topic id", () => {
  /* Node ids share one namespace, so a topic labelled `paper:dt2022`
     would otherwise be the same node as the paper dt2022 -- and a topic
     label is only semi-trusted data. The prefix is on the paper side,
     so the collision has to be *constructed*, and this pins that it
     still resolves to two nodes. */
  const hostile = {
    n_docs: 4,
    topics: [
      { label: "paper:dt2022", origin: "seed", terms: [], members: [] },
      DATA.topics[0],
    ],
    edges_overlap: [],
    edges_semantic: [],
  };
  const els = graph.elementsFor(hostile, new Set(["paper:dt2022", "digital twin"]), [], {
    expanded: new Set(["digital twin"]),
  });
  const ids = els.filter((e) => e.group === "nodes").map((e) => e.data.id);
  assert.equal(new Set(ids).size, ids.length, "two elements claimed one id: " + ids);
  // And the id still round-trips back to the citekey it stands for.
  assert.equal(graph.citekeyOf(hostile, graph.paperId(hostile, "dt2022")), "dt2022");
  assert.equal(graph.citekeyOf(hostile, "digital twin"), null);
});

// ---------- a paper in every view (#981) ----------

/* Papers used to be appended after the view pass had decorated the
   topics, so every per-view attribute a topic got, a paper did not:
   a dimmed topic's papers stayed bright (#981), the ego layout parked
   them on the far context ring and the grouped layout put them on the
   top-level circle among the boxes (#982), and a topic folded into a
   collapsed group still had its membership lines drawn to it (#936).
   One matrix over every view, each with papers open, so that a view
   added later is one row rather than a fresh bug. */

const ego = require("../../assets/webapp/ego.js");

const CUT = graph.cutTree(DATA.hierarchy, DATA.topics, 0.31);
const PAIR = CUT.groupOf["digital twin"];
const OPEN = new Set(["digital twin", "machine learning", "topic-7"]);
const BOTH = ["overlap", "semantic"];

/* topic-7 pinned: machine learning is one hop away, digital twin two,
   so with one hop shown digital twin is the context. dt2022 belongs to
   both open neighbours, which makes it the case where a paper's dim
   and a topic's can part. */
function ego1(context) {
  const hops = ego.hopsFrom(DATA, ["topic-7"], BOTH);
  const visible = graph.restrictTo(ego.withinHops(hops, 1), ALL);
  const view = { context, all: ALL, expanded: OPEN };
  return {
    els: graph.elementsFor(DATA, visible, ["topic-7"], view),
    place: (els) => ego.ringLayout(DATA, els, ["topic-7"], hops, 1, BOTH),
  };
}

const VIEWS = {
  ungrouped: () => ({ els: graph.elementsFor(DATA, ALL, [], { expanded: OPEN }) }),
  grouped: () => ({
    els: graph.elementsFor(DATA, ALL, [], { cut: CUT, collapsed: new Set(), expanded: OPEN }),
    place: graph.positionsFor,
  }),
  collapsed: () => ({
    els: graph.elementsFor(DATA, ALL, [], { cut: CUT, collapsed: new Set([PAIR]), expanded: OPEN }),
    place: graph.positionsFor,
  }),
  "ego, context dimmed": () => ego1("dim"),
  "ego, context hidden": () => ego1("hide"),
};

function distance(p, q) {
  return Math.hypot(p.x - q.x, p.y - q.y);
}

for (const [name, build] of Object.entries(VIEWS)) {
  test(`${name}: every paper takes its view attributes from its topic`, () => {
    const { els, place } = build();
    const nodes = Object.create(null);
    els.filter((e) => e.group === "nodes").forEach((e) => { nodes[e.data.id] = e; });

    // No line may end at a node that is not drawn (#936): cytoscape
    // throws on it and leaves the redraw half-applied.
    els.filter((e) => e.group === "edges").forEach((e) => {
      assert.ok(nodes[e.data.source], `${e.data.id} starts at undrawn ${e.data.source}`);
      assert.ok(nodes[e.data.target], `${e.data.id} ends at undrawn ${e.data.target}`);
    });

    const at = place ? place(els) : null;
    const topics = Object.values(nodes).filter((n) => !n.data.kind && !n.data.isGroup && !n.data.collapsed);
    const papers = paperNodes(els);
    assert.ok(papers.length, "the view drew no papers to check");
    papers.forEach((paper) => {
      const lines = membershipEdges(els).filter((e) => e.data.target === paper.data.id);
      const holders = lines.map((e) => nodes[e.data.source]);
      // Beside the brightest topic holding it, the first of those if
      // several tie: a bright paper by a dimmed topic on the context
      // ring is #982 again, for exactly the papers the reader can see.
      const dims = holders.map((h) => h.data.dim);
      const anchor = dims[0] === undefined ? holders[0] : holders[dims.indexOf(Math.min(...dims))];
      // Inside its topic's box, so the box is drawn round it.
      assert.equal(paper.data.parent, anchor.data.parent, `${paper.data.id}'s parent`);
      // As bright as the brightest topic holding it, and each line as
      // bright as the topic it leaves.
      assert.equal(paper.data.dim, dims[0] === undefined ? undefined : Math.min(...dims),
        `${paper.data.id}'s dim`);
      lines.forEach((line) => {
        assert.equal(line.data.dim, nodes[line.data.source].data.dim, `${line.data.id}'s dim`);
      });
      if (!at) { return; }
      // Beside its topic: nearer to it than to any other topic, so not
      // on a ring or circle of its own.
      const mine = at[paper.data.id];
      assert.ok(mine, `${paper.data.id} was not placed`);
      const nearest = topics.reduce((best, t) =>
        distance(at[t.data.id], mine) < distance(at[best.data.id], mine) ? t : best);
      assert.equal(nearest.data.id, anchor.data.id, `${paper.data.id} sits by ${nearest.data.id}`);
    });
  });
}

test("collapsing a group takes its topics' papers off with them", () => {
  const { els } = VIEWS.collapsed();
  const lines = membershipEdges(els).map((e) => e.data.source);
  assert.deepEqual([...new Set(lines)], ["topic-7"]);
  // Remembered, so the papers come back when the group is reopened.
  assert.equal(paperNodes(VIEWS.grouped().els).length, 5);
});

test("a dimmed topic's papers are dimmed, and a paper a bright topic also holds is not", () => {
  const { els } = ego1("dim");
  const dimOf = (citekey) => paperNodes(els).find((p) => p.data.id === graph.paperId(DATA, citekey)).data.dim;
  assert.equal(dimOf("sim2021"), 1, "only digital twin, the context, holds it");
  assert.equal(dimOf("dt2022"), 0, "machine learning, in focus, holds it too");
  assert.equal(dimOf("rv2018"), 0);
});

// ---------- the panel ----------

const panel = require("../../assets/webapp/panel.js");

test("a paper node's panel is the paper, with the topics that hold it", () => {
  const html = panel.paperHtml(DATA, "dt2022");
  assert.match(html, /<code>dt2022<\/code>/);
  assert.match(html, /A digital twin/);
  assert.match(html, /data-goto="digital twin"/);
  assert.match(html, /data-goto="machine learning"/);
  assert.match(html, /2 topics/);
});

test("a paper in one topic is not described as a bridge", () => {
  const html = panel.paperHtml(DATA, "sim2021");
  assert.match(html, /1 topic/);
  assert.ok(!html.match(/bridges/i));
});

test("a bridging paper is named as one", () => {
  assert.match(panel.paperHtml(DATA, "dt2022"), /bridges/i);
});

test("a citekey the payload does not know is refused rather than invented", () => {
  assert.equal(panel.paperHtml(DATA, "nosuch2099"), null);
});

test("the paper panel escapes a hostile title", () => {
  const html = panel.paperHtml(DATA, "x2017");
  assert.ok(!html.includes("Odd <one>"));
  assert.match(html, /Odd &lt;one&gt;/);
});
