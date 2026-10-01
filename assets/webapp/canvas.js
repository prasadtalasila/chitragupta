/* The canvas: the cytoscape instance, what is drawn on it and how it is
   laid out, the click-to-latch and hover-to-preview focus, the edge
   tooltip, and every gesture on a node or an edge.

   DOM wiring, not pure logic, and split out of app.js for the same
   reason #857 split search.js and pickers.js: one file holding the
   canvas, the side panel and every control was over the C2 limit.
   What is drawn and where comes from graph.js and ego.js, which
   `tests/webapp/*.test.js` already exercises without a DOM; what is
   left here is handing it to cytoscape, which is why this file adds no
   node test of its own.

   `create()` takes the shared selection/filter/view `state` and the
   side panel, whose writers the gestures here call -- see app.js's own
   call site. The panel calls back into `setLatch` and `highlightPath`,
   so app.js creates the canvas first and hands the panel to it through
   a getter. */
"use strict";

window.CHITRAGUPTA_CANVAS = (function () {
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
  function paintFocus(cy, id) {
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

  function clearFocus(cy) {
    cy.batch(function () { cy.elements().removeClass("focused focus-near faded"); });
  }

  // ---------- the edge tooltip ----------

  // A DOM tooltip rather than a vendored positioning library: the
  // bridge pair is the fastest answer to "why is this edge here", and
  // it should not cost a click.
  function showTip(event, text) {
    var tip = document.getElementById("tip");
    // Position first, then reveal: showing it before placing it leaves a
    // tooltip stuck at the last position if anything about the event is
    // not what was expected.
    tip.style.left = event.renderedPosition.x + 14 + "px";
    tip.style.top = event.renderedPosition.y + 14 + "px";
    tip.textContent = text;
    tip.hidden = false;
  }

  function hideTip() {
    document.getElementById("tip").hidden = true;
  }

  function create(options) {
    var DATA = options.DATA;
    var app = options.app;
    var state = options.state;
    var families = options.families;
    var panel = options.panel;
    var hoverTimer = null;

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
        cut: state.cut, collapsed: state.collapsed, context: state.context,
        all: state.ALL_LABELS, expanded: state.expanded, families: families(),
      };
    }

    /* One layout at a time. Two redraws in the same turn -- removing two
       chips at once does exactly that -- leave the first layout's
       viewport tween running after its elements are gone, and it lands on
       top of the second layout's fit: the canvas ends up framed for a
       graph that no longer exists. */
    var running = null;

    function run(layout) {
      if (running) { running.stop(); }
      running = cy.layout(layout);
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
        ? app.restrictTo(app.withinHops(hops, state.maxHops), state.ALL_LABELS)
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
        layOutRings(hops);
      } else if (state.cut) {
        layOutGroups(elements);
      } else {
        layOutLoose();
      }
    }

    // Rings by hop distance from what is pinned: deterministic, and an
    // extension of the "a circle is legible" argument rather than a
    // contradiction of it. elementsFor has already suspended the cut,
    // so there are no boxes to lay out here.
    function layOutRings(hops) {
      var at = app.ringPositions(DATA, state.selected, hops, state.maxHops, families());
      var outside = app.contextRing(
        cy.nodes().map(function (n) { return n.id(); }), hops, state.maxHops
      );
      run({
        name: "preset",
        positions: function (n) { return at[n.id()] || outside[n.id()]; },
        // Object constancy: a node that teleports when the selection
        // changes makes the reader re-parse the whole picture.
        animate: true, animationDuration: 350,
        fit: true, padding: 40,
      });
    }

    // Groups round one circle, each group's topics round a smaller one
    // inside it. Deterministic, and cose is bad at compounds -- graph.js's
    // own comment has the reasoning.
    function layOutGroups(elements) {
      var grouped = app.positionsFor(elements);
      // `fit` inside the layout, not a `cy.fit()` after `.run()`: with
      // `animate` on, run() returns before the nodes have moved, and
      // fitting there frames the positions they are leaving.
      run({
        name: "preset", positions: function (n) { return grouped[n.id()]; },
        animate: true, animationDuration: 350, fit: true, padding: 40,
      });
    }

    // Ungrouped: a deterministic circle first, then cose refines from it
    // without re-randomising -- the same graph always lands in the same
    // place.
    function layOutLoose() {
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

    // What every path back to "no transient hover" repaints: the latch,
    // if it is still on the canvas, otherwise nothing -- and releasing it
    // cleanly if it just fell off (an origin filter, a collapsed group).
    function paintLatchOrClear() {
      if (state.latched && cy.$id(state.latched).length) {
        paintFocus(cy, state.latched);
      } else if (state.latched) {
        releaseLatch();
      } else {
        clearFocus(cy);
      }
    }

    function cancelHover() {
      if (hoverTimer) { window.clearTimeout(hoverTimer); hoverTimer = null; }
    }

    function releaseLatch() {
      cancelHover();
      state.latched = null;
      clearFocus(cy);
    }

    // Click toggles: the same node releases, a different node moves the
    // latch, and the decision itself is a pure function (tests/webapp/
    // graph.test.js) so the toggle/move/release cases don't depend on a
    // browser to check.
    function setLatch(id) {
      cancelHover();
      state.latched = app.nextLatch(state.latched, id);
      paintLatchOrClear();
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

    // ---------- gestures ----------

    /* Every gesture on a node, an edge or the background, registered once
       at creation. Its own function only so that `create` reads as the
       list of things the canvas does; the handlers share its closure. */
    function wireGestures() {
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
          panel().showPaper(app.citekeyOf(DATA, node.id()));
        } else if (node.data("isGroup") || node.data("collapsed")) {
          panel().showGroup(node.id());
        } else {
          panel().showTopic(node.id());
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
        if (state.expanded.has(node.id())) {
          state.expanded.delete(node.id());
        } else if (state.expanded.size >= app.EXPANSION_CAP) {
          // Say what happened rather than quietly drawing nothing.
          panel().say("At most " + app.EXPANSION_CAP + " topics can show their papers at " +
            "once — double-click one of the open ones to close it.");
          return;
        } else {
          state.expanded.add(node.id());
        }
        redraw();
        panel().showTopic(node.id());
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
          paintFocus(cy, id);
        }, 60);
      });
      cy.on("mouseout", "node", function () {
        cancelHover();
        paintLatchOrClear();
      });
      cy.on("tap", "edge", function (event) {
        var edge = event.target;
        if (edge.data("family") === "member") { return; }
        if (edge.data("bundled")) {
          panel().showBundle(edge.data("pairs"));
        } else {
          panel().showEdge(edge.data("family"), edge.data("index"));
        }
      });

      // Double-click is the expand/collapse gesture: on a meta-node it
      // opens that group in place, on a group's box it closes it again,
      // and the rest of the canvas keeps whatever state it had.
      cy.on("dbltap", "node", function (event) {
        var node = event.target;
        if (!node.data("isGroup") && !node.data("collapsed")) { return; }
        if (state.collapsed.has(node.id())) {
          state.collapsed.delete(node.id());
        } else {
          state.collapsed.add(node.id());
        }
        redraw();
      });
    }
    wireGestures();

    return {
      redraw: redraw,
      setLatch: setLatch,
      releaseLatch: releaseLatch,
      highlightPath: highlightPath,
    };
  }

  return { create: create };
})();
