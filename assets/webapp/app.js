/* The topic-graph app: pure renderer of window.CHITRAGUPTA_TOPICS,
   which data.js (written by `corpus discover --app`) assigns. It
   computes no edge and no membership -- everything drawn here was
   derived once by `chitragupta enrich` -- so the app cannot disagree
   with the terminal views. Colour vocabulary mirrors style.css. */
"use strict";

(function () {
  var DATA = window.CHITRAGUPTA_TOPICS;
  var ORIGIN_COLORS = {
    seed: "#2e7d32",
    keyword: "#b8860b",
    both: "#00695c",
    emergent: "#1565c0",
  };
  var ORIGIN_LABELS = {
    seed: "seed topic",
    keyword: "keyword topic",
    both: "seed + keyword topic",
    emergent: "emergent topic",
  };

  var topicsByLabel = {};
  DATA.topics.forEach(function (t) { topicsByLabel[t.label] = t; });

  // Direct neighbours over both edge families, precomputed once: the
  // filter's "related" set is exactly this adjacency.
  var neighbours = {};
  function addNeighbour(a, b) {
    (neighbours[a] = neighbours[a] || new Set()).add(b);
    (neighbours[b] = neighbours[b] || new Set()).add(a);
  }
  DATA.edges_overlap.forEach(function (e) { addNeighbour(e.a, e.b); });
  DATA.edges_semantic.forEach(function (e) { addNeighbour(e.a, e.b); });

  var selected = []; // chip order preserved

  // ---------- cytoscape ----------

  function nodeSize(topic) {
    return 22 + 9 * Math.sqrt(topic.members.length);
  }

  function elementsFor(visible) {
    var els = [];
    DATA.topics.forEach(function (t) {
      if (!visible.has(t.label)) { return; }
      els.push({
        group: "nodes",
        data: {
          id: t.label,
          label: t.label,
          origin: t.origin,
          color: ORIGIN_COLORS[t.origin] || ORIGIN_COLORS.emergent,
          size: nodeSize(t),
          picked: selected.indexOf(t.label) >= 0 ? 1 : 0,
        },
      });
    });
    DATA.edges_overlap.forEach(function (e, i) {
      if (!visible.has(e.a) || !visible.has(e.b)) { return; }
      els.push({
        group: "edges",
        data: {
          id: "ov-" + i, source: e.a, target: e.b, family: "overlap",
          width: 1.5 + 6 * e.overlap_coeff, index: i,
        },
      });
    });
    DATA.edges_semantic.forEach(function (e, i) {
      if (!visible.has(e.a) || !visible.has(e.b)) { return; }
      els.push({
        group: "edges",
        data: {
          id: "se-" + i, source: e.a, target: e.b, family: "semantic",
          width: 1 + 3 * e.similarity, index: i,
        },
      });
    });
    return els;
  }

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

  function visibleLabels() {
    if (!selected.length) {
      return new Set(DATA.topics.map(function (t) { return t.label; }));
    }
    var visible = new Set(selected);
    selected.forEach(function (label) {
      (neighbours[label] || new Set()).forEach(function (n) { visible.add(n); });
    });
    return visible;
  }

  function redraw() {
    var visible = visibleLabels();
    cy.elements().remove();
    cy.add(elementsFor(visible));
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

  function escapeHtml(text) {
    var div = document.createElement("div");
    div.textContent = text == null ? "" : String(text);
    return div.innerHTML;
  }

  function paperCard(member) {
    var pct = Math.max(0, Math.min(100, Math.round(member.score * 100)));
    return '<div class="paper">' +
      '<p class="title">' + (escapeHtml(member.title) || "<em>(no title in ledger)</em>") + "</p>" +
      '<div class="meta"><code>' + escapeHtml(member.citekey) + "</code>" +
      '<div class="scorebar"><span style="width:' + pct + '%"></span></div>' +
      "<span>" + member.score.toFixed(2) + "</span></div></div>";
  }

  function linkedRows(topic) {
    var rows = "";
    DATA.edges_overlap.forEach(function (e) {
      var other = e.a === topic.label ? e.b : e.b === topic.label ? e.a : null;
      if (!other) { return; }
      rows += '<div class="linked-topic"><a data-goto="' + escapeHtml(other) + '">' +
        escapeHtml(other) + "</a><div class=\"why\">shares " + e.shared.length +
        " paper" + (e.shared.length === 1 ? "" : "s") + ": " +
        escapeHtml(e.shared.join(", ")) + "</div></div>";
    });
    DATA.edges_semantic.forEach(function (e) {
      var other = e.a === topic.label ? e.b : e.b === topic.label ? e.a : null;
      if (!other) { return; }
      rows += '<div class="linked-topic"><a data-goto="' + escapeHtml(other) + '">' +
        escapeHtml(other) + "</a><div class=\"why\">semantically near (" +
        e.similarity.toFixed(2) + "), bridged by " +
        escapeHtml(e.bridge.join(" and ")) + "</div></div>";
    });
    return rows || '<div class="linked-topic">no linked topics</div>';
  }

  function showTopic(label) {
    var topic = topicsByLabel[label];
    if (!topic) { return; }
    hint.hidden = true;
    detail.innerHTML =
      "<h2>" + escapeHtml(topic.label) + "</h2>" +
      '<span class="origin-tag" style="background:' +
      (ORIGIN_COLORS[topic.origin] || ORIGIN_COLORS.emergent) + '">' +
      (ORIGIN_LABELS[topic.origin] || topic.origin) + "</span>" +
      (topic.terms.length
        ? '<p class="terms">' + escapeHtml(topic.terms.join(" · ")) + "</p>" : "") +
      "<h3>Papers (" + topic.members.length + ")</h3>" +
      topic.members.map(paperCard).join("") +
      "<h3>Linked topics</h3>" + linkedRows(topic);
  }

  function showEdge(family, index) {
    hint.hidden = true;
    var e, papers, why;
    if (family === "overlap") {
      e = DATA.edges_overlap[index];
      papers = e.shared;
      why = "These topics share " + papers.length + " paper" +
        (papers.length === 1 ? "" : "s") + " (jaccard " + e.jaccard.toFixed(2) +
        ", p = " + e.p_value.toExponential(1) + ").";
    } else {
      e = DATA.edges_semantic[index];
      papers = e.bridge;
      why = "These topics are semantically near (similarity " +
        e.similarity.toFixed(2) + "); the closest paper pair bridges them.";
    }
    var cards = papers.map(function (citekey) {
      var member = findMember(citekey);
      return member ? paperCard(member) :
        '<div class="paper"><div class="meta"><code>' + escapeHtml(citekey) +
        "</code></div></div>";
    });
    detail.innerHTML =
      "<h2>" + escapeHtml(e.a) + " — " + escapeHtml(e.b) + "</h2>" +
      '<p class="terms">' + escapeHtml(why) + "</p>" +
      "<h3>" + (family === "overlap" ? "Shared papers" : "Bridge papers") + "</h3>" +
      cards.join("");
  }

  function findMember(citekey) {
    for (var i = 0; i < DATA.topics.length; i++) {
      var members = DATA.topics[i].members;
      for (var j = 0; j < members.length; j++) {
        if (members[j].citekey === citekey) { return members[j]; }
      }
    }
    return null;
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
    var body = document.getElementById("hierarchy-body");
    if (!DATA.hierarchy.length) {
      document.getElementById("hierarchy").hidden = true;
      return;
    }
    body.innerHTML = DATA.hierarchy.map(function (merge) {
      return "<div>" + escapeHtml(merge.a) + " + " + escapeHtml(merge.b) +
        " (distance " + merge.distance.toFixed(2) + ")</div>";
    }).join("");
  })();

  // ---------- search: typeahead, chips, filtering ----------

  var searchInput = document.getElementById("search");
  var suggestions = document.getElementById("suggestions");
  var chips = document.getElementById("chips");
  var activeIndex = -1;

  function candidatesFor(query) {
    var needle = query.trim().toLowerCase();
    if (!needle) { return []; }
    var out = [];
    DATA.topics.forEach(function (t) {
      if (selected.indexOf(t.label) >= 0) { return; }
      if (t.label.toLowerCase().indexOf(needle) >= 0) {
        out.push({ label: t.label, why: ORIGIN_LABELS[t.origin] || t.origin });
        return;
      }
      var term = t.terms.find(function (word) {
        return word.toLowerCase().indexOf(needle) >= 0;
      });
      if (term) { out.push({ label: t.label, why: "term: " + term }); }
    });
    return out.slice(0, 12);
  }

  function renderSuggestions() {
    var found = candidatesFor(searchInput.value);
    suggestions.innerHTML = found.map(function (c, i) {
      return '<li data-label="' + escapeHtml(c.label) + '"' +
        (i === activeIndex ? ' class="active"' : "") + ">" +
        "<span>" + escapeHtml(c.label) + '</span><span class="why">' +
        escapeHtml(c.why) + "</span></li>";
    }).join("");
    suggestions.hidden = !found.length;
    return found;
  }

  function addChip(label) {
    if (!topicsByLabel[label] || selected.indexOf(label) >= 0) { return; }
    selected.push(label);
    var topic = topicsByLabel[label];
    var chip = document.createElement("span");
    chip.className = "chip";
    chip.style.background = ORIGIN_COLORS[topic.origin] || ORIGIN_COLORS.emergent;
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
    var found = candidatesFor(searchInput.value);
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
