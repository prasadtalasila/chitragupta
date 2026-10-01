/* The two filter pickers: origin classes and edge families, one widget
   each. Both are the reader's view and not the corpus's: they change
   what is on the canvas, never what any stage computed -- the absence
   verdict, the withheld-edge count and the panel's per-family
   brokerage figures stay corpus-wide for that reason, and the caption
   in the header says so.

   Only the summary is rewritten when a row moves, never the panel:
   re-rendering the whole control would close it under the reader's
   pointer, and the second of two families is exactly the tick they
   most often want to move straight after the first.

   DOM wiring, not pure logic -- `app.originControls`/`familyControls`/
   `nextSelection` (graph.js) and `pickerHtml`/`originsHtml`/
   `familiesHtml` (panel.js) already carry the testable parts, and
   `tests/webapp/picker.test.js` exercises them without a DOM. What is
   left here is reading the checkboxes and writing the summary back,
   which is why this file has no pure parts of its own to add a test
   for.

   `create()` takes the shared selection/filter state and the handful
   of app.js callbacks it has to reach across module boundaries for --
   see app.js's own call site for what each one does. */
"use strict";

window.CHITRAGUPTA_PICKERS = (function () {
  function create(options) {
    var DATA = options.DATA;
    var app = options.app;
    var state = options.state;
    var originsRow = options.originsRow;
    var familiesRow = options.familiesRow;
    var pruneChips = options.pruneChips;
    var onOriginsChanged = options.onOriginsChanged;
    var onFamiliesChanged = options.onFamiliesChanged;

    function renderOrigins() {
      originsRow.innerHTML = app.originsHtml(app.originControls(DATA, state.activeOrigins), DATA);
    }

    function renderFamilies() {
      familiesRow.innerHTML = app.familiesHtml(app.familyControls(DATA, state.activeFamilies));
    }

    function updateSummary(row, text) {
      var summary = row.querySelector(".picker-state");
      if (summary) { summary.textContent = text; }
    }

    originsRow.addEventListener("change", function (event) {
      var box = event.target.closest("input[data-origin]");
      if (!box) { return; }
      var next = app.nextSelection(state.activeOrigins, box.dataset.origin, box.checked);
      if (!next) {
        // The last class. An empty canvas reads as an empty corpus, so
        // the tick goes back rather than the graph going away.
        box.checked = true;
        return;
      }
      state.activeOrigins = next;
      state.ALL_LABELS = app.labelsWithOrigins(DATA, state.activeOrigins);
      updateSummary(
        originsRow,
        app.originsSummary(app.originControls(DATA, state.activeOrigins), DATA)
      );
      pruneChips();
      onOriginsChanged();
    });

    familiesRow.addEventListener("change", function (event) {
      var box = event.target.closest("input[data-family]");
      if (!box) { return; }
      var next = app.nextSelection(state.activeFamilies, box.dataset.family, box.checked);
      if (!next) {
        /* The last family. With neither on there is no graph at all --
           not even the union the rings used to walk -- so the tick goes
           back, the same refusal the origin axis makes. */
        box.checked = true;
        return;
      }
      state.activeFamilies = next;
      updateSummary(
        familiesRow, app.familiesSummary(app.familyControls(DATA, state.activeFamilies))
      );
      onFamiliesChanged(next);
    });

    /* Opening and shutting, for both pickers. A native <button> already
       answers Enter and Space, so this is the toggle, the escape hatch
       and the click-away -- the same three the type-ahead's popover has.
       Arrow-down opens and steps into the rows; inside the panel, Tab and
       Space are the browser's own and are left alone, which is why the
       rows are real checkboxes and not list items pretending to be. */
    function panelOf(row) { return row.querySelector(".picker-panel"); }

    /* Which picker is open, if either. Esc's policy lives in one place
       (`app.escapeAction`, with the type-ahead ahead of this and the
       latch behind it), so what the pickers owe that policy is this
       question and nothing more. */
    function openPicker() {
      var rows = [originsRow, familiesRow];
      for (var i = 0; i < rows.length; i++) {
        if (!panelOf(rows[i]).hidden) { return rows[i]; }
      }
      return null;
    }

    function anyPickerOpen() { return openPicker() !== null; }

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
      /* Esc is not handled here: it is one policy for the whole app, in
         app.js's capture-phase handler, because with a panel open it has
         to outrank releasing the latch and be outranked by closing the
         type-ahead. Two handlers would be two policies. */
      row.addEventListener("keydown", function (event) {
        if (event.key === "ArrowDown" && event.target.closest(".picker-summary")) {
          setOpen(row, true);
          var first = row.querySelector('.picker-row input:not([disabled])');
          if (first) { first.focus(); }
          event.preventDefault();
        }
      });
    });

    // app.js's one document click listener calls this for every click.
    function clickAway(target) {
      if (!target.closest(".picker")) { closeAllPickers(null); }
    }

    renderOrigins();
    renderFamilies();

    return {
      anyPickerOpen: anyPickerOpen,
      openPicker: openPicker,
      closeAllPickers: closeAllPickers,
      clickAway: clickAway,
    };
  }

  return { create: create };
})();
