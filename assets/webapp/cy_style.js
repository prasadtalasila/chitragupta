/* The cytoscape style sheet: pure data, no DOM and no event wiring, so
   it is its own file rather than inline in the `cytoscape({...})` call
   app.js makes. Order inside the array is itself part of the rule set
   -- a later selector wins a shared property against an earlier one on
   the same element -- so the ordering comments below travel with the
   array rather than living beside a cytoscape call that no longer
   explains them. */
"use strict";

(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.CHITRAGUPTA_APP = Object.assign(root.CHITRAGUPTA_APP || {}, api);
  }
})(typeof self !== "undefined" ? self : this, function () {
  var CY_STYLE = [
    { selector: "node", style: {
      "background-color": "data(color)",
      "width": "data(size)",
      "height": "data(size)",
      "label": "data(label)",
      "font-size": 12,
      "color": "#1c2733",
      "text-valign": "bottom",
      "text-margin-y": 5,
      "text-wrap": "wrap",
      "text-max-width": 140,
      "border-width": 0,
    } },
    { selector: "node[picked = 1]", style: {
      "border-width": 4,
      "border-color": "#1c2733",
    } },
    /* Width is strength; opacity is *surprise*, the hypergeometric
       that let the edge exist at all and that nothing has ever shown.
       Only on this family -- semantic edges never ran that test and
       are not given a borrowed value. */
    { selector: "edge[family = 'overlap']", style: {
      "width": "data(width)",
      "line-color": "#5c6bc0",
      "curve-style": "bezier",
      "opacity": "data(surprise)",
    } },
    { selector: "edge[family = 'semantic']", style: {
      "width": "data(width)",
      "line-color": "#8e24aa",
      "line-style": "dashed",
      "curve-style": "bezier",
      "opacity": 0.65,
    } },
    { selector: ".highlighted", style: { "opacity": 1, "line-color": "#e53935" } },
    // A group is grey on purpose: colour means provenance on this
    // canvas, and a group has no provenance of its own -- it is the
    // reader's cut of the merge tree, not something the corpus says.
    { selector: "node[isGroup = 1]", style: {
      "background-color": "#eef1f5",
      "background-opacity": 0.6,
      "border-width": 1,
      "border-style": "dashed",
      "border-color": "#8a97a8",
      "text-valign": "top",
      "text-margin-y": -4,
      "font-size": 11,
      "color": "#5b6879",
      "padding": 12,
    } },
    // The label goes inside a collapsed group rather than under it:
    // eight meta-nodes carry eight long labels, and underneath they
    // collide with each other and with the edges between them.
    { selector: "node[collapsed = 1]", style: {
      "background-color": "#8a97a8",
      "shape": "round-rectangle",
      "border-width": 2,
      "border-color": "#5b6879",
      "font-size": 11,
      "color": "#fff",
      "text-valign": "center",
      "text-margin-y": 0,
      "text-max-width": "data(size)",
    } },
    { selector: "edge[bundled = 1]", style: { "line-style": "solid", "opacity": 0.85 } },
    { selector: "edge[bundled = 1][family = 'semantic']", style: { "line-style": "dashed" } },
    /* Moved ahead of its usual place beside the other paper-related
       rules below: `edge.focus-near` sets the same two properties
       (`width`, `opacity`) and has to win over this family styling
       when a paper's membership line is in a latched neighbourhood --
       `elementsFor` never marks a member edge `dim` (paperElements is
       concatenated after the dimming pass), so member and dim never
       compete for the same element and reordering the two is safe. */
    { selector: "edge[family = 'member']", style: {
      "width": 1,
      "line-color": "#90a4ae",
      "line-style": "dotted",
      "curve-style": "haystack",
      "opacity": 0.7,
    } },
    /* Node focus (click-to-latch, hover-to-preview): an outline
       rather than a border, so it never fights `node[picked = 1]`'s
       4px border or `.on-path`'s for the same channel. Teal is a
       fresh hue nothing else on this canvas uses. Placed after the
       member rule above (so a latched paper's membership lines still
       get the highlight) and before the dim rules below (so a dim
       node inside a latched neighbourhood still reads as context,
       not as newly emphasised) -- dim must keep winning. */
    { selector: "node.focused", style: {
      "outline-width": 3, "outline-color": "#00897b", "outline-offset": 2,
    } },
    { selector: "node.focus-near", style: {
      "outline-width": 2, "outline-color": "#4db6ac", "outline-offset": 1,
    } },
    // Undoes a family's partial opacity (surprise, or the semantic
    // 0.65) and adds a flat width bump on top of `data(width)`'s
    // strength encoding -- a function, not a fixed number, so a
    // strong edge still reads as stronger than a weak one among the
    // ones highlighted. Family colour is kept throughout: only
    // opacity and width change, so the two families stay legible as
    // a *set*, not just as not-faded.
    { selector: "edge.focus-near", style: {
      "opacity": 1,
      "width": function (ele) { return (ele.data("width") || 1) + 1.5; },
    } },
    /* Focus plus context. The context is pushed back rather than
       deleted, and `events: no` keeps it from taking clicks or
       stealing hover -- a dimmed node that still answers the mouse
       reads as a bug, not as background. */
    { selector: "node[dim = 1]", style: {
      "opacity": 0.12, "text-opacity": 0, "events": "no",
    } },
    { selector: "edge[dim = 1]", style: { "opacity": 0.06, "events": "no" } },
    /* `.faded` is the third channel, separate from `dim` (the chips')
       and from `.focused`/`.focus-near` (the click/hover target and
       its neighbourhood): it is everything outside whatever is
       currently focused, whether that focus is a hover preview or a
       click latch. */
    { selector: ".faded", style: { "opacity": 0.15, "text-opacity": 0.15 } },
    /* A paper is a different *kind* of thing, so it gets the one
       channel nothing else uses: shape. Its line to a topic is
       membership -- neither of the two families -- and is drawn thin
       and grey so it cannot be mistaken for either. */
    { selector: "node[kind = 'paper']", style: {
      "shape": "diamond",
      "background-color": "#455a64",
      "width": "mapData(score, 0, 1, 16, 34)",
      "height": "mapData(score, 0, 1, 16, 34)",
      "label": "data(label)",
      "font-size": 9,
      "color": "#455a64",
    } },
    { selector: "node[kind = 'paper'][drawn > 1]", style: {
      "background-color": "#c2185b",
      "border-width": 2,
      "border-color": "#880e4f",
    } },
    { selector: ".on-path", style: {
      "line-color": "#e53935", "target-arrow-color": "#e53935",
      "border-width": 3, "border-color": "#e53935",
      "opacity": 1, "z-index": 10,
    } },
  ];

  return { CY_STYLE: CY_STYLE };
});
