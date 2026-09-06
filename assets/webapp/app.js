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
  var ALL_LABELS = new Set(DATA.topics.map(function (t) { return t.label; }));
  var FAMILIES = ["overlap", "semantic"];
  var context = "dim";
  var maxHops = 2;
  /* Papers on the canvas, opt-in and capped: a paper in three topics is
     visibly a bridge, and 131 topics fully expanded is several hundred
     nodes and thousands of lines. */
  var expanded = new Set();

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
      /* Focus plus context. The context is pushed back rather than
         deleted, and `events: no` keeps it from taking clicks or
         stealing hover -- a dimmed node that still answers the mouse
         reads as a bug, not as background. */
      { selector: "node[dim = 1]", style: {
        "opacity": 0.12, "text-opacity": 0, "events": "no",
      } },
      { selector: "edge[dim = 1]", style: { "opacity": 0.06, "events": "no" } },
      /* Hover is a separate channel from selection dimming, so the two
         compose instead of clobbering each other: `.faded` is what the
         mouse is doing right now, `dim` is what the chips are doing. */
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
      { selector: "edge[family = 'member']", style: {
        "width": 1,
        "line-color": "#90a4ae",
        "line-style": "dotted",
        "curve-style": "haystack",
        "opacity": 0.7,
      } },
      { selector: ".on-path", style: {
        "line-color": "#e53935", "target-arrow-color": "#e53935",
        "border-width": 3, "border-color": "#e53935",
        "opacity": 1, "z-index": 10,
      } },
      { selector: ".hovered", style: {
        "border-width": 3, "border-color": "#e53935", "text-opacity": 1,
      } },
    ],
  });

  function view() {
    return {
      cut: cut, collapsed: collapsed, context: context,
      all: ALL_LABELS, expanded: expanded,
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
    // One notion of "near the selection", used for both what is
    // emphasised and where it is drawn: the hop control moves them
    // together, so nothing is ever placed on a ring and dimmed to
    // background at the same time.
    var hops = selected.length ? app.hopsFrom(DATA, selected, FAMILIES) : null;
    var visible = hops ? app.withinHops(hops, maxHops) : ALL_LABELS;
    var elements = app.elementsFor(DATA, visible, selected, view());
    cy.batch(function () {
      cy.elements().remove();
      cy.add(elements);
    });
    if (hops) {
      // Rings by hop distance from what is pinned: deterministic, and
      // an extension of the "a circle is legible" argument rather than
      // a contradiction of it. elementsFor has already suspended the
      // cut, so there are no boxes to lay out here.
      var at = app.ringPositions(DATA, selected, hops, maxHops);
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

  // ---------- side panel ----------

  var detail = document.getElementById("detail");
  var hint = document.getElementById("hint");

  function showTopic(label) {
    var topic = topicsByLabel[label];
    if (!topic) { return; }
    hint.hidden = true;
    detail.innerHTML = app.topicHtml(DATA, topic) + egoSection(label);
  }

  /* The brokerage reading, under the papers rather than instead of
     them: "is this topic a theme or a bridge" is the survey-scoping
     question, and it is answered per edge family because a topic that
     brokers over shared papers but not over vocabulary is a different
     animal from one that does the reverse. */
  function egoSection(label) {
    return app.egoHtml(label, {
      overlap: app.egoStats(DATA, label, "overlap"),
      semantic: app.egoStats(DATA, label, "semantic"),
    });
  }

  function showEdge(family, index) {
    hint.hidden = true;
    detail.innerHTML = app.edgeHtml(DATA, family, index);
  }

  function showGroup(id) {
    if (!groupsById[id]) { return; }
    hint.hidden = true;
    detail.innerHTML = app.groupHtml(groupsById[id]);
  }

  function showPaper(citekey) {
    var html = citekey && app.paperHtml(DATA, citekey);
    if (!html) { return; }
    hint.hidden = true;
    detail.innerHTML = html;
  }

  function showBundle(pairs) {
    hint.hidden = true;
    detail.innerHTML = app.bundleHtml(DATA, pairs);
  }

  /* Two pinned topics with no edge between them: the reader gets the
     gate's own reasoning rather than an empty canvas between two chips.
     Exactly two, because the sentence is about a pair -- with three
     pinned there are three pairs and no obvious one to answer. */
  function showPair(a, b) {
    var verdict = app.explain(DATA, a, b);
    if (!verdict || verdict.drawn) { return false; }
    hint.hidden = true;
    detail.innerHTML = app.absenceHtml(a, b, verdict);
    return true;
  }

  // A DOM tooltip rather than a vendored positioning library: the
  // bridge pair is the fastest answer to "why is this edge here", and
  // it should not cost a click.
  var tip = document.getElementById("tip");

  function showTip(event, text) {
    tip.textContent = text;
    tip.hidden = false;
    tip.style.left = event.renderedPosition.x + 14 + "px";
    tip.style.top = event.renderedPosition.y + 14 + "px";
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
  cy.on("mouseout", "edge", function () { tip.hidden = true; });

  cy.on("tap", "node", function (event) {
    var node = event.target;
    if (node.data("kind") === "paper") {
      showPaper(app.citekeyOf(DATA, node.id()));
    } else if (node.data("isGroup") || node.data("collapsed")) {
      showGroup(node.id());
    } else {
      showTopic(node.id());
    }
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
      hint.hidden = false;
      hint.textContent = "At most " + app.EXPANSION_CAP + " topics can show " +
        "their papers at once — double-click one of the open ones to close it.";
      return;
    } else {
      expanded.add(node.id());
    }
    redraw();
    showTopic(node.id());
  });

  /* Hovering a node lights its own neighbourhood and pushes the rest
     back -- the one interaction people expect from a graph, and the
     app had none of it. Cheap enough to do on every mouse move because
     it is class toggles inside one batch, not a re-layout. */
  cy.on("mouseover", "node", function (event) {
    var near = event.target.closedNeighborhood();
    cy.batch(function () {
      cy.elements().not(near).addClass("faded");
      event.target.addClass("hovered");
    });
  });
  cy.on("mouseout", "node", function () {
    cy.batch(function () { cy.elements().removeClass("faded hovered"); });
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

  detail.addEventListener("click", function (event) {
    var goto_ = event.target.closest("a[data-goto]");
    if (goto_) {
      showTopic(goto_.getAttribute("data-goto"));
      return;
    }
    var edge = event.target.closest("a[data-edge]");
    if (edge) {
      var parts = edge.getAttribute("data-edge").split(":");
      showEdge(parts[0], Number(parts[1]));
    }
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
    hint.hidden = true;
    detail.innerHTML = "<h2>" + app.escapeHtml(selected[0]) + " — " +
      app.escapeHtml(selected[1]) + "</h2>" + app.pathHtml(DATA, result);
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

  inflationControl.addEventListener("input", function () {
    inflationReadout.textContent = inflation().toFixed(1);
  });
  document.getElementById("disagreement").addEventListener("click", function () {
    hint.hidden = true;
    detail.innerHTML = "<p>clustering both families…</p>";
    // Yield once so the message paints before the matrices run.
    window.setTimeout(function () {
      detail.innerHTML = app.disagreementHtml(app.disagreement(DATA, inflation()));
    }, 0);
  });

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
    // A path is a question about a pair, so the buttons appear at two
    // pinned topics and go again at one or three.
    Object.keys(pathButtons).forEach(function (family) {
      pathButtons[family].hidden = selected.length !== 2;
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

  (function renderHierarchy() {
    if (!DATA.hierarchy.length) {
      document.getElementById("hierarchy").hidden = true;
      return;
    }
    document.getElementById("hierarchy-body").innerHTML =
      app.hierarchyHtml(DATA.hierarchy);
  })();

  // ---------- search: typeahead, chips, filtering ----------

  var searchInput = document.getElementById("search");
  var suggestions = document.getElementById("suggestions");
  var chips = document.getElementById("chips");
  var activeIndex = -1;

  function renderSuggestions() {
    var found = app.candidatesFor(DATA, selected, searchInput.value);
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
    var found = app.candidatesFor(DATA, selected, searchInput.value);
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

  showControlsForSelection();
  redraw();
})();
