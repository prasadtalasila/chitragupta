/* The side panel: every writer that fills it, the links inside it, and
   the two controls whose whole answer is a panel -- the path buttons
   and the disagreement grid.

   DOM wiring, not pure logic, split out of app.js beside canvas.js for
   the same C2 reason #857 split search.js and pickers.js. The HTML
   itself is panel.js's, which `tests/webapp/panel.test.js` exercises
   without a DOM; what is left here is choosing which string goes into
   `#detail` and keeping track of what the panel is showing, which is
   why this file adds no node test of its own.

   `create()` takes the shared selection/filter/view `state` and the
   canvas, for the two things a panel write does to it: moving the
   latch to a topic the reader followed a link to, and lighting the
   path the panel describes. */
"use strict";

window.CHITRAGUPTA_SIDEPANEL = (function () {
  /* The brokerage reading, under the papers rather than instead of
     them: "is this topic a theme or a bridge" is the survey-scoping
     question, and it is answered per edge family because a topic that
     brokers over shared papers but not over vocabulary is a different
     animal from one that does the reverse. */
  function egoSection(app, DATA, topic) {
    return app.egoHtml(topic.label, {
      overlap: app.statsFor(DATA, topic, "overlap"),
      semantic: app.statsFor(DATA, topic, "semantic"),
    });
  }

  function create(options) {
    var DATA = options.DATA;
    var app = options.app;
    var state = options.state;
    var topicsByLabel = options.topicsByLabel;
    var canvas = options.canvas;

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
      detail.innerHTML = app.topicHtml(DATA, topic) + egoSection(app, DATA, topic);
    }

    function showEdge(family, index) {
      var html = app.edgeHtml(DATA, family, index);
      if (!html) { showHelp(); return; }
      clearHint();
      detail.innerHTML = html;
      panelFamily = family;
    }

    function showGroup(id) {
      if (!state.groupsById[id]) { return; }
      clearHint();
      detail.innerHTML = app.groupHtml(state.groupsById[id]);
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

    function wirePanelLinks() {
      // The panel's own topic links are the accessible route to a node's
      // neighbourhood -- `tabindex` (panel.js) makes them reachable, and a
      // click and an Enter/Space both count as activating one.
      function activatePanelLink(target) {
        var goto_ = target.closest("a[data-goto]");
        if (goto_) {
          var label = goto_.getAttribute("data-goto");
          showTopic(label);
          canvas().setLatch(label);
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
    }
    wirePanelLinks();

    // ---------- the two families: paths, and clusters ----------

    /* The two controls whose whole answer is a panel, wired once at
       creation. Their own function so that `create` reads as the panel's
       writers; they share its closure, and the token and the "what is
       shown" fields above stay the one copy every writer clears. */
    function wireFamilyControls() {
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
        canvas().highlightPath(result);
      }

      Object.keys(pathButtons).forEach(function (family) {
        pathButtons[family].addEventListener("click", function () { showPath(family); });
      });

      /* A path is a question about a pair and about one family, so a
         button appears at two pinned topics and only while its own family
         is on. Offering "path over semantic nearness" over edges the
         reader has just taken off the canvas would answer a question
         about a graph they are not looking at. */
      function showPathButtons() {
        Object.keys(pathButtons).forEach(function (family) {
          pathButtons[family].hidden = state.selected.length !== 2 || !state.activeFamilies.has(family);
        });
      }

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

      return { showPathButtons: showPathButtons };
    }
    var familyControls = wireFamilyControls();

    return {
      showHelp: showHelp,
      say: say,
      showTopic: showTopic,
      showEdge: showEdge,
      showGroup: showGroup,
      showPaper: showPaper,
      showBundle: showBundle,
      showPair: showPair,
      showPathButtons: familyControls.showPathButtons,
      // The family that owns what is on the panel now, if one does --
      // read by app.js when the reader switches a family off.
      familyShown: function () { return panelFamily; },
    };
  }

  return { create: create };
})();
