/* Filtering the canvas by topic origin: the class vocabulary, and
   every consumer of the label universe that has to move with it. The
   control itself is a picker row now rather than a loose checkbox, and
   tests/webapp/picker.test.js covers the widget; what is here is the
   filtering the widget drives.

   The properties under test are the ones a reader would notice if they
   broke -- the type-ahead offering a topic that is not on the canvas,
   a hierarchy row naming a topic the filter removed, a row for a class
   this export never contained looking merely unticked, and the last
   class going out to leave an empty canvas that reads as an empty
   corpus. */
"use strict";

const test = require("node:test");
const assert = require("node:assert");

const graph = require("../../assets/webapp/graph.js");
const panel = require("../../assets/webapp/panel.js");
const { DATA } = require("./fixture.js");

const ALL = new Set(graph.ORIGIN_CLASSES);

test("the four classes are the app's vocabulary, in the reader's order", () => {
  assert.deepEqual(graph.ORIGIN_CLASSES, ["seed", "keyword", "corroborated", "emergent"]);
  // Every class has a colour and a human name, or a legend entry lies.
  graph.ORIGIN_CLASSES.forEach((origin) => {
    assert.ok(graph.ORIGIN_COLORS[origin], origin);
    assert.ok(graph.ORIGIN_LABELS[origin], origin);
  });
});

test("the universe is the labels whose origin is ticked", () => {
  const labels = graph.labelsWithOrigins(DATA, new Set(["emergent"]));
  assert.deepEqual([...labels], ["topic-7"]);
});

test("corroborated is its own row, not a rider on seed", () => {
  /* The CLI's `--origins seed` is inclusive of corroborated, because
     three words cannot express four classes and hiding a hand-written
     topic from someone who asked for hand-written topics would be
     wrong. The app has a row per class, so here each one is literal:
     every row the reader can tick does something when ticked.

     The two still agree on what a reader sees, because the app opens
     with every class that shipped ticked -- see the test below. */
  const bySeed = graph.labelsWithOrigins(DATA, new Set(["seed"]));
  assert.deepEqual([...bySeed], ["digital twin"]);
  const only = graph.labelsWithOrigins(DATA, new Set(["corroborated"]));
  assert.deepEqual([...only], ['__proto__ <"hostile">']);
});

test("the app opens showing exactly what the export shipped", () => {
  // `--origins seed` ships seed *and* corroborated topics, and both are
  // recorded in `origins` -- so an app opened over that export shows
  // both, which is what the same flag showed in the terminal.
  const shipped = { ...DATA, origins: ["seed", "corroborated"] };
  const opening = new Set(graph.shippedOrigins(shipped));
  const labels = graph.labelsWithOrigins(shipped, opening);
  assert.deepEqual([...labels].sort(), ['__proto__ <"hostile">', "digital twin"]);
});

test("every class ticked is every topic", () => {
  const labels = graph.labelsWithOrigins(DATA, ALL);
  assert.equal(labels.size, DATA.topics.length);
});

test("a payload with no origin field is treated as emergent, not dropped", () => {
  // An older data.js, or a topic the annotation could not classify: it
  // still belongs on the canvas, because a topic silently absent is
  // worse than one in the wrong colour.
  const older = { topics: [{ label: "x", provenance: "emergent" }] };
  assert.ok(graph.labelsWithOrigins(older, new Set(["emergent"])).has("x"));
});

test("a hop ring is cut back to the visible universe", () => {
  // The rings are walked over the whole payload, so a neighbour two
  // hops out can be a topic the filter has taken off the canvas.
  const reached = new Set(["digital twin", "machine learning", "topic-7"]);
  const kept = graph.restrictTo(reached, new Set(["topic-7"]));
  assert.deepEqual([...kept], ["topic-7"]);
});

test("the type-ahead offers only what the canvas is showing", () => {
  const active = new Set(["emergent"]);
  const found = graph.candidatesFor(DATA, [], "i", active);
  assert.ok(found.length);
  found.forEach((hit) => assert.equal(hit.label, "topic-7"));
});

test("the type-ahead is unfiltered when no selection is passed", () => {
  // Every existing caller passes three arguments; the fourth is the
  // filter, and its absence must mean "everything" rather than nothing.
  const found = graph.candidatesFor(DATA, [], "learning");
  assert.deepEqual(found.map((hit) => hit.label), ["machine learning"]);
});

test("the controls report each class, its count, and whether it shipped", () => {
  // As `--origins emergent` writes it: only emergent topics in the
  // payload, and `origins` saying that is the export's doing.
  const shipped = {
    ...DATA,
    topics: DATA.topics.filter((t) => t.origin === "emergent"),
    origins: ["emergent"],
  };
  const controls = graph.originControls(shipped, new Set(["emergent"]));
  assert.deepEqual(controls.map((c) => c.origin), graph.ORIGIN_CLASSES);
  const emergent = controls.find((c) => c.origin === "emergent");
  assert.equal(emergent.shipped, true);
  assert.equal(emergent.checked, true);
  assert.equal(emergent.count, 1);
  // A class this export excluded is not merely unticked: nothing the
  // reader does can bring it back, so it says so.
  const seed = controls.find((c) => c.origin === "seed");
  assert.equal(seed.shipped, false);
  assert.equal(seed.count, 0);
});

test("a payload that records no origins is treated as carrying all four", () => {
  const controls = graph.originControls({ topics: [] }, ALL);
  controls.forEach((c) => assert.equal(c.shipped, true, c.origin));
});

test("toggling a class off returns the smaller selection", () => {
  const next = graph.nextSelection(ALL, "emergent", false);
  assert.ok(!next.has("emergent"));
  assert.equal(next.size, 3);
});

test("toggling the last class off is refused", () => {
  // An empty canvas reads as an empty corpus. The caller restores the
  // tick rather than drawing nothing.
  assert.equal(graph.nextSelection(new Set(["seed"]), "seed", false), null);
});

test("toggling a class on returns the larger selection, and does not mutate", () => {
  const active = new Set(["seed"]);
  const next = graph.nextSelection(active, "emergent", true);
  assert.deepEqual([...active], ["seed"]);
  assert.equal(next.size, 2);
});

test("the origin picker escapes what it renders and marks the excluded", () => {
  const shipped = { ...DATA, origins: ["emergent"] };
  const html = panel.originsHtml(graph.originControls(shipped, new Set(["emergent"])), shipped);
  assert.ok(html.includes('data-origin="emergent"'));
  assert.ok(html.includes("checked"));
  assert.ok(html.includes("disabled"));
  // The reason, not just the state: "filtered out at export" and "this
  // corpus has none" are different facts.
  assert.ok(html.includes("--origins emergent"));
});

test("a group box is named after the members still on the canvas", () => {
  /* Caught in a real browser, not here: with emergent unticked the
     boxes still read "topic-30 +29" -- led by a topic the filter had
     removed, and counting members the reader could not find. The cut
     itself is the stage's and is untouched; only the summary moves. */
  const cut = graph.cutTree(
    [{ id: "node-0", a: "digital twin", b: "machine learning", distance: 0.31 },
     { id: "node-1", a: "topic-7", b: "node-0", distance: 0.52 }],
    DATA.topics,
    0.6
  );
  const view = { cut: cut, collapsed: new Set([cut.groupOf["digital twin"]]) };
  const whole = graph.elementsFor(DATA, graph.labelsWithOrigins(DATA, ALL), [], view);
  assert.match(whole.find((e) => e.data.collapsed === 1).data.label, /machine learning \+2/);

  // With emergent off, topic-7 leaves the group: two members, not three.
  const kept = graph.labelsWithOrigins(DATA, new Set(["seed", "keyword"]));
  const box = graph.elementsFor(DATA, kept, [], view).find((e) => e.data.collapsed === 1);
  assert.equal(box.data.count, 2);
  assert.match(box.data.label, /machine learning \+1/);
});

test("the hierarchy panel drops a merge naming a hidden topic", () => {
  const visible = new Set(["digital twin"]);
  assert.equal(panel.hierarchyHtml(DATA.hierarchy, visible), "");
  const both = new Set(["digital twin", "machine learning"]);
  assert.ok(panel.hierarchyHtml(DATA.hierarchy, both).includes("digital twin"));
});

test("the hierarchy panel is unfiltered when no visible set is passed", () => {
  assert.ok(panel.hierarchyHtml(DATA.hierarchy).includes("machine learning"));
});

test("the disagreement grid lists no pair the canvas cannot show", () => {
  /* The partitions stay corpus-wide -- re-clustering a subset would
     answer a question nobody asked -- but a pair naming a hidden topic
     is a row about something the reader cannot see. */
  const families = require("../../assets/webapp/families.js");
  const visible = new Set(["digital twin"]);
  const grid = families.disagreement(DATA, 2.0, visible);
  const named = grid.semanticOnly.concat(grid.overlapOnly);
  named.forEach((pair) => {
    assert.ok(visible.has(pair.a) && visible.has(pair.b), pair.a + "/" + pair.b);
  });
  assert.equal(grid.filtered, true);
  // ...and an unfiltered grid says so, so the caption stays quiet.
  assert.equal(families.disagreement(DATA, 2.0).filtered, false);
});

test("the grid's caption separates the corpus's clusters from the canvas's pairs", () => {
  const html = panel.disagreementHtml({
    inflation: 2, stored: true, filtered: true,
    semanticOnly: [], overlapOnly: [], dropped: 0,
  });
  assert.match(html, /clusters are the corpus's/);
});

test("a path that leaves the filter says so instead of losing a hop", () => {
  /* The walk is the corpus's and every hop is still named -- hiding one
     would make the chain unexplainable -- but a topic named here and
     absent from the canvas must read as the route's doing. */
  const result = {
    family: "overlap",
    labels: ["digital twin", "topic-7", "machine learning"],
    hops: [
      { a: "digital twin", b: "topic-7", strength: 0.5, evidence: ["dt2022"], index: 0 },
      { a: "topic-7", b: "machine learning", strength: 0.4, evidence: ["ml2020"], index: 1 },
    ],
  };
  const visible = new Set(["digital twin", "machine learning"]);
  const html = panel.pathHtml(DATA, result, visible);
  assert.match(html, /leaves your origin filter/);
  assert.ok(html.includes("topic-7"));
  // No filter, no note.
  assert.ok(!panel.pathHtml(DATA, result).includes("leaves your origin filter"));
});
