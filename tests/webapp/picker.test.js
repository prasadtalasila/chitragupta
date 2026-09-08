/* The header's two multi-select pickers: the edge families, and the
   origin classes the checkbox row used to carry.

   One widget, two axes, because "all or some of these" is the same
   question either way -- and because a row of four boxes makes the
   reader scan four states to learn one fact, where a summary says it
   before anything is opened.

   The properties under test are the ones a reader would notice if they
   broke: a summary that disagrees with the ticks, a member whose
   legend key is missing so the row cannot be matched to the canvas, a
   family this corpus has no edges for looking merely unticked, and the
   last member of either axis going out to leave a canvas that reads as
   an empty corpus. */
"use strict";

const test = require("node:test");
const assert = require("node:assert");

const graph = require("../../assets/webapp/graph.js");
const panel = require("../../assets/webapp/panel.js");
const { DATA } = require("./fixture.js");

const BOTH = new Set(graph.FAMILY_CLASSES);

test("the two families are the app's vocabulary, in the legend's order", () => {
  assert.deepEqual(graph.FAMILY_CLASSES, ["overlap", "semantic"]);
  graph.FAMILY_CLASSES.forEach((family) => {
    // A name and a legend key, or the picker row cannot be matched to
    // anything the reader can see on the canvas.
    assert.ok(graph.FAMILY_LABELS[family], family);
    assert.ok(graph.FAMILY_KEYS[family], family);
  });
});

test("the family names are the legend's words, not the payload's", () => {
  // `overlap` and `semantic` are field names in data.js. The reader was
  // never shown them and is not shown them here.
  assert.equal(graph.FAMILY_LABELS.overlap, "shares papers");
  assert.equal(graph.FAMILY_LABELS.semantic, "semantically near");
});

test("the family controls report each family, its edges, and whether it is on", () => {
  const controls = graph.familyControls(DATA, new Set(["overlap"]));
  assert.deepEqual(controls.map((c) => c.family), graph.FAMILY_CLASSES);
  const overlap = controls.find((c) => c.family === "overlap");
  assert.equal(overlap.checked, true);
  assert.equal(overlap.count, 1);
  assert.equal(overlap.shipped, true);
  const semantic = controls.find((c) => c.family === "semantic");
  assert.equal(semantic.checked, false);
  assert.equal(semantic.count, 1);
});

test("a family this corpus has no edges for says so rather than looking unticked", () => {
  // "you switched it off" and "there is nothing to switch on" are
  // different facts, the same distinction the origin row draws for a
  // class an export left out.
  const overlapOnly = { ...DATA, edges_semantic: [] };
  const controls = graph.familyControls(overlapOnly, BOTH);
  assert.equal(controls.find((c) => c.family === "semantic").shipped, false);
  assert.equal(controls.find((c) => c.family === "overlap").shipped, true);
});

test("a payload with no edges at all offers both families", () => {
  // Nothing to filter, so nothing is disabled: the alternative is a
  // picker in which every row is dead and none of them says why.
  const bare = { topics: [], edges_overlap: [], edges_semantic: [] };
  graph.familyControls(bare, BOTH).forEach((c) => {
    assert.equal(c.shipped, true, c.family);
    assert.equal(c.count, 0, c.family);
  });
});

test("the app opens over whichever families the corpus actually has", () => {
  assert.deepEqual(graph.shippedFamilies(DATA), ["overlap", "semantic"]);
  const overlapOnly = { ...DATA, edges_semantic: [] };
  assert.deepEqual(graph.shippedFamilies(overlapOnly), ["overlap"]);
  const bare = { edges_overlap: [], edges_semantic: [] };
  assert.deepEqual(graph.shippedFamilies(bare), graph.FAMILY_CLASSES);
});

// ---------- the selection, either axis ----------

test("toggling a member off returns the smaller selection, and does not mutate", () => {
  const next = graph.nextSelection(BOTH, "semantic", false);
  assert.deepEqual([...next], ["overlap"]);
  assert.equal(BOTH.size, 2);
});

test("toggling the last member off is refused, on either axis", () => {
  /* An empty canvas reads as an empty corpus. With no family on there
     is no graph left at all -- not even the union the ego rings walk
     today -- so the tick goes back and the caller restores the box. */
  assert.equal(graph.nextSelection(new Set(["overlap"]), "overlap", false), null);
  assert.equal(graph.nextSelection(new Set(["seed"]), "seed", false), null);
});

// ---------- the widget ----------

test("the picker renders one row per member, with its state and its key", () => {
  const html = panel.pickerHtml({
    attr: "data-family",
    label: "Edges",
    allLabel: "both families",
    rows: graph.familyControls(DATA, new Set(["overlap"])).map((c) => ({
      value: c.family, name: graph.FAMILY_LABELS[c.family],
      edge: graph.FAMILY_KEYS[c.family], count: c.count,
      shipped: c.shipped, checked: c.checked,
    })),
  });
  assert.ok(html.includes('data-family="overlap"'));
  assert.ok(html.includes('data-family="semantic"'));
  assert.ok(html.includes("shares papers"));
  // The legend key, so a row can be matched to a line on the canvas.
  assert.ok(html.includes("edge-key solid"));
  assert.ok(html.includes("edge-key dashed"));
  // Exactly one row is ticked, and it is the one the caller said.
  assert.equal(html.split(" checked").length - 1, 1);
});

test("a member with nothing behind it is disabled and carries the reason", () => {
  const html = panel.pickerHtml({
    attr: "data-family",
    label: "Edges",
    allLabel: "both families",
    rows: [{ value: "semantic", name: "semantically near", edge: "dashed",
      count: 0, shipped: false, checked: false }],
  });
  assert.ok(html.includes("disabled"));
  assert.ok(html.includes("none in this corpus"));
});

test("the picker escapes a hostile member name", () => {
  // The origin axis's names are the app's own words, but the row goes
  // through the same renderer as anything else and the escaping is not
  // a property of the caller.
  const html = panel.pickerHtml({
    attr: "data-origin",
    label: "Nodes",
    allLabel: "all origins",
    rows: [{ value: '"><script>', name: '"><script>', color: "#000",
      count: 1, shipped: true, checked: true }],
  });
  assert.ok(!html.includes("<script>"));
  assert.ok(html.includes("&lt;script&gt;"));
});

test("the summary says what is on before anything is opened", () => {
  const all = [
    { value: "overlap", name: "shares papers", shipped: true, checked: true },
    { value: "semantic", name: "semantically near", shipped: true, checked: true },
  ];
  assert.equal(panel.pickerSummary(all, "both families"), "both families");
  const one = [all[0], { ...all[1], checked: false }];
  // A subset is named, and said to be a subset: "shares papers" alone
  // would read as a description of the graph rather than a filter.
  assert.equal(panel.pickerSummary(one, "both families"), "shares papers only");
});

test("the summary names whichever side is shorter", () => {
  // Four origin classes with one off: "all but emergent", not the three
  // that are on. The same fact, half the words.
  const rows = ["seed", "keyword", "corroborated", "emergent"].map((name) => ({
    value: name, name: name, shipped: true, checked: name !== "emergent",
  }));
  assert.equal(panel.pickerSummary(rows, "all 4 origins"), "all but emergent");
  const half = rows.map((row) => ({
    ...row, checked: row.name === "seed" || row.name === "keyword",
  }));
  assert.equal(panel.pickerSummary(half, "all 4 origins"), "seed, keyword only");
});

test("the summary ignores a member the corpus cannot offer", () => {
  // With no semantic edges anywhere, overlap alone is everything there
  // is -- so the summary must not call it a filtered subset.
  const rows = [
    { value: "overlap", name: "shares papers", shipped: true, checked: true },
    { value: "semantic", name: "semantically near", shipped: false, checked: false },
  ];
  assert.equal(panel.pickerSummary(rows, "both families"), "both families");
});

test("the origin row is now the same widget, and kept its export reason", () => {
  const shipped = { ...DATA, origins: ["emergent"] };
  const html = panel.originsHtml(graph.originControls(shipped, new Set(["emergent"])), shipped);
  assert.ok(html.includes("picker-summary"));
  assert.ok(html.includes('data-origin="emergent"'));
  assert.ok(html.includes("disabled"));
  // Unchanged from the checkbox row: the reason a class cannot come
  // back is the export's flag, and it is still named.
  assert.ok(html.includes("--origins emergent"));
});

test("the families row says which families are on, in one string", () => {
  const html = panel.familiesHtml(graph.familyControls(DATA, new Set(["overlap"])));
  assert.ok(html.includes('data-family="overlap"'));
  assert.ok(html.includes("shares papers only"));
});

// ---------- "everything" counts only what the reader can reach ----------

test("a filtered export does not claim four origins while showing one", () => {
  /* `--origins emergent` ships one class and disables the other three.
     Saying "all 4 origins" over three dead rows states a number the
     picker itself contradicts -- the same quiet misstatement the
     disabled rows exist to prevent. */
  const shipped = { ...DATA, origins: ["emergent"] };
  const controls = graph.originControls(shipped, new Set(["emergent"]));
  assert.equal(panel.originsSummary(controls, shipped), "emergent");
  const html = panel.originsHtml(controls, shipped);
  assert.ok(!html.includes("all 4 origins"));
});

test("an unfiltered export does say all four", () => {
  const controls = graph.originControls(DATA, new Set(graph.ORIGIN_CLASSES));
  assert.equal(panel.originsSummary(controls, DATA), "all 4 origins");
});

test("a corpus with one family's edges does not call it both", () => {
  const overlapOnly = { ...DATA, edges_semantic: [] };
  const controls = graph.familyControls(overlapOnly, new Set(["overlap"]));
  assert.equal(panel.familiesSummary(controls), "shares papers");
  assert.equal(
    panel.familiesSummary(graph.familyControls(DATA, new Set(graph.FAMILY_CLASSES))),
    "both families"
  );
});

test("the summary the wiring shows is the one the widget rendered", () => {
  // The label lived in two places once -- the renderer's and the
  // caller's copy -- and that is how they came to disagree.
  const shipped = { ...DATA, origins: ["seed", "corroborated"] };
  const controls = graph.originControls(shipped, new Set(["seed", "corroborated"]));
  const inHtml = panel.originsHtml(controls, shipped).match(/picker-state">([^<]*)/)[1];
  assert.equal(inHtml, panel.originsSummary(controls, shipped));
  assert.equal(inHtml, "all 2 origins");
});
