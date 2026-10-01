/* The header's search box: type-ahead suggestions and the chips for
   whatever is pinned.

   DOM wiring, not pure logic -- `app.candidatesFor`/`suggestionsHtml`
   (graph.js, panel.js) already carry the testable parts, and
   `tests/webapp/*.test.js` exercises them without a DOM. What is left
   here is reading the input, walking the suggestion list and building
   chip elements, which is why this file adds no new node test of its
   own.

   `create()` takes the shared selection/filter state and the app.js
   callbacks a chip's own side effects need to reach across module
   boundaries -- see app.js's own call site for what each one does. */
"use strict";

window.CHITRAGUPTA_SEARCH = (function () {
  function create(options) {
    var DATA = options.DATA;
    var app = options.app;
    var state = options.state;
    var topicsByLabel = options.topicsByLabel;
    var redraw = options.redraw;
    var showControlsForSelection = options.showControlsForSelection;
    var showPair = options.showPair;
    var showTopic = options.showTopic;

    var searchInput = document.getElementById("search");
    var suggestions = document.getElementById("suggestions");
    var chips = document.getElementById("chips");
    var activeIndex = -1;

    function renderSuggestions() {
      var found = app.candidatesFor(DATA, state.selected, searchInput.value, state.activeOrigins);
      suggestions.innerHTML = app.suggestionsHtml(found, activeIndex);
      suggestions.hidden = !found.length;
      return found;
    }

    function addChip(label) {
      if (!topicsByLabel[label] || state.selected.indexOf(label) >= 0) { return; }
      state.selected.push(label);
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
        state.selected = state.selected.filter(function (s) { return s !== label; });
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
      if (state.selected.length === 2 && showPair(state.selected[0], state.selected[1])) { return; }
      showTopic(label);
    }

    searchInput.addEventListener("input", function () {
      activeIndex = -1;
      renderSuggestions();
    });
    searchInput.addEventListener("keydown", function (event) {
      var found = app.candidatesFor(DATA, state.selected, searchInput.value, state.activeOrigins);
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
      } else if (event.key === "Backspace" && !searchInput.value && state.selected.length) {
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
    // app.js's one document click listener calls this for every click.
    function clickAway(target) {
      if (!document.getElementById("search-wrap").contains(target)) {
        suggestions.hidden = true;
      }
    }

    /* A pinned topic whose class has just gone out cannot stay pinned:
       the chip would name a node no longer on the canvas, and the ego
       view would be laid out around nothing. Removing the chip through
       its own close button keeps one code path for un-pinning. */
    function pruneChips() {
      Array.prototype.forEach.call(chips.querySelectorAll(".chip"), function (chip) {
        if (state.ALL_LABELS.has(chip.dataset.label)) { return; }
        var close = chip.querySelector("button");
        if (close) { close.click(); }
      });
    }

    return {
      // Esc's precedence: the type-ahead, when open, always wins. This
      // is what lets app.js's capture-phase document handler observe
      // that before deciding whether to close a picker or release the
      // latch instead -- the actual closing above is this module's own
      // bubble-phase handler on searchInput, unchanged.
      isOpen: function () { return !suggestions.hidden; },
      pruneChips: pruneChips,
      clickAway: clickAway,
    };
  }

  return { create: create };
})();
