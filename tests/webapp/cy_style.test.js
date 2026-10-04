/* assets/webapp/cy_style.js: the cytoscape style sheet.

   Pure data, so most of it is only checkable by looking at the canvas.
   The one piece of behaviour in it is the focus-near edge width, which
   is a function of the edge's own strength rather than a fixed number
   -- the point being that a strong edge still reads as stronger than a
   weak one among the highlighted ones. */
"use strict";

const test = require("node:test");
const assert = require("node:assert");

const { CY_STYLE } = require("../../assets/webapp/cy_style.js");

function edgeWith(width) {
  return { data: (key) => (key === "width" ? width : undefined) };
}

const focusNearWidth = CY_STYLE.find((rule) => rule.selector === "edge.focus-near").style.width;

test("a highlighted edge keeps its strength ordering under the width bump", () => {
  assert.equal(focusNearWidth(edgeWith(4)), 5.5);
  assert.ok(focusNearWidth(edgeWith(4)) > focusNearWidth(edgeWith(2)));
});

test("an edge with no width of its own is bumped from 1", () => {
  assert.equal(focusNearWidth(edgeWith(undefined)), 2.5);
});

test("every rule is a selector string and a style object", () => {
  assert.ok(CY_STYLE.length > 0);
  for (const rule of CY_STYLE) {
    assert.equal(typeof rule.selector, "string");
    assert.equal(typeof rule.style, "object");
  }
});

test("a dimmed membership line is drawn dim, not at the member rule's opacity", () => {
  /* Since #981 a membership line leaving a dimmed topic carries `dim`,
     so it matches both rules and the later one wins. */
  const at = (selector) => CY_STYLE.findIndex((rule) => rule.selector === selector);
  assert.ok(at("edge[family = 'member']") >= 0);
  assert.ok(at("edge[dim = 1]") > at("edge[family = 'member']"));
});
