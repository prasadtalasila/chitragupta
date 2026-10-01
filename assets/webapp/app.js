/* The topic-graph app: pure renderer of window.CHITRAGUPTA_TOPICS,
   which data.js (written by `corpus discover --app`) assigns. It
   computes no edge and no membership -- everything drawn here was
   derived once by `chitragupta enrich` -- so the app cannot disagree
   with the terminal views. Colour vocabulary mirrors style.css.

   What is left in this file is the wiring between the modules: the
   payload check, `state` (the selection, filter and view fields every
   DOM module reaches across the split for), the resolution and focus
   controls, the hierarchy and uncovered-seed sections, and the
   document-level Esc and click-away handlers. The logic those DOM
   events call lives in graph.js (payload -> what is visible, what
   cytoscape is handed) and panel.js (data -> HTML). The DOM wiring is
   four modules, each taking `state` and a few callbacks rather than
   reading this file's variables directly: search.js (type-ahead and
   chips) and pickers.js (the origin and family widgets), split out by
   #857, and canvas.js (cytoscape, layout, focus, gestures) and
   sidepanel.js (every panel writer, the path buttons and the
   disagreement grid), split out once this file was still twice the C2
   limit. cy_style.js holds the cytoscape stylesheet as data.
   index.html loads all of them before this file, and everything except
   the DOM wiring is testable without a browser and tested under
   tests/webapp/. */
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
      ". Re-export it with `chitragupta corpus discover --app DIR`.";
    notice.hidden = false;
    return;
  }

  var topicsByLabel = app.byLabel(DATA.topics);

  /* The state every DOM module mutates as well as this file. A plain
     object rather than module-level `var`s, so the extracted modules
     can share it by reference instead of each needing its own copy
     wired back here.

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
     order is the legend's.

     Grouping. The app opens at a cut of the stored merge tree yielding
     roughly eight groups, all collapsed, because 131 topics drawn loose
     is a hairball and a reader who has to find a control first has
     already met it. `cut` is null when the reader slides the
     resolution all the way down, which is the pre-grouping view.

     The ego view. With topics pinned the context stays on the canvas,
     dimmed, rather than being deleted -- removing it costs the reader
     their sense of where they are in a corpus this size. `maxHops`
     bounds the ring view: one hop answers "what is next to this", two
     answers "what would a chapter around this have to cover".

     `expanded`: papers on the canvas, opt-in and capped -- a paper in
     three topics is visibly a bridge, and 131 topics fully expanded is
     several hundred nodes and thousands of lines.

     `latched`: sticky node focus, the id latched by a click, or null.
     A hover previews the same paint transiently and reverts to this on
     `mouseout`; the canvas's `redraw()` wipes every class each call (it
     removes and re-adds all elements), so it repaints this after every
     rebuild, or releases it if the id no longer exists. */
  var state = {
    selected: [],
    activeOrigins: new Set(app.shippedOrigins(DATA)),
    activeFamilies: new Set(app.shippedFamilies(DATA)),
    cut: null,
    collapsed: new Set(),
    groupsById: Object.create(null),
    context: "dim",
    maxHops: 2,
    expanded: new Set(),
    latched: null,
  };
  state.ALL_LABELS = app.labelsWithOrigins(DATA, state.activeOrigins);
  // The opening cut's target group count -- "Grouping" above has why.
  var OPENING_GROUPS = 8;

  function families() {
    return app.FAMILY_CLASSES.filter(function (family) {
      return state.activeFamilies.has(family);
    });
  }

  // ---------- the canvas and the side panel ----------

  /* Each calls into the other -- a gesture fills the panel, a panel
     link moves the latch and a path lights its hops -- so the one
     created first reaches the second through a getter rather than a
     reference that does not exist yet. */
  var canvas = window.CHITRAGUPTA_CANVAS.create({
    DATA: DATA, app: app, state: state, families: families,
    panel: function () { return panel; },
  });
  var panel = window.CHITRAGUPTA_SIDEPANEL.create({
    DATA: DATA, app: app, state: state, topicsByLabel: topicsByLabel,
    canvas: function () { return canvas; },
  });
  var redraw = canvas.redraw;

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
    state.cut = step > 0 ? app.cutTree(DATA.hierarchy, DATA.topics, distances[step - 1]) : null;
    state.groupsById = Object.create(null);
    var groupable = 0;
    if (state.cut) {
      state.cut.groups.forEach(function (group) {
        state.groupsById[group.id] = group;
        if (group.members.length > 1) { groupable += 1; }
      });
    }
    if (!keepCollapsed) {
      state.collapsed = new Set(state.cut ? state.cut.groups.map(function (group) { return group.id; }) : []);
    }
    cutReadout.textContent = state.cut
      ? state.cut.groups.length + " groups (" + groupable + " with more than one topic)"
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
      state.collapsed = new Set(Object.keys(state.groupsById));
      redraw();
    });
    expandAll.addEventListener("click", function () {
      state.collapsed = new Set();
      redraw();
    });
    applyCut(Number(cutControl.value), false);
  })();
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
    panel.showPathButtons();
  }

  hopsControl.addEventListener("change", function () {
    state.maxHops = Number(hopsControl.value);
    redraw();
  });
  hideContext.addEventListener("change", function () {
    state.context = hideContext.checked ? "hide" : "dim";
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
    showPair: panel.showPair, showTopic: panel.showTopic,
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
      var shown = panel.familyShown();
      if (shown && !next.has(shown)) { panel.showHelp(); }
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
    var action = app.escapeAction(search.isOpen(), state.latched, pickers.anyPickerOpen());
    if (action === "closePicker") {
      // Focus goes back to the button that opened it: without this it
      // is left on a checkbox inside a hidden panel, and the next Tab
      // starts from nowhere the reader can see.
      var row = pickers.openPicker();
      pickers.closeAllPickers(null);
      row.querySelector(".picker-summary").focus();
      return;
    }
    if (action === "releaseLatch") { canvas.releaseLatch(); }
  }, true);

  showControlsForSelection();
  redraw();
})();
