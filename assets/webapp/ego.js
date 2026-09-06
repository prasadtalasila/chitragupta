/* The egocentric view: how far each topic is from what the reader
   pinned, which family reached it, how that neighbourhood is shaped,
   and where the rings go.

   Everything here is **view-derived** -- it changes the moment the
   reader clicks something else, it is computed in this browser, and
   `--json` will not confirm it. That is the split
   `docs/TOPIC-DISCOVERY-GRAPH.md` §2 records: the corpus numbers stay
   the corpus's, and anything about the current selection is the
   reader's own view, labelled as such wherever it is shown.

   Split out of graph.js rather than added to it because it is a
   different job: graph.js turns a payload into elements, this turns a
   selection into a reading of the neighbourhood around it. Tested
   without a DOM by tests/webapp/ego.test.js. */
"use strict";

(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.CHITRAGUPTA_APP = Object.assign(root.CHITRAGUPTA_APP || {}, api);
  }
})(typeof self !== "undefined" ? self : this, function () {
  var RING_GAP = 240;
  var ROOT_RADIUS = 70;
  function edgesOf(data, family) {
    return family === "overlap" ? data.edges_overlap : data.edges_semantic;
  }

  function weightOf(family, edge) {
    return family === "overlap" ? edge.overlap_coeff : edge.similarity;
  }

  /* Adjacency over just the families asked for, with weights. Built per
     call rather than cached: it is a few hundred edges, and a stale
     copy after the reader turns a family off would be a wrong picture
     rather than a slow one. */
  function weighted(data, families) {
    var near = Object.create(null);
    families.forEach(function (family) {
      edgesOf(data, family).forEach(function (edge) {
        var w = weightOf(family, edge);
        (near[edge.a] = near[edge.a] || Object.create(null))[edge.b] = w;
        (near[edge.b] = near[edge.b] || Object.create(null))[edge.a] = w;
      });
    });
    return near;
  }

  /* Hop distance from the pinned set, over the enabled families. One
     hop answers "what is next to this"; two answers "what would a
     chapter around this have to cover". A topic the selection cannot
     reach has no entry at all -- an absent distance is the honest
     answer, where a large one would draw it on an outer ring as though
     it were merely far. */
  function hopsFrom(data, roots, families) {
    var near = weighted(data, families);
    var depth = Object.create(null);
    var frontier = [];
    roots.forEach(function (label) {
      if (depth[label] === undefined) { depth[label] = 0; frontier.push(label); }
    });
    while (frontier.length) {
      var next = [];
      frontier.forEach(function (label) {
        Object.keys(near[label] || {}).forEach(function (other) {
          if (depth[other] === undefined) {
            depth[other] = depth[label] + 1;
            next.push(other);
          }
        });
      });
      frontier = next;
    }
    return depth;
  }

  /* The emphasis set: everything the reader's hop control reaches,
     the pinned topics included. The same bound governs the rings, so a
     topic can never be placed on a ring and drawn as background at the
     same time. */
  function withinHops(hops, maxHops) {
    return new Set(Object.keys(hops).filter(function (label) {
      return hops[label] <= maxHops;
    }));
  }

  /* Which family reaches each direct neighbour of the pinned set:
     "overlap", "semantic", or "both". A neighbour reached only through
     a shared paper is a different object from one reached only through
     cosine nearness, and this is what keeps them apart on the ring. */
  function reachedVia(data, roots) {
    var pinned = new Set(roots);
    var via = Object.create(null);
    function mark(label, family) {
      if (pinned.has(label)) { return; }
      via[label] = via[label] && via[label] !== family ? "both" : family;
    }
    ["overlap", "semantic"].forEach(function (family) {
      edgesOf(data, family).forEach(function (edge) {
        if (pinned.has(edge.a)) { mark(edge.b, family); }
        if (pinned.has(edge.b)) { mark(edge.a, family); }
      });
    });
    return via;
  }

  /* Burt's brokerage measures over one edge family, plus the plain ego
     density, all weighted by tie strength.

     Read together they answer "is this topic a theme or a bridge": a
     dense neighbourhood whose members all cite each other is a coherent
     theme, and one whose members never touch is a broker -- which is
     where a survey section earns its keep.

     Per family and never pooled. A topic that brokers over shared
     papers but not over vocabulary is a methods topic; the reverse is
     usually a terminology split worth naming in the draft, and one
     fused figure would show neither.

     Null, not NaN, wherever the arithmetic has no answer: NaN passes
     every guard that tests for a number and satisfies no comparison. */
  function egoStats(data, label, family) {
    var near = weighted(data, [family]);
    var ties = near[label] || Object.create(null);
    var alters = Object.keys(ties);
    if (!alters.length) {
      return { alters: 0, density: null, effectiveSize: 0, constraint: null };
    }
    var total = alters.reduce(function (sum, j) { return sum + ties[j]; }, 0);
    var p = Object.create(null);
    alters.forEach(function (j) { p[j] = ties[j] / total; });

    // Density: the alters' own edges over the pairs they could form.
    var among = 0;
    alters.forEach(function (j, i) {
      alters.slice(i + 1).forEach(function (k) {
        if ((near[j] || {})[k] !== undefined) { among += 1; }
      });
    });
    var pairs = (alters.length * (alters.length - 1)) / 2;

    // p_qj: q's tie to j as a share of everything q spends, which is
    // what makes an alter with few other ties constrain the ego more.
    function share(q, j) {
      var qs = near[q] || Object.create(null);
      var spent = Object.keys(qs).reduce(function (sum, k) { return sum + qs[k]; }, 0);
      return spent ? (qs[j] || 0) / spent : 0;
    }
    // m_jq: q's share of j's strongest single tie (Burt's marginal).
    function marginal(j, q) {
      var js = near[j] || Object.create(null);
      var strongest = Object.keys(js).reduce(function (big, k) {
        return Math.max(big, js[k]);
      }, 0);
      return strongest ? (js[q] || 0) / strongest : 0;
    }

    var effectiveSize = alters.reduce(function (sum, j) {
      var redundancy = alters.reduce(function (r, q) {
        return q === j ? r : r + p[q] * marginal(j, q);
      }, 0);
      return sum + (1 - redundancy);
    }, 0);
    var constraint = alters.reduce(function (sum, j) {
      var indirect = alters.reduce(function (c, q) {
        return q === j ? c : c + p[q] * share(q, j);
      }, 0);
      return sum + Math.pow(p[j] + indirect, 2);
    }, 0);

    return {
      alters: alters.length,
      density: pairs ? among / pairs : null,
      effectiveSize: effectiveSize,
      constraint: constraint,
    };
  }

  /* Concentric rings by hop distance: the pinned set at the centre,
     hop 1 round it, hop 2 outside that. Deterministic, no physics --
     the extension of the argument the static page already makes for
     drawing a circle rather than settling a simulation.

     Only the first ring is typed by family. Past one hop a topic is
     reached by a path rather than an edge, and labelling a path with
     one family would be a claim about how the reader got there that
     the graph does not support. */
  function ringPositions(data, roots, hops, maxHops) {
    var via = reachedVia(data, roots);
    var rings = Object.create(null);
    Object.keys(hops).forEach(function (label) {
      var depth = hops[label];
      if (depth > maxHops) { return; }
      (rings[depth] = rings[depth] || []).push(label);
    });
    var at = Object.create(null);
    Object.keys(rings).forEach(function (depth) {
      var members = rings[depth].slice().sort();
      if (Number(depth) === 0) {
        placeRoots(members, at);
      } else if (Number(depth) === 1) {
        placeTyped(members, via, RING_GAP, at);
      } else {
        placeArc(members, { from: 0, to: 360 }, Number(depth) * RING_GAP, at);
      }
    });
    return at;
  }

  /* Where the dimmed context goes: everything the ego view does not
     reach within `maxHops`, on one far ring outside the rings that do.
     Drawn rather than deleted so the reader can see how much of the
     corpus their selection is *not* -- which is the whole argument for
     dimming instead of filtering -- and sorted so the same selection
     always parks it in the same place. */
  function contextRing(labels, hops, maxHops) {
    var outside = labels.filter(function (label) {
      return hops[label] === undefined || hops[label] > maxHops;
    }).sort();
    var at = Object.create(null);
    placeArc(outside, { from: 0, to: 360 }, (maxHops + 1.6) * RING_GAP, at);
    return at;
  }

  function placeRoots(members, at) {
    if (members.length === 1) {
      at[members[0]] = { x: 0, y: 0 };
      return;
    }
    placeArc(members, { from: 0, to: 360 }, ROOT_RADIUS, at);
  }

  /* Three contiguous arcs, in the order overlap -> both -> semantic,
     each as wide as its share of the ring. Fixed quadrants were the
     first attempt and they crowd: on a real corpus a topic can have
     twenty neighbours that both families reach and two that only one
     does, and a fixed 40-degree wedge piles the twenty on top of each
     other. Proportional arcs keep the three kinds separated -- which is
     the whole point -- and let the ring breathe.

     The overlap arc is centred on zero degrees, so with a balanced ring
     shared-paper neighbours land on the right and vocabulary
     neighbours on the left, and the reader keeps a stable sense of
     which side is which. */
  function placeTyped(members, via, radius, at) {
    var kinds = ["overlap", "both", "semantic"].map(function (family) {
      return members.filter(function (label) {
        return (via[label] || "both") === family;
      });
    });
    var span = function (mine) { return (360 * mine.length) / members.length; };
    var start = -span(kinds[0]) / 2;
    kinds.forEach(function (mine) {
      placeArc(mine, { from: start, to: start + span(mine) }, radius, at);
      start += span(mine);
    });
  }

  /* Cell-centred: each member sits in the middle of its own slice of
     the arc rather than on the endpoints. That keeps two neighbouring
     arcs from putting a node each on the same boundary angle, and
     makes a one-member arc land in its middle without a special case. */
  function placeArc(members, arc, radius, at) {
    if (!members.length) { return; }
    var step = (arc.to - arc.from) / members.length;
    members.forEach(function (label, i) {
      var radians = ((arc.from + step * (i + 0.5)) * Math.PI) / 180;
      at[label] = {
        x: radius * Math.cos(radians),
        y: radius * Math.sin(radians),
      };
    });
  }

  return {
    hopsFrom: hopsFrom,
    withinHops: withinHops,
    reachedVia: reachedVia,
    egoStats: egoStats,
    ringPositions: ringPositions,
    contextRing: contextRing,
  };
});
