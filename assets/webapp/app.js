/* The topic-graph app: pure renderer of window.CHITRAGUPTA_TOPICS,
   which data.js (written by `corpus discover --app`) assigns. It
   computes no edge and no membership -- everything drawn here was
   derived once by `chitragupta enrich` -- so the app cannot disagree
   with the terminal views. Colour vocabulary mirrors style.css.

   What is left in this file is the wiring that doesn't belong to its
   own module: the cytoscape instance, the node-focus/panel/resolution/
   path/hierarchy events, and `state`, the selection and filter fields
   search.js and pickers.js need to reach across the split. The logic
   those DOM events call lives in graph.js (payload -> what is visible,
   what cytoscape is handed) and panel.js (data -> HTML); search.js
   (type-ahead and chips) and pickers.js (the origin and family
   widgets) hold the DOM wiring #857 split out of here, each taking
   `state` and a few of this file's own callbacks rather than reading
   its module-level variables directly; cy_style.js holds the
   cytoscape stylesheet as data. index.html loads all of them before
   this file, and everything except the DOM wiring is testable without
   a browser and tested under tests/webapp/. */
"use strict";

(function () {
  var DATA = window.CHITRAGUPTA_TOPICS;
  var app = window.CHITRAGUPTA_APP;

  /* Checked before anything reads the payload (#855). A missing,
     truncated or hand-edited data.js used to throw on the next line,
     before any handler was wired, and the reader was left with help
     text describing controls that did nothing. The message goes where
     `say` puts one, written directly because `say` and its element are
     set up further down, past the reads this check exists to stop. */
  var problems = app.payloadProblems(DATA);
  if (problems.length) {
    var notice = document.getElementById("hint");
    notice.textContent = "data.js is missing or incomplete: " + problems.join(", ") +
      ". Re-export it with `chitragupta corpus discover --app`.";
    notice.hidden = false;
    return;
  }

  var topicsByLabel = app.byLabel(DATA.topics);

  /* The state search.js and pickers.js mutate as well as this file. A
     plain object rather than four more module-level `var`s, so the two
     extracted modules can share it by reference instead of each
     needing its own copy wired back here.

     `selected` is the reader's own pinned-topic chips (chip order
     preserved).

     The origin filter. `activeOrigins` opens as whatever the export
     shipped, so the app's first frame is exactly what the same
     `--origins` run showed in the terminal; `ALL_LABELS` is derived
     from it and re-derived whenever a picker row moves.

     The edge-family filter. `activeFamilies` was a module constant no
     element read, and the cost was not a missing control: `hopsFrom`
     walks whatever adjacency it is handed, so the ego rings measured
     distance over the union of both families and a topic one shared
     paper plus one cosine hop away sat on ring 2 beside a topic two
     shared papers out. The reader could not ask "how far is this over
     shared papers" -- a question `discover --path --family` has always
     answered in the terminal.

     A Set here and a list at the call sites, because `familiesOf` in
     graph.js and `hopsFrom` in ego.js both want an ordered list and
     order is the legend's. */
  var state = {
    selected: [],
    activeOrigins: new Set(app.shippedOrigins(DATA)),
    activeFamilies: new Set(app.shippedFamilies(DATA)),
  };
  state.ALL_LABELS = app.labelsWithOrigins(DATA, state.activeOrigins);

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
      return state.activeFamilies.has(family);
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
    style: app.CY_STYLE,
  });

  function view() {
    return {
      cut: cut, collapsed: collapsed, context: context,
      all: state.ALL_LABELS, expanded: expanded, families: families(),
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
    var hops = state.selected.length
      ? app.hopsFrom(DATA, state.selected, families())
      : null;
    // The rings are walked over the whole payload, so a neighbour can be
    // a topic the origin filter has taken off the canvas.
    var visible = hops
      ? app.restrictTo(app.withinHops(hops, maxHops), state.ALL_LABELS)
      : state.ALL_LABELS;
    var elements = app.elementsFor(DATA, visible, state.selected, view());
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
      var at = app.ringPositions(DATA, state.selected, hops, maxHops, families());
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

  /* Bumped by every panel write, so a write deferred to a later task
     can tell it has been overtaken. The disagreement grid paints a
     "clustering…" line and fills itself in after a `setTimeout`; a node
     tap already queued when the button was pressed runs in between, and
     without this the timeout overwrote that topic's card and set
     `disagreementShown`, so the next inflation change re-clustered over
     a panel the reader had pointed elsewhere (#860). */
  var renderToken = 0;

  function clearHint() {
    hint.hidden = true;
    hint.textContent = HELP;
    disagreementShown = false;
    panelFamily = null;
    renderToken += 1;
  }

  /* Back to the standing help text, with nothing selected in the panel:
     the state the app opens in, and where a panel whose subject has
     just left the canvas has to return to. */
  function showHelp() {
    clearHint();
    detail.innerHTML = "";
    hint.hidden = false;
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
    var html = app.edgeHtml(DATA, family, index);
    if (!html) { showHelp(); return; }
    clearHint();
    detail.innerHTML = html;
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

  /* A membership line carries no payload index -- it is neither family
     -- so both edge handlers leave it alone rather than look one up
     (#859): the paper node at its end is what answers a click. */
  cy.on("mouseover", "edge", function (event) {
    var edge = event.target;
    if (edge.data("family") === "member") { return; }
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
    showTip(event, app.linkWhy("overlap", overlap));
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
    if (edge.data("family") === "member") { return; }
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
    var result = app.path(DATA, family, state.selected[0], state.selected[1]);
    if (!result) { return; }
    clearHint();
    detail.innerHTML = "<h2>" + app.escapeHtml(state.selected[0]) + " — " +
      app.escapeHtml(state.selected[1]) + "</h2>" + app.pathHtml(DATA, result, state.ALL_LABELS);
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
        cy.$id(app.edgeId(DATA, hop.family, hop.index)).addClass("on-path");
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
    var token = renderToken;
    detail.innerHTML = "<p>clustering both families…</p>";
    // Yield once so the message paints before the matrices run.
    window.setTimeout(function () {
      if (token !== renderToken) { return; }
      detail.innerHTML = app.disagreementHtml(
        app.disagreement(DATA, inflation(), state.ALL_LABELS)
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
    var pinned = state.selected.length > 0;
    focusControls.hidden = !pinned;
    var resolution = document.getElementById("resolution");
    if (resolution) { resolution.hidden = pinned || !DATA.hierarchy.length; }
    /* A path is a question about a pair and about one family, so a
       button appears at two pinned topics and only while its own family
       is on. Offering "path over semantic nearness" over edges the
       reader has just taken off the canvas would answer a question
       about a graph they are not looking at. */
    Object.keys(pathButtons).forEach(function (family) {
      pathButtons[family].hidden = state.selected.length !== 2 || !state.activeFamilies.has(family);
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
    var body = app.hierarchyHtml(DATA.hierarchy, state.ALL_LABELS);
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

  // ---------- search and the two filter pickers: cross-module wiring ----------

  /* Both modules take `state` by reference (so a write to e.g.
     `state.selected` here is visible to them and vice versa) plus
     whichever of this file's own functions their own event handlers
     have to call -- see search.js/pickers.js for what each does with
     them. */
  var search = window.CHITRAGUPTA_SEARCH.create({
    DATA: DATA, app: app, state: state, topicsByLabel: topicsByLabel,
    redraw: redraw, showControlsForSelection: showControlsForSelection,
    showPair: showPair, showTopic: showTopic,
  });

  var pickers = window.CHITRAGUPTA_PICKERS.create({
    DATA: DATA, app: app, state: state,
    originsRow: document.getElementById("origins"),
    familiesRow: document.getElementById("families"),
    pruneChips: search.pruneChips,
    onOriginsChanged: function () { renderHierarchy(); redraw(); },
    onFamiliesChanged: function (next) {
      /* The panel first: a path or an edge card belonging to the family
         that has just gone off is describing lines no longer drawn.
         Then the buttons, then the canvas -- where the edge set, the hop
         distances and the ring placement all move together, because
         `redraw` reads `families()` for all three. */
      if (panelFamily && !next.has(panelFamily)) { showHelp(); }
      showControlsForSelection();
      redraw();
    },
  });

  /* Click-away, one policy for both pop-ups the way Esc below is one:
     a click outside the search box shuts its suggestions, and one
     outside every picker shuts the pickers. One listener rather than
     one per module, so the order the two are asked in is written here
     instead of following from which module happened to be created
     first. */
  document.addEventListener("click", function (event) {
    search.clickAway(event.target);
    pickers.clickAway(event.target);
  });

  /* Esc's precedence: the type-ahead, when open, always wins --
     that is search.js's own bubble-phase handler on its input,
     unchanged. Registered on `document` in the *capture* phase so it
     observes search's suggestions list before this keystroke's own
     bubble-phase handler has run and possibly closed it -- capture
     fires top-down, ahead of the target's own listeners. Chips are
     never touched here: clearing them is a destructive act the request
     gives its own gesture, not a fall-through from Esc. */
  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") { return; }
    var action = app.escapeAction(search.isOpen(), latched, pickers.anyPickerOpen());
    if (action === "closePicker") {
      // Focus goes back to the button that opened it: without this it
      // is left on a checkbox inside a hidden panel, and the next Tab
      // starts from nowhere the reader can see.
      var row = pickers.openPicker();
      pickers.closeAllPickers(null);
      row.querySelector(".picker-summary").focus();
      return;
    }
    if (action === "releaseLatch") { releaseLatch(); }
  }, true);

  showControlsForSelection();
  redraw();
})();
