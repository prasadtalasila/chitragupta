/* assets/webapp/panel.js: the side panel's HTML, built as strings.

   Every function here interpolates semi-trusted data -- a topic label
   may have ridden in through a PDF's extracted keywords, and a title
   comes from the ledger -- so the escaping is not a detail of these
   tests, it is most of what they are for. The five-character escape
   (#636) is explicit rather than textContent-based because the output
   also lands inside double-quoted attributes, and a serialized text
   node never escapes a quote. */
"use strict";

const test = require("node:test");
const assert = require("node:assert");

const panel = require("../../assets/webapp/panel.js");
const { DATA } = require("./fixture.js");

const HOSTILE = DATA.topics[3];

test("all five HTML-significant characters are escaped", () => {
  assert.equal(
    panel.escapeHtml("<a href=\"x\" title='y'>&</a>"),
    "&lt;a href=&quot;x&quot; title=&#39;y&#39;&gt;&amp;&lt;/a&gt;"
  );
});

test("escaping is null-safe and stringifies", () => {
  assert.equal(panel.escapeHtml(null), "");
  assert.equal(panel.escapeHtml(undefined), "");
  assert.equal(panel.escapeHtml(0), "0");
});

test("a paper card carries the citekey verbatim and the ledger title", () => {
  const html = panel.paperCard(DATA.topics[0].members[0]);
  assert.match(html, /<code>dt2022<\/code>/);
  assert.match(html, /A digital twin/);
});

test("a paper with no title in the ledger says so rather than showing an empty line", () => {
  const html = panel.paperCard({ citekey: "nn2019", title: "", score: 0.2 });
  assert.match(html, /no title in ledger/);
});

test("the score bar is clamped to the 0-100 range", () => {
  assert.match(panel.paperCard({ citekey: "k", title: "t", score: 5 }), /width:100%/);
  assert.match(panel.paperCard({ citekey: "k", title: "t", score: -1 }), /width:0%/);
});

test("a hostile title cannot open a tag inside a paper card", () => {
  const html = panel.paperCard({ citekey: "x2017", title: "Odd <one>", score: 0.1 });
  assert.ok(!html.includes("<one>"));
  assert.match(html, /Odd &lt;one&gt;/);
});

test("linked rows name both edge families and explain each by naming papers", () => {
  const rows = panel.linkedRows(DATA, DATA.topics[1]);
  assert.match(rows, /shares 1 paper: dt2022/);
  assert.match(rows, /semantically near \(0\.61\), bridged by ml2020 and rv2018/);
});

test("a topic on no edge says it has no linked topics", () => {
  assert.match(panel.linkedRows(DATA, HOSTILE), /no linked topics/);
});

test("a hostile label cannot break out of the data-goto attribute", () => {
  const near = {
    topics: [HOSTILE, DATA.topics[0]],
    edges_overlap: [
      {
        a: HOSTILE.label,
        b: "digital twin",
        jaccard: 0.1,
        overlap_coeff: 0.2,
        p_value: 0.5,
        shared: ["x2017"],
      },
    ],
    edges_semantic: [],
  };
  const rows = panel.linkedRows(near, DATA.topics[0]);
  assert.ok(!rows.includes('<"hostile">'));
  assert.match(rows, /data-goto="__proto__ &lt;&quot;hostile&quot;&gt;"/);
});

test("a topic panel shows its origin, its terms and every paper", () => {
  const html = panel.topicHtml(DATA, DATA.topics[0]);
  assert.match(html, /seed topic/);
  assert.match(html, /twin · simulation/);
  assert.match(html, /Papers \(2\)/);
  assert.match(html, /<code>sim2021<\/code>/);
});

test("a topic with no terms shows no empty terms line", () => {
  const bare = { label: "b", origin: "seed", terms: [], members: [] };
  assert.ok(!panel.topicHtml(DATA, bare).includes('class="terms"'));
});

test("an unknown origin falls back rather than rendering undefined", () => {
  const odd = { label: "o", origin: "not-an-origin", terms: [], members: [] };
  const html = panel.topicHtml(DATA, odd);
  assert.ok(!html.includes("undefined"));
  assert.match(html, /not-an-origin/);
});

test("an overlap edge panel reports the shared papers, the jaccard and the p-value", () => {
  const html = panel.edgeHtml(DATA, "overlap", 0);
  assert.match(html, /share 1 paper/);
  assert.match(html, /jaccard 0\.25/);
  assert.match(html, /p = 4\.0e-3/);
  assert.match(html, /Shared papers/);
  assert.match(html, /<code>dt2022<\/code>/);
});

test("a semantic edge panel reports the similarity and the bridging pair", () => {
  const html = panel.edgeHtml(DATA, "semantic", 0);
  assert.match(html, /similarity 0\.61/);
  assert.match(html, /Bridge papers/);
  assert.match(html, /<code>ml2020<\/code>/);
  assert.match(html, /<code>rv2018<\/code>/);
});

test("a citekey with no member record still renders as a citekey", () => {
  const orphan = {
    topics: [],
    edges_overlap: [
      {
        a: "a",
        b: "b",
        jaccard: 0.1,
        overlap_coeff: 0.2,
        p_value: 0.5,
        shared: ["ghost2001"],
      },
    ],
    edges_semantic: [],
  };
  assert.match(panel.edgeHtml(orphan, "overlap", 0), /<code>ghost2001<\/code>/);
});

test("the suggestion list marks the active row and escapes both label and reason", () => {
  const html = panel.suggestionsHtml(
    [
      { label: "digital twin", why: "seed topic" },
      { label: '__proto__ <"hostile">', why: "term: hostile" },
    ],
    1
  );
  assert.match(html, /<li data-label="digital twin">/);
  assert.match(html, /class="active"/);
  assert.ok(!html.includes('<"hostile">'));
});

test("nothing is active when the index is -1", () => {
  const html = panel.suggestionsHtml([{ label: "a", why: "b" }], -1);
  assert.ok(!html.includes("active"));
});

test("the hierarchy lists every merge with its distance", () => {
  const html = panel.hierarchyHtml(DATA.hierarchy);
  assert.match(html, /digital twin \+ machine learning \(distance 0\.31\)/);
});
