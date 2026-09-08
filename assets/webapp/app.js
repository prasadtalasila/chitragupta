/* The topic-graph app: pure renderer of window.CHITRAGUPTA_TOPICS,
   which data.js (written by `corpus discover --app`) assigns. It
   computes no edge and no membership -- everything drawn here was
   derived once by `chitragupta enrich` -- so the app cannot disagree
   with the terminal views. Colour vocabulary mirrors style.css.

   What is left in this file is the wiring: the cytoscape instance, the
   DOM events, and the selection state they mutate. The logic they call
   lives in graph.js (payload -> what is visible, what cytoscape is
   handed) and panel.js (data -> HTML), which index.html loads first;
   both are testable without a browser and are tested under
   tests/webapp/. */
"use strict";

(function () {
  var DATA = window.CHITRAGUPTA_TOPICS;
  var app = window.CHITRAGUPTA_APP;

  var topicsByLabel = app.byLabel(DATA.topics);
  var selected = []; // chip order preserved

  /* Grouping state. The app opens at a cut of the stored merge tree
     yielding roughly eight groups, all collapsed, because 131 topics
     drawn loose is a hairball and a reader who has to find a control
     first has already met it. `cut` is null when the reader slides the
     resolution all the way down, which is the pre-grouping view. */
  var OPENING_GROUPS = 8;
  var cut = null;
  var collapsed = new Set();
  var groupsById = Object.create(null);

  /* Ego state. With topics pinned the context stays on the canvas,
     dimmed, rather than being deleted -- removing it costs the reader
     their sense of where they are in a corpus this size. `maxHops`
     bounds the ring view: one hop answers "what is next to this", two
     answers "what would a chapter around this have to cover". */
  /* The origin filter. `activeOrigins` opens as whatever the export
     shipped, so the app's first frame is exactly what the same
     `--origins` run showed in the terminal; ALL_LABELS is derived from
     it and re-derived whenever a picker row moves. */
  var activeOrigins = new Set(app.shippedOrigins(DATA));
  var ALL_LABELS = app.labelsWithOrigins(DATA, activeOrigins);

  /* The edge-family filter. This was a module constant no element read,
     and the cost was not a missing control: `hopsFrom` walks whatever
     adjacency it is handed, so the ego rings measured distance over the
     union of both families and a topic one shared paper plus one cosine
     hop away sat on ring 2 beside a topic two shared papers out. The
     reader could not ask "how far is this over shared papers" -- a
     question `discover --path --family` has always answered in the
     terminal.

     A Set here and a list at the call sites, because `familiesOf` in
     graph.js and `hopsFrom` in ego.js both want an ordered list and
     order is the legend's. */
  var activeFamilies = new Set(app.shippedFamilies(DATA));

  var context = "dim";
  var maxHops = 2;
  /* Papers on the canvas, opt-in and capped: a paper in three topics is
     visibly a bridge, and 131 topics fully expanded is several hundred
     nodes and thousands of lines. */
  var expanded = new Set();
  /* Sticky node focus: the id latched by a click, or null. A
     hover previews the same paint transiently and reverts to this on
     `mouseout`; `redraw()` wipes every class each call (it removes and
     re-adds all elements), so it repaints this after every rebuild, or
     releases it if the id no longer exists. */
  var latched = null;
  var hoverTimer = null;

  function families() {
    return app.FAMILY_CLASSES.filter(function (family) {
      return activeFamilies.has(family);
    });
  }

  // ---------- cytoscape ----------

  var cy = cytoscape({
    container: document.getElementById("cy"),
    elements: [],
    /* Only worth having once papers can join the graph: a few hundred
       nodes and thousands of lines. Costless before that. */
    hideEdgesOnViewport: true,
    textureOnViewport: true,
    pixelRatio: 1,
    style: [
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
    ],
  });

  function view() {
    return {
      cut: cut, collapsed: collapsed, context: context,
      all: ALL_LABELS, expanded: expanded, families: families(),
    };
  }

  /* One layout at a time. Two redraws in the same turn -- removing two
     chips at once does exactly that -- leave the first layout's
     viewport tween running after its elements are gone, and it lands on
     top of the second layout's fit: the canvas ends up framed for a
     graph that no longer exists. */
  var running = null;

  function run(options) {
    if (running) { running.stop(); }
    running = cy.layout(options);
    running.run();
  }

  function redraw() {
    /* The tooltip belongs to an element that is about to be removed. A
       redraw with the pointer over an edge -- expanding a group, moving
       the slider -- takes that edge away without a `mouseout`, and the
       tooltip stays on screen describing something no longer drawn. */
    hideTip();
    // One notion of "near the selection", used for both what is
    // emphasised and where it is drawn: the hop control moves them
    // together, so nothing is ever placed on a ring and dimmed to
    // background at the same time.
    var hops = selected.length ? app.hopsFrom(DATA, selected, families()) : null;
    // The rings are walked over the whole payload, so a neighbour can be
    // a topic the origin filter has taken off the canvas.
    var visible = hops
      ? app.restrictTo(app.withinHops(hops, maxHops), ALL_LABELS)
      : ALL_LABELS;
    var elements = app.elementsFor(DATA, visible, selected, view());
    cy.batch(function () {
      cy.elements().remove();
      cy.add(elements);
    });
    // Every redraw removes and re-adds every element, which drops any
    // class along with it -- the latch has to be repainted after each
    // one, or released if whatever it named is no longer on the canvas
    // (an origin filter, a group collapsing over it, an ego view that
    // no longer reaches it).
    paintLatchOrClear();
    if (hops) {
      // Rings by hop distance from what is pinned: deterministic, and
      // an extension of the "a circle is legible" argument rather than
      // a contradiction of it. elementsFor has already suspended the
      // cut, so there are no boxes to lay out here.
      var at = app.ringPositions(DATA, selected, hops, maxHops, families());
      var outside = app.contextRing(
        cy.nodes().map(function (n) { return n.id(); }), hops, maxHops
      );
      run({
        name: "preset",
        positions: function (n) { return at[n.id()] || outside[n.id()]; },
        // Object constancy: a node that teleports when the selection
        // changes makes the reader re-parse the whole picture.
        animate: true, animationDuration: 350,
        fit: true, padding: 40,
      });
      return;
    }
    if (cut) {
      // Groups round one circle, each group's topics round a smaller
      // one inside it. Deterministic, and cose is bad at compounds --
      // graph.js's own comment has the reasoning.
      var grouped = app.positionsFor(elements);
      // `fit` inside the layout, not a `cy.fit()` after `.run()`: with
      // `animate` on, run() returns before the nodes have moved, and
      // fitting there frames the positions they are leaving.
      run({
        name: "preset", positions: function (n) { return grouped[n.id()]; },
        animate: true, animationDuration: 350, fit: true, padding: 40,
      });
      return;
    }
    // Ungrouped: a deterministic circle first, then cose refines from
    // it without re-randomising -- the same graph always lands in the
    // same place.
    run({ name: "circle" });
    if (cy.nodes().length > 2) {
      run({
        name: "cose", randomize: false, animate: false, padding: 40,
        stop: function () { cy.fit(undefined, 40); },
      });
    } else {
      cy.fit(undefined, 40);
    }
  }

  // ---------- node focus: click-to-latch, hover-to-preview ----------

  /* One paint, shared by hover and latch: everything outside the
     closed neighbourhood fades, the neighbourhood itself is actively
     highlighted rather than merely left alone, and the centre is
     marked apart from its neighbours. A no-op if `id` is not on the
     canvas -- the caller (redraw's repaint, a stale hover) decides
     whether that means releasing the latch.

     `closedNeighborhood()` is edge-based only -- an expanded group is
     a compound *parent* with no edges of its own, so without also
     pulling in `ancestors()`/`descendants()` a latched group box faded
     its own members, and a latched member faded the box around it. */
  function paintFocus(id) {
    var center = cy.$id(id);
    if (!center.length) { return; }
    var near = center.closedNeighborhood()
      .union(center.ancestors())
      .union(center.descendants());
    cy.batch(function () {
      cy.elements().removeClass("focused focus-near faded");
      cy.elements().not(near).addClass("faded");
      near.not(center).addClass("focus-near");
      center.addClass("focused");
    });
  }

  function clearFocus() {
    cy.batch(function () { cy.elements().removeClass("focused focus-near faded"); });
  }

  // What every path back to "no transient hover" repaints: the latch,
  // if it is still on the canvas, otherwise nothing -- and releasing it
  // cleanly if it just fell off (an origin filter, a collapsed group).
  function paintLatchOrClear() {
    if (latched && cy.$id(latched).length) {
      paintFocus(latched);
    } else if (latched) {
      releaseLatch();
    } else {
      clearFocus();
    }
  }

  function releaseLatch() {
    if (hoverTimer) { window.clearTimeout(hoverTimer); hoverTimer = null; }
    latched = null;
    clearFocus();
  }

  // Click toggles: the same node releases, a different node moves the
  // latch, and the decision itself is a pure function (tests/webapp/
  // graph.test.js) so the toggle/move/release cases don't depend on a
  // browser to check.
  function setLatch(id) {
    if (hoverTimer) { window.clearTimeout(hoverTimer); hoverTimer = null; }
    latched = app.nextLatch(latched, id);
    paintLatchOrClear();
  }

  // ---------- side panel ----------

  var detail = document.getElementById("detail");
  var hint = document.getElementById("hint");
  /* The hint is the standing help text, and it is also where a
     transient message goes -- so the original has to be kept and put
     back. Without this, asking for one expansion too many replaced the
     help paragraph permanently, and nothing ever restored it. */
  var HELP = hint.textContent;

  /* Whether the disagreement grid is what the panel currently shows.
     Every other panel writer goes through clearHint first, so resetting
     here is what keeps the inflation slider from re-clustering into a
     panel the reader has since pointed elsewhere. */
  var disagreementShown = false;

  /* Which edge family owns what the panel is currently showing, if one
     does: a path over shared papers, or one edge's own card. Hiding the
     control that produced it does not unsay it -- switch that family
     off with its path on screen and the panel goes on describing hops
     over edges no longer drawn -- so the family is remembered and the
     panel is put back to the help text when it goes.

     Cleared here because every panel writer goes through clearHint
     first, the same mechanism `disagreementShown` relies on. */
  var panelFamily = null;

  function clearHint() {
    hint.hidden = true;
    hint.textContent = HELP;
    disagreementShown = false;
    panelFamily = null;
  }

  /* Back to the standing help text, with nothing selected in the panel:
     the state the app opens in, and where a panel whose subject has
     just left the canvas has to return to. */
  function showHelp() {
    detail.innerHTML = "";
    hint.textContent = HELP;
    hint.hidden = false;
    disagreementShown = false;
    panelFamily = null;
  }

  function say(message) {
    hint.textContent = message;
    hint.hidden = false;
  }

  function showTopic(label) {
    var topic = topicsByLabel[label];
    if (!topic) { return; }
    clearHint();
    detail.innerHTML = app.topicHtml(DATA, topic) + egoSection(label);
  }

  /* The brokerage reading, under the papers rather than instead of
     them: "is this topic a theme or a bridge" is the survey-scoping
     question, and it is answered per edge family because a topic that
     brokers over shared papers but not over vocabulary is a different
     animal from one that does the reverse. */
  function egoSection(label) {
    var topic = topicsByLabel[label];
    return app.egoHtml(label, {
      overlap: app.statsFor(DATA, topic, "overlap"),
      semantic: app.statsFor(DATA, topic, "semantic"),
    });
  }

  function showEdge(family, index) {
    clearHint();
    detail.innerHTML = app.edgeHtml(DATA, family, index);
    panelFamily = family;
  }

  function showGroup(id) {
    if (!groupsById[id]) { return; }
    clearHint();
    detail.innerHTML = app.groupHtml(groupsById[id]);
  }

  function showPaper(citekey) {
    var html = citekey && app.paperHtml(DATA, citekey);
    if (!html) { return; }
    clearHint();
    detail.innerHTML = html;
  }

  function showBundle(pairs) {
    clearHint();
    detail.innerHTML = app.bundleHtml(DATA, pairs);
    /* A bundle is keyed by family as well as by endpoints, so every
       pair in one shares a family and the card belongs to it -- but
       `bundleHtml` counts the two apart rather than assuming that, and
       this asks rather than assuming too. */
    var one = pairs.every(function (pair) { return pair.family === pairs[0].family; });
    panelFamily = one && pairs.length ? pairs[0].family : null;
  }

  /* Two pinned topics with no edge between them: the reader gets the
     gate's own reasoning rather than an empty canvas between two chips.
     Exactly two, because the sentence is about a pair -- with three
     pinned there are three pairs and no obvious one to answer. */
  function showPair(a, b) {
    var verdict = app.explain(DATA, a, b);
    if (!verdict || verdict.drawn) { return false; }
    clearHint();
    detail.innerHTML = app.absenceHtml(a, b, verdict);
    return true;
  }

  // A DOM tooltip rather than a vendored positioning library: the
  // bridge pair is the fastest answer to "why is this edge here", and
  // it should not cost a click.
  var tip = document.getElementById("tip");

  function showTip(event, text) {
    // Position first, then reveal: showing it before placing it leaves a
    // tooltip stuck at the last position if anything about the event is
    // not what was expected.
    tip.style.left = event.renderedPosition.x + 14 + "px";
    tip.style.top = event.renderedPosition.y + 14 + "px";
    tip.textContent = text;
    tip.hidden = false;
  }

  function hideTip() {
    tip.hidden = true;
  }

  cy.on("mouseover", "edge", function (event) {
    var edge = event.target;
    if (edge.data("bundled")) {
      showTip(event, edge.data("count") + " links bundled — click to see them");
      return;
    }
    if (edge.data("family") === "semantic") {
      var e = DATA.edges_semantic[edge.data("index")];
      showTip(event, "bridged by " + e.bridge.join(" and ") +
        " (similarity " + e.similarity.toFixed(2) + ")");
      return;
    }
    var overlap = DATA.edges_overlap[edge.data("index")];
    showTip(event, "shares " + overlap.shared.length + " paper" +
      (overlap.shared.length === 1 ? "" : "s") + ": " + overlap.shared.join(", "));
  });
  cy.on("mouseout", "edge", hideTip);

  cy.on("tap", "node", function (event) {
    var node = event.target;
    if (node.data("kind") === "paper") {
      showPaper(app.citekeyOf(DATA, node.id()));
    } else if (node.data("isGroup") || node.data("collapsed")) {
      showGroup(node.id());
    } else {
      showTopic(node.id());
    }
    setLatch(node.id());
  });

  // A tap that lands on neither a node nor an edge is the canvas
  // background: `event.target` is the core itself only then, and it is
  // the release gesture the request names alongside Esc and re-tapping
  // the same node.
  cy.on("tap", function (event) {
    if (event.target === cy) { releaseLatch(); }
  });

  // Double-click a topic to put its papers on the canvas, and again to
  // take them off. The same gesture that opens a group, on the other
  // kind of node.
  cy.on("dbltap", "node", function (event) {
    var node = event.target;
    if (node.data("isGroup") || node.data("collapsed") || node.data("kind") === "paper") {
      return;
    }
    if (expanded.has(node.id())) {
      expanded.delete(node.id());
    } else if (expanded.size >= app.EXPANSION_CAP) {
      // Say what happened rather than quietly drawing nothing.
      say("At most " + app.EXPANSION_CAP + " topics can show their papers at " +
        "once — double-click one of the open ones to close it.");
      return;
    } else {
      expanded.add(node.id());
    }
    redraw();
    showTopic(node.id());
  });

  /* Hovering a node lights its own neighbourhood and pushes the rest
     back -- the one interaction people expect from a graph, and the
     app had none of it. Debounced: unbatched per mouse-move is costless
     at 131 topics but not once paper diamonds are on the canvas. A
     latch survives the preview -- `mouseout` reverts to it rather than
     to nothing. */
  cy.on("mouseover", "node", function (event) {
    var id = event.target.id();
    if (hoverTimer) { window.clearTimeout(hoverTimer); }
    hoverTimer = window.setTimeout(function () {
      hoverTimer = null;
      paintFocus(id);
    }, 60);
  });
  cy.on("mouseout", "node", function () {
    if (hoverTimer) { window.clearTimeout(hoverTimer); hoverTimer = null; }
    paintLatchOrClear();
  });
  cy.on("tap", "edge", function (event) {
    var edge = event.target;
    if (edge.data("bundled")) {
      showBundle(edge.data("pairs"));
    } else {
      showEdge(edge.data("family"), edge.data("index"));
    }
  });

  // Double-click is the expand/collapse gesture: on a meta-node it
  // opens that group in place, on a group's box it closes it again,
  // and the rest of the canvas keeps whatever state it had.
  cy.on("dbltap", "node", function (event) {
    var node = event.target;
    if (!node.data("isGroup") && !node.data("collapsed")) { return; }
    if (collapsed.has(node.id())) {
      collapsed.delete(node.id());
    } else {
      collapsed.add(node.id());
    }
    redraw();
  });

  // The panel's own topic links are the accessible route to a node's
  // neighbourhood -- `tabindex` (panel.js) makes them reachable, and a
  // click and an Enter/Space both count as activating one.
  function activatePanelLink(target) {
    var goto_ = target.closest("a[data-goto]");
    if (goto_) {
      var label = goto_.getAttribute("data-goto");
      showTopic(label);
      setLatch(label);
      return true;
    }
    var edge = target.closest("a[data-edge]");
    if (edge) {
      var parts = edge.getAttribute("data-edge").split(":");
      showEdge(parts[0], Number(parts[1]));
      return true;
    }
    return false;
  }

  detail.addEventListener("click", function (event) {
    activatePanelLink(event.target);
  });
  detail.addEventListener("keydown", function (event) {
    if (event.key !== "Enter" && event.key !== " ") { return; }
    if (activatePanelLink(event.target)) { event.preventDefault(); }
  });

  // ---------- resolution: cutting the stored merge tree ----------

  /* The slider walks the merge distances themselves rather than a
     continuous range: every position is a cut that actually exists in
     the stored tree, so dragging one step always changes the picture,
     and position 0 is "no merges applied", i.e. the ungrouped graph. */
  var cutControl = document.getElementById("cut");
  var cutReadout = document.getElementById("cut-readout");
  var collapseAll = document.getElementById("collapse-all");
  var expandAll = document.getElementById("expand-all");
  var distances = DATA.hierarchy
    .map(function (merge) { return merge.distance; })
    .sort(function (x, y) { return x - y; });

  function applyCut(step, keepCollapsed) {
    cut = step > 0 ? app.cutTree(DATA.hierarchy, DATA.topics, distances[step - 1]) : null;
    groupsById = Object.create(null);
    var groupable = 0;
    if (cut) {
      cut.groups.forEach(function (group) {
        groupsById[group.id] = group;
        if (group.members.length > 1) { groupable += 1; }
      });
    }
    if (!keepCollapsed) {
      collapsed = new Set(cut ? cut.groups.map(function (group) { return group.id; }) : []);
    }
    cutReadout.textContent = cut
      ? cut.groups.length + " groups (" + groupable + " with more than one topic)"
      : DATA.topics.length + " topics, ungrouped";
  }

  function stepForGroups(target) {
    var wanted = app.thresholdForGroups(DATA.hierarchy, DATA.topics, target);
    for (var i = 0; i < distances.length; i++) {
      if (distances[i] > wanted) { return i; }
    }
    return distances.length;
  }

  (function setUpCutControl() {
    if (!distances.length) {
      document.getElementById("resolution").hidden = true;
      return;
    }
    cutControl.min = 0;
    cutControl.max = distances.length;
    cutControl.value = stepForGroups(OPENING_GROUPS);
    cutControl.addEventListener("input", function () {
      applyCut(Number(cutControl.value), false);
    });
    // Re-running the layout per keystroke of a drag is what makes a
    // slider feel broken; the cut is previewed on input and drawn on
    // release.
    cutControl.addEventListener("change", function () {
      applyCut(Number(cutControl.value), false);
      redraw();
    });
    collapseAll.addEventListener("click", function () {
      collapsed = new Set(Object.keys(groupsById));
      redraw();
    });
    expandAll.addEventListener("click", function () {
      collapsed = new Set();
      redraw();
    });
    applyCut(Number(cutControl.value), false);
  })();

  // ---------- the two families: clusters, and paths ----------

  /* Two buttons, never one. A single path over a fused weight would be
     a distance nobody can interpret, and the design refuses it -- so
     the reader asks the question of one family at a time, and each hop
     comes back with the citekeys or the bridging pair under it. */
  var pathButtons = {
    overlap: document.getElementById("path-overlap"),
    semantic: document.getElementById("path-semantic"),
  };

  function showPath(family) {
    var result = app.path(DATA, family, selected[0], selected[1]);
    if (!result) { return; }
    clearHint();
    detail.innerHTML = "<h2>" + app.escapeHtml(selected[0]) + " — " +
      app.escapeHtml(selected[1]) + "</h2>" + app.pathHtml(DATA, result, ALL_LABELS);
    panelFamily = family;
    highlightPath(result);
  }

  /* The path on the canvas as well as in the panel: the panel is the
     accessible representation, the highlight is the quick read. A hop
     through a topic the reader has hidden ("hide the rest of the
     corpus") has no element to light up -- the panel still names it,
     which is the copy that matters. */
  function highlightPath(result) {
    cy.batch(function () {
      cy.elements().removeClass("on-path");
      result.hops.forEach(function (hop) {
        var id = (hop.family === "overlap" ? "ov-" : "se-") + hop.index;
        cy.$id(id).addClass("on-path");
      });
      (result.labels || []).forEach(function (label) { cy.$id(label).addClass("on-path"); });
    });
  }

  Object.keys(pathButtons).forEach(function (family) {
    pathButtons[family].addEventListener("click", function () { showPath(family); });
  });

  /* Markov clustering over each family, and the grid of where the two
     disagree. Run on demand rather than on load: it is a matrix
     multiplication per iteration over every topic, and the reader who
     never opens the grid should not pay for it. */
  var inflationControl = document.getElementById("inflation");
  var inflationReadout = document.getElementById("inflation-readout");

  function inflation() {
    return Number(inflationControl.value) / 10;
  }

  function renderDisagreement() {
    clearHint();
    detail.innerHTML = "<p>clustering both families…</p>";
    // Yield once so the message paints before the matrices run.
    window.setTimeout(function () {
      detail.innerHTML = app.disagreementHtml(
        app.disagreement(DATA, inflation(), ALL_LABELS)
      );
      disagreementShown = true;
    }, 0);
  }

  inflationControl.addEventListener("input", function () {
    inflationReadout.textContent = inflation().toFixed(1);
  });
  /* Re-cluster on release ("change"), not per tick ("input"): MCL is a
     matrix multiplication per iteration over every topic, and the grid
     must never name an inflation the slider no longer shows (#703). */
  inflationControl.addEventListener("change", function () {
    if (disagreementShown) { renderDisagreement(); }
  });
  document.getElementById("disagreement").addEventListener("click", renderDisagreement);

  // ---------- focus: rings, hops, and the dimmed context ----------

  /* The two controls swap: with nothing pinned the reader is browsing
     the whole corpus and wants the resolution slider; with something
     pinned the cut is suspended (one layout regime at a time) and what
     matters is how far out to read and whether to keep the context. */
  var focusControls = document.getElementById("focus");
  var hopsControl = document.getElementById("hops");
  var hideContext = document.getElementById("hide-context");

  function showControlsForSelection() {
    var pinned = selected.length > 0;
    focusControls.hidden = !pinned;
    var resolution = document.getElementById("resolution");
    if (resolution) { resolution.hidden = pinned || !DATA.hierarchy.length; }
    /* A path is a question about a pair and about one family, so a
       button appears at two pinned topics and only while its own family
       is on. Offering "path over semantic nearness" over edges the
       reader has just taken off the canvas would answer a question
       about a graph they are not looking at. */
    Object.keys(pathButtons).forEach(function (family) {
      pathButtons[family].hidden = selected.length !== 2 || !activeFamilies.has(family);
    });
  }

  hopsControl.addEventListener("change", function () {
    maxHops = Number(hopsControl.value);
    redraw();
  });
  hideContext.addEventListener("change", function () {
    context = hideContext.checked ? "hide" : "dim";
    redraw();
  });

  // ---------- hierarchy ----------

  /* Re-rendered when the origin filter moves: a merge naming a topic
     the reader has filtered away is a row about nothing they can see.
     The stored tree itself is never recut -- that would invent a
     grouping no stage computed. */
  function renderHierarchy() {
    var body = app.hierarchyHtml(DATA.hierarchy, ALL_LABELS);
    document.getElementById("hierarchy").hidden = !body;
    document.getElementById("hierarchy-body").innerHTML = body;
  }
  renderHierarchy();

  // ---------- uncovered seeds ----------

  /* Hidden entirely when every seed found a home -- an empty admission
     is noise -- and hidden too for an older payload that predates the
     field, which is indistinguishable from that and honestly so. */
  (function renderUncovered() {
    var uncovered = DATA.uncovered || [];
    if (!uncovered.length) {
      document.getElementById("uncovered").hidden = true;
      return;
    }
    document.getElementById("uncovered-body").innerHTML = app.uncoveredHtml(uncovered);
  })();

  // ---------- search: typeahead, chips, filtering ----------

  var searchInput = document.getElementById("search");
  var suggestions = document.getElementById("suggestions");
  var chips = document.getElementById("chips");
  var activeIndex = -1;

  function renderSuggestions() {
    var found = app.candidatesFor(DATA, selected, searchInput.value, activeOrigins);
    suggestions.innerHTML = app.suggestionsHtml(found, activeIndex);
    suggestions.hidden = !found.length;
    return found;
  }

  function addChip(label) {
    if (!topicsByLabel[label] || selected.indexOf(label) >= 0) { return; }
    selected.push(label);
    var topic = topicsByLabel[label];
    var chip = document.createElement("span");
    chip.className = "chip";
    chip.style.background =
      app.ORIGIN_COLORS[topic.origin] || app.ORIGIN_COLORS.emergent;
    chip.dataset.label = label;
    chip.appendChild(document.createTextNode(label));
    var close = document.createElement("button");
    close.textContent = "×";
    close.setAttribute("aria-label", "remove " + label);
    close.addEventListener("click", function () {
      selected = selected.filter(function (s) { return s !== label; });
      chip.remove();
      // Removing the last chip hands the canvas back to the grouped
      // view, which is where it started.
      showControlsForSelection();
      redraw();
    });
    chip.appendChild(close);
    chips.appendChild(chip);
    searchInput.value = "";
    activeIndex = -1;
    suggestions.hidden = true;
    showControlsForSelection();
    redraw();
    if (selected.length === 2 && showPair(selected[0], selected[1])) { return; }
    showTopic(label);
  }

  searchInput.addEventListener("input", function () {
    activeIndex = -1;
    renderSuggestions();
  });
  searchInput.addEventListener("keydown", function (event) {
    var found = app.candidatesFor(DATA, selected, searchInput.value, activeOrigins);
    if (event.key === "ArrowDown") {
      activeIndex = Math.min(activeIndex + 1, found.length - 1);
      renderSuggestions();
      event.preventDefault();
    } else if (event.key === "ArrowUp") {
      activeIndex = Math.max(activeIndex - 1, 0);
      renderSuggestions();
      event.preventDefault();
    } else if (event.key === "Enter" && found.length) {
      addChip(found[activeIndex >= 0 ? activeIndex : 0].label);
    } else if (event.key === "Escape") {
      searchInput.value = "";
      activeIndex = -1;
      suggestions.hidden = true;
    } else if (event.key === "Backspace" && !searchInput.value && selected.length) {
      var last = chips.querySelector(".chip:last-of-type button");
      if (last) { last.click(); }
    }
  });
  suggestions.addEventListener("mousedown", function (event) {
    var item = event.target.closest("li[data-label]");
    if (item) {
      addChip(item.getAttribute("data-label"));
      event.preventDefault();
    }
  });
  document.addEventListener("click", function (event) {
    if (!document.getElementById("search-wrap").contains(event.target)) {
      suggestions.hidden = true;
    }
  });

  /* Esc's precedence: the type-ahead, when open, always wins --
     that is the searchInput handler above, unchanged. Registered on
     `document` in the *capture* phase so it observes `suggestions`
     before this keystroke's own bubble-phase handler (searchInput's)
     has run and possibly closed it -- capture fires top-down, ahead of
     the target's own listeners. Chips are never touched here: clearing
     them is a destructive act the request gives its own gesture, not a
     fall-through from Esc. */
  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") { return; }
    if (app.escapeAction(!suggestions.hidden, latched) === "releaseLatch") {
      releaseLatch();
    }
  }, true);

  // ---------- the two filter pickers ----------

  /* Origin classes and edge families, one widget each. Both are the
     reader's view and not the corpus's: they change what is on the
     canvas, never what any stage computed -- the absence verdict, the
     withheld-edge count and the panel's per-family brokerage figures
     stay corpus-wide for that reason, and the caption in the header
     says so.

     Only the summary is rewritten when a row moves, never the panel:
     re-rendering the whole control would close it under the reader's
     pointer, and the second of two families is exactly the tick they
     most often want to move straight after the first. */
  var originsRow = document.getElementById("origins");
  var familiesRow = document.getElementById("families");

  function renderOrigins() {
    originsRow.innerHTML = app.originsHtml(app.originControls(DATA, activeOrigins), DATA);
  }

  function renderFamilies() {
    familiesRow.innerHTML = app.familiesHtml(app.familyControls(DATA, activeFamilies));
  }

  function updateSummary(row, text) {
    var state = row.querySelector(".picker-state");
    if (state) { state.textContent = text; }
  }

  /* A pinned topic whose class has just gone out cannot stay pinned:
     the chip would name a node no longer on the canvas, and the ego
     view would be laid out around nothing. Removing the chip through
     its own close button keeps one code path for un-pinning. */
  function pruneChips() {
    Array.prototype.forEach.call(chips.querySelectorAll(".chip"), function (chip) {
      if (ALL_LABELS.has(chip.dataset.label)) { return; }
      var close = chip.querySelector("button");
      if (close) { close.click(); }
    });
  }

  originsRow.addEventListener("change", function (event) {
    var box = event.target.closest("input[data-origin]");
    if (!box) { return; }
    var next = app.nextSelection(activeOrigins, box.dataset.origin, box.checked);
    if (!next) {
      // The last class. An empty canvas reads as an empty corpus, so
      // the tick goes back rather than the graph going away.
      box.checked = true;
      return;
    }
    activeOrigins = next;
    ALL_LABELS = app.labelsWithOrigins(DATA, activeOrigins);
    updateSummary(
      originsRow,
      app.originsSummary(app.originControls(DATA, activeOrigins), DATA)
    );
    pruneChips();
    renderHierarchy();
    redraw();
  });

  familiesRow.addEventListener("change", function (event) {
    var box = event.target.closest("input[data-family]");
    if (!box) { return; }
    var next = app.nextSelection(activeFamilies, box.dataset.family, box.checked);
    if (!next) {
      /* The last family. With neither on there is no graph at all --
         not even the union the rings used to walk -- so the tick goes
         back, the same refusal the origin axis makes. */
      box.checked = true;
      return;
    }
    activeFamilies = next;
    updateSummary(
      familiesRow, app.familiesSummary(app.familyControls(DATA, activeFamilies))
    );
    /* The panel first: a path or an edge card belonging to the family
       that has just gone off is describing lines no longer drawn.
       Then the buttons, then the canvas -- where the edge set, the hop
       distances and the ring placement all move together, because
       `redraw` reads `families()` for all three. */
    if (panelFamily && !activeFamilies.has(panelFamily)) { showHelp(); }
    showControlsForSelection();
    redraw();
  });

  /* Opening and shutting, for both pickers. A native <button> already
     answers Enter and Space, so this is the toggle, the escape hatch
     and the click-away -- the same three the type-ahead's popover has.
     Arrow-down opens and steps into the rows; inside the panel, Tab and
     Space are the browser's own and are left alone, which is why the
     rows are real checkboxes and not list items pretending to be. */
  function panelOf(row) { return row.querySelector(".picker-panel"); }

  function setOpen(row, open) {
    var button = row.querySelector(".picker-summary");
    panelOf(row).hidden = !open;
    button.setAttribute("aria-expanded", open ? "true" : "false");
  }

  function closeAllPickers(except) {
    [originsRow, familiesRow].forEach(function (row) {
      if (row !== except && panelOf(row)) { setOpen(row, false); }
    });
  }

  [originsRow, familiesRow].forEach(function (row) {
    row.addEventListener("click", function (event) {
      var button = event.target.closest(".picker-summary");
      if (!button) { return; }
      var open = panelOf(row).hidden;
      closeAllPickers(row);
      setOpen(row, open);
    });
    row.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        setOpen(row, false);
        row.querySelector(".picker-summary").focus();
        return;
      }
      if (event.key === "ArrowDown" && event.target.closest(".picker-summary")) {
        setOpen(row, true);
        var first = row.querySelector('.picker-row input:not([disabled])');
        if (first) { first.focus(); }
        event.preventDefault();
      }
    });
  });

  document.addEventListener("click", function (event) {
    if (!event.target.closest(".picker")) { closeAllPickers(null); }
  });

  renderOrigins();
  renderFamilies();
  showControlsForSelection();
  redraw();
})();
