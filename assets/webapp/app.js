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
    ],
  });

  function redraw() {
    var visible = app.visibleLabels(DATA, selected, neighbours);
    cy.elements().remove();
    cy.add(app.elementsFor(DATA, visible, selected));
    // A deterministic circle first, then cose refines from it without
    // re-randomising -- the same graph always lands in the same place.
    cy.layout({ name: "circle" }).run();
    if (cy.nodes().length > 2) {
      cy.layout({ name: "cose", randomize: false, animate: false, padding: 40 }).run();
    }
    cy.fit(undefined, 40);
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

  cy.on("tap", "node", function (event) { showTopic(event.target.id()); });
  cy.on("tap", "edge", function (event) {
    showEdge(event.target.data("family"), event.target.data("index"));
  });
  detail.addEventListener("click", function (event) {
    var target = event.target.closest("a[data-goto]");
    if (target) { showTopic(target.getAttribute("data-goto")); }
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
