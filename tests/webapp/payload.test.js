/* assets/webapp/payload.js: what the app needs of data.js, and the
   edge-family accessors every module reads it through.

   A missing, truncated or hand-edited data.js used to throw on the
   app's first dereference, before any handler was wired, and the reader
   was left with help text describing controls that did nothing (#855).
   These tests pin the check the app now runs first, one deleted key at
   a time, against the fixture every other webapp test reads. */
"use strict";

const test = require("node:test");
const assert = require("node:assert");

const payload = require("../../assets/webapp/payload.js");
const { DATA } = require("./fixture.js");

function without(key) {
  const copy = Object.assign({}, DATA);
  delete copy[key];
  return copy;
}

test("the fixture payload has no problems", () => {
  assert.deepEqual(payload.payloadProblems(DATA), []);
});

for (const key of ["topics", "edges_overlap", "edges_semantic", "hierarchy", "n_docs"]) {
  test("a payload without " + key + " names it as missing", () => {
    assert.deepEqual(payload.payloadProblems(without(key)), [key + " (missing)"]);
  });
}

test("a key of the wrong type is named as mistyped, not missing", () => {
  const bad = Object.assign({}, DATA, { topics: {}, n_docs: "4" });
  assert.deepEqual(payload.payloadProblems(bad), [
    "topics (not a list)", "n_docs (not a number)",
  ]);
});

// No data.js at all, or one that assigned something other than an
// object: every key is missing, and the check itself must not throw.
test("no payload at all names every key", () => {
  for (const nothing of [undefined, null, 42]) {
    assert.deepEqual(payload.payloadProblems(nothing), payload.REQUIRED_KEYS.map(function (key) {
      return key + " (missing)";
    }));
  }
});

test("each family reads its own edge list, weight and evidence", () => {
  const overlap = payload.edgesOf(DATA, "overlap");
  const semantic = payload.edgesOf(DATA, "semantic");
  assert.equal(overlap, DATA.edges_overlap);
  assert.equal(semantic, DATA.edges_semantic);
  assert.equal(payload.weightOf("overlap", overlap[0]), overlap[0].overlap_coeff);
  assert.equal(payload.weightOf("semantic", semantic[0]), semantic[0].similarity);
  assert.equal(payload.evidenceOf("overlap", overlap[0]), overlap[0].shared);
  assert.equal(payload.evidenceOf("semantic", semantic[0]), semantic[0].bridge);
});

/* One implementation each (#860). ego.js, families.js and graph.js
   each carried their own copy of the family-to-edge-list choice, one
   with a `|| []` the others lacked, and panel.js hand-built the goto
   link and the "N paper(s)" plural at every site that needed one. A
   copy added back would pass every behavioural test, so this reads the
   shipped sources for the three shapes and expects each exactly once. */
test("the edge-list choice, the goto link and the plural are each written once", () => {
  const fs = require("node:fs");
  const path = require("node:path");
  const dir = path.join(__dirname, "..", "..", "assets", "webapp");
  const sources = fs.readdirSync(dir).filter((name) => name.endsWith(".js"))
    .map((name) => fs.readFileSync(path.join(dir, name), "utf8")).join("\n");
  const count = (needle) => sources.split(needle).length - 1;
  assert.equal(count("data.edges_overlap : data.edges_semantic"), 1);
  assert.equal(count('data-goto="'), 1);
  assert.equal(count('=== 1 ? "" : "s"'), 1);
});
