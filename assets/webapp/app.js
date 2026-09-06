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
  var neighbours = app.adjacency(DATA);
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

  // ---------- cytoscape ----------

  var cy = cytoscape({
    container: document.getElementById("cy"),
    elements: [],
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
      { selector: "edge[family = 'overlap']", style: {
        "width": "data(width)",
        "line-color": "#5c6bc0",
        "curve-style": "bezier",
        "opacity": 0.75,
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
    ],
  });

  function view() {
    return { cut: cut, collapsed: collapsed };
  }

  function redraw() {
    var visible = app.visibleLabels(DATA, selected, neighbours);
    var elements = app.elementsFor(DATA, visible, selected, view());
    cy.batch(function () {
      cy.elements().remove();
      cy.add(elements);
    });
    if (cut) {
      // Groups round one circle, each group's topics round a smaller
      // one inside it. Deterministic, and cose is bad at compounds --
      // graph.js's own comment has the reasoning.
      var at = app.positionsFor(elements);
      cy.layout({ name: "preset", positions: function (n) { return at[n.id()]; } }).run();
      cy.fit(undefined, 40);
      return;
    }
    // Ungrouped: a deterministic circle first, then cose refines from
    // it without re-randomising -- the same graph always lands in the
    // same place.
    cy.layout({ name: "circle" }).run();
    if (cy.nodes().length > 2) {
      cy.layout({
        name: "cose", randomize: false, animate: false, padding: 40,
        stop: function () { cy.fit(undefined, 40); },
      }).run();
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
    detail.innerHTML = app.topicHtml(DATA, topic);
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

  function showBundle(pairs) {
    hint.hidden = true;
    detail.innerHTML = app.bundleHtml(DATA, pairs);
  }

  cy.on("tap", "node", function (event) {
    var node = event.target;
    if (node.data("isGroup") || node.data("collapsed")) {
      showGroup(node.id());
    } else {
      showTopic(node.id());
    }
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
      redraw();
    });
    chip.appendChild(close);
    chips.appendChild(chip);
    searchInput.value = "";
    activeIndex = -1;
    suggestions.hidden = true;
    redraw();
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

  redraw();
})();
