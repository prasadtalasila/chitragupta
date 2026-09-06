/* The payload logic behind the canvas: which topics are visible, what
   cytoscape is handed, and what the type-ahead offers.

   Split out of app.js so it can be tested without a DOM and without
   cytoscape (tests/webapp/graph.test.js runs it under `node --test`).
   Nothing here derives an edge or a membership -- every number it reads
   was computed once by `chitragupta enrich` -- so the app still cannot
   disagree with the terminal views.

   Loaded as a classic script, not an ES module: `import` from file://
   is blocked as a cross-origin request, and the exported directory has
   to open with no server, forever. The tail below is what lets the same
   file be a browser global and a node require. */
"use strict";

(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.CHITRAGUPTA_APP = Object.assign(root.CHITRAGUPTA_APP || {}, api);
  }
})(typeof self !== "undefined" ? self : this, function () {
  /* Null prototypes on every table keyed by data-derived strings
     (topic labels, origins): on a plain object a topic literally
     labelled "__proto__" reads back Object.prototype -- truthy, so it
     slips past `||` fallbacks and has no .add -- which crashed the
     whole render (#636). */
  var ORIGIN_COLORS = Object.assign(Object.create(null), {
    seed: "#2e7d32",
    keyword: "#b8860b",
    both: "#00695c",
    emergent: "#1565c0",
  });
  var ORIGIN_LABELS = Object.assign(Object.create(null), {
    seed: "seed topic",
    keyword: "keyword topic",
    both: "seed + keyword topic",
    emergent: "emergent topic",
  });

  function byLabel(topics) {
    var index = Object.create(null);
    topics.forEach(function (t) { index[t.label] = t; });
    return index;
  }

  // Direct neighbours over both edge families, precomputed once: the
  // filter's "related" set is exactly this adjacency.
  function adjacency(data) {
    var neighbours = Object.create(null);
    function add(a, b) {
      (neighbours[a] = neighbours[a] || new Set()).add(b);
      (neighbours[b] = neighbours[b] || new Set()).add(a);
    }
    data.edges_overlap.forEach(function (e) { add(e.a, e.b); });
    data.edges_semantic.forEach(function (e) { add(e.a, e.b); });
    return neighbours;
  }

  function visibleLabels(data, selected, neighbours) {
    if (!selected.length) {
      return new Set(data.topics.map(function (t) { return t.label; }));
    }
    var visible = new Set(selected);
    selected.forEach(function (label) {
      (neighbours[label] || new Set()).forEach(function (n) { visible.add(n); });
    });
    return visible;
  }

  function nodeSize(topic) {
    return 22 + 9 * Math.sqrt(topic.members.length);
  }

  /* ---------- cutting the stored merge tree ----------

     The `hierarchy` the topic-graph stage wrote is an agglomerative
     merge tree over topic centroids, closest merge first, and a later
     merge is free to name an earlier merge's id rather than a topic
     (`{id: "node-4", a: "topic-53", b: "node-1"}`). Cutting it at a
     distance is union-find over the merges at or below that distance,
     with every internal id resolved back to the leaves underneath it.

     This is a *cut of a stored tree*, not a clustering: the same
     threshold always yields the same groups, and the app is reading
     what `--json` already exposes rather than deriving a partition the
     terminal cannot confirm. */

  function cutTree(hierarchy, topics, threshold) {
    var labels = topics.map(function (t) { return t.label; });
    var isLeaf = new Set(labels);
    var parent = Object.create(null);
    labels.forEach(function (label) { parent[label] = label; });

    function find(label) {
      while (parent[label] !== label) {
        parent[label] = parent[parent[label]];
        label = parent[label];
      }
      return label;
    }

    // A topic could be labelled "node-3" and collide with an internal
    // id, so a name that is a known topic label is always a leaf.
    var under = Object.create(null);
    function leavesOf(name) {
      return isLeaf.has(name) ? [name] : under[name] || [];
    }
    hierarchy.forEach(function (merge) {
      var members = leavesOf(merge.a).concat(leavesOf(merge.b));
      under[merge.id] = members;
      if (merge.distance <= threshold) {
        members.forEach(function (label) {
          var a = find(members[0]), b = find(label);
          if (a !== b) { parent[b] = a; }
        });
      }
    });

    var byRoot = Object.create(null);
    var groupOf = Object.create(null);
    var groups = [];
    topics.forEach(function (t) {
      var root = find(t.label);
      var group = byRoot[root];
      if (!group) {
        group = byRoot[root] = { id: "cluster-" + groups.length, members: [], label: "" };
        groups.push(group);
      }
      group.members.push(t.label);
      groupOf[t.label] = group.id;
    });
    groups.forEach(function (group) { group.label = groupLabel(group.members, topics); });
    return { groups: groups, groupOf: groupOf };
  }

  /* A group's label is a summary of its own members' labels: the topic
     carrying the most papers leads, and the rest are counted. Never a
     name the app invented -- a reader has to be able to find every word
     of it in the corpus. */
  function groupLabel(members, topics) {
    if (members.length === 1) { return members[0]; }
    var size = Object.create(null);
    topics.forEach(function (t) { size[t.label] = t.members.length; });
    var lead = members.slice().sort(function (x, y) {
      return (size[y] || 0) - (size[x] || 0) || (x < y ? -1 : 1);
    })[0];
    return lead + " +" + (members.length - 1);
  }

  /* The threshold that yields as close to `target` groups as the tree
     allows. Every distinct merge distance is a candidate cut and there
     are at most one per topic, so this walks them rather than
     bisecting: at 131 topics it is 130 comparisons, once per slider
     release. The target is a target -- a tree that never joins an
     outlying topic cannot reach one group, and says so by returning the
     nearest cut rather than pretending. */
  function thresholdForGroups(hierarchy, topics, target) {
    var best = 0;
    var bestMiss = Math.abs(topics.length - target);
    hierarchy.forEach(function (merge) {
      var miss = Math.abs(cutTree(hierarchy, topics, merge.distance).groups.length - target);
      if (miss < bestMiss) { bestMiss = miss; best = merge.distance; }
    });
    return best;
  }

  // ---------- drawing ----------

  function topicNode(t, selected, parentId) {
    var node = {
      group: "nodes",
      data: {
        id: t.label,
        label: t.label,
        origin: t.origin,
        color: ORIGIN_COLORS[t.origin] || ORIGIN_COLORS.emergent,
        size: nodeSize(t),
        picked: selected.indexOf(t.label) >= 0 ? 1 : 0,
      },
    };
    if (parentId) { node.data.parent = parentId; }
    return node;
  }

  /* What the reader is looking at, resolved once: which groups have
     enough visible members to be worth drawing as a group at all, and
     for each visible topic, the id its edges should attach to. A group
     of one is drawn bare either way -- a box around a single topic, or
     a meta-node standing for one node already on the canvas, both cost
     a nesting level and say nothing. */
  function resolveView(data, visible, view) {
    var cut = view && view.cut;
    var collapsed = (view && view.collapsed) || new Set();
    var shown = [];
    var drawnAs = Object.create(null);
    data.topics.forEach(function (t) {
      if (visible.has(t.label)) { drawnAs[t.label] = t.label; }
    });
    if (!cut) { return { groups: [], drawnAs: drawnAs, collapsedIds: new Set() }; }
    var collapsedIds = new Set();
    cut.groups.forEach(function (group) {
      var members = group.members.filter(function (label) { return visible.has(label); });
      if (members.length < 2) { return; }
      shown.push({ group: group, members: members });
      if (collapsed.has(group.id)) {
        collapsedIds.add(group.id);
        members.forEach(function (label) { drawnAs[label] = group.id; });
      }
    });
    return { groups: shown, drawnAs: drawnAs, collapsedIds: collapsedIds };
  }

  function groupNodes(shown, collapsedIds) {
    return shown.map(function (entry) {
      var isCollapsed = collapsedIds.has(entry.group.id);
      return {
        group: "nodes",
        data: {
          id: entry.group.id,
          label: entry.group.label,
          isGroup: isCollapsed ? 0 : 1,
          collapsed: isCollapsed ? 1 : 0,
          count: entry.members.length,
          size: 54 + 11 * Math.sqrt(entry.members.length),
        },
      };
    });
  }

  /* One edge per (family, endpoint pair) once anything is collapsed.
     Width tracks the strongest constituent rather than their sum, so a
     bundle of weak links cannot outdraw one strong one, and `pairs`
     keeps every constituent reachable so the panel can name them. The
     two families are bundled separately and never fused: a bundle
     counting shared papers together with cosine nearness would be the
     one number this design refuses to compute. */
  function bundleEdges(data, drawnAs, collapsedIds) {
    var bundles = Object.create(null);
    var order = [];
    function fold(family, i, a, b, width) {
      var source = drawnAs[a], target = drawnAs[b];
      if (!source || !target || source === target) { return; }
      var key = family + " " + source + " " + target;
      var bundle = bundles[key];
      if (!bundle) {
        bundle = bundles[key] = {
          group: "edges",
          data: {
            id: "bd-" + order.length, source: source, target: target,
            family: family, bundled: 1, count: 0, width: 0, pairs: [],
          },
        };
        order.push(bundle);
      }
      bundle.data.count += 1;
      bundle.data.width = Math.max(bundle.data.width, width);
      bundle.data.pairs.push({ family: family, index: i });
    }
    data.edges_overlap.forEach(function (e, i) {
      fold("overlap", i, e.a, e.b, 1.5 + 6 * e.overlap_coeff);
    });
    data.edges_semantic.forEach(function (e, i) {
      fold("semantic", i, e.a, e.b, 1 + 3 * e.similarity);
    });
    // An edge between two topics that are both drawn as themselves is
    // not a bundle: hand it back in its plain form, so nothing changes
    // for the part of the graph the reader has expanded.
    return order.map(function (bundle) {
      if (bundle.data.count > 1 || collapsedIds.has(bundle.data.source) ||
          collapsedIds.has(bundle.data.target)) {
        return bundle;
      }
      var pair = bundle.data.pairs[0];
      return {
        group: "edges",
        data: {
          id: (pair.family === "overlap" ? "ov-" : "se-") + pair.index,
          source: bundle.data.source, target: bundle.data.target,
          family: pair.family, width: bundle.data.width, index: pair.index,
        },
      };
    });
  }

  /* ---------- placing a cut on the canvas ----------

     A deterministic nested circle rather than a force layout, for the
     reason the static page already gives for its circle: it renders
     identically every run, and a stochastic layout would make the same
     exported directory draw differently on two openings. cose is also
     simply bad at compound graphs -- it treats a parent as one body and
     its children as another system, and an expanded group comes out
     piled on itself with its neighbours sitting on top of the box.

     Groups go round one circle, each group's own topics round a smaller
     one inside it, and each slot's share of the big circle is
     proportional to how much room it needs. */

  var CHILD_SPACING = 96;
  /* Two neighbours on a ring of radius R, each needing radius r, are
     2*R*sin(pi/n) apart, so R has to be at least r/sin(pi/n) for them
     not to touch. Writing R as GAP * sum(r) / pi makes the worst case
     n = 2 (GAP >= pi/2), and every larger ring wants less -- so one
     constant a shade above pi/2 holds for every group count. */
  var GROUP_GAP = 1.6;

  function radiusFor(count, size) {
    if (count <= 1) { return size / 2; }
    return Math.max(size, (CHILD_SPACING * count) / (2 * Math.PI));
  }

  // What the top-level circle has to carry: one entry per collapsed
  // group, per expanded group, and per topic outside any group, each
  // with the radius it needs.
  function topLevel(elements) {
    var children = Object.create(null);
    elements.forEach(function (el) {
      if (el.group === "nodes" && el.data.parent) {
        (children[el.data.parent] = children[el.data.parent] || []).push(el);
      }
    });
    var items = [];
    elements.forEach(function (el) {
      if (el.group !== "nodes" || el.data.parent) { return; }
      var kids = children[el.data.id] || [];
      items.push({
        id: el.data.id,
        children: kids,
        radius: el.data.isGroup
          ? radiusFor(kids.length, maxSize(kids)) + maxSize(kids) / 2
          : (el.data.size || 40) / 2,
      });
    });
    return items;
  }

  function maxSize(nodes) {
    return nodes.reduce(function (big, n) { return Math.max(big, n.data.size || 40); }, 40);
  }

  function ring(items, cx, cy, at) {
    var total = items.reduce(function (sum, item) { return sum + item.radius; }, 0);
    var widest = items.reduce(function (big, item) { return Math.max(big, item.radius); }, 0);
    var radius = items.length === 1 ? 0
      : Math.max(widest, (GROUP_GAP * total) / Math.PI);
    var angle = 0;
    items.forEach(function (item) {
      var share = total ? (2 * Math.PI * item.radius) / total : 0;
      var mid = angle + share / 2;
      angle += share;
      var x = cx + radius * Math.cos(mid);
      var y = cy + radius * Math.sin(mid);
      if (item.children.length) {
        placeChildren(item, x, y, at);
      } else {
        at[item.id] = { x: x, y: y };
      }
    });
  }

  function placeChildren(item, cx, cy, at) {
    var radius = radiusFor(item.children.length, maxSize(item.children));
    item.children.forEach(function (child, i) {
      var angle = (2 * Math.PI * i) / item.children.length;
      at[child.data.id] = item.children.length === 1
        ? { x: cx, y: cy }
        : { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) };
    });
  }

  function positionsFor(elements) {
    var at = Object.create(null);
    ring(topLevel(elements), 0, 0, at);
    return at;
  }

  /* Where an expanded group ended up, and how much room it takes.

     A compound parent has no position of its own -- cytoscape derives
     its box from its children -- so this is the only way to ask where a
     group is. It exists for the tests, deliberately: asserting that a
     group's topics land inside it, and that two groups do not overlap,
     otherwise means re-deriving this radius arithmetic in the test,
     which would then agree with a broken layout as readily as a working
     one. Null for a group with nothing placed under it. */
  function groupCentre(elements, at, id) {
    var kids = elements.filter(function (el) {
      return el.group === "nodes" && el.data.parent === id;
    });
    var placed = kids.map(function (kid) { return at[kid.data.id]; });
    if (!placed.length) { return null; }
    var cx = placed.reduce(function (sum, p) { return sum + p.x; }, 0) / placed.length;
    var cy = placed.reduce(function (sum, p) { return sum + p.y; }, 0) / placed.length;
    return {
      x: cx, y: cy,
      radius: radiusFor(kids.length, maxSize(kids)) + maxSize(kids) / 2,
    };
  }

  function elementsFor(data, visible, selected, view) {
    var resolved = resolveView(data, visible, view);
    var els = groupNodes(resolved.groups, resolved.collapsedIds);
    var parentOf = Object.create(null);
    resolved.groups.forEach(function (entry) {
      if (resolved.collapsedIds.has(entry.group.id)) { return; }
      entry.members.forEach(function (label) { parentOf[label] = entry.group.id; });
    });
    data.topics.forEach(function (t) {
      if (!visible.has(t.label)) { return; }
      if (resolved.drawnAs[t.label] !== t.label) { return; }
      els.push(topicNode(t, selected, parentOf[t.label]));
    });
    return els.concat(bundleEdges(data, resolved.drawnAs, resolved.collapsedIds));
  }

  function candidatesFor(data, selected, query) {
    var needle = query.trim().toLowerCase();
    if (!needle) { return []; }
    var out = [];
    data.topics.forEach(function (t) {
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

  function findMember(data, citekey) {
    for (var i = 0; i < data.topics.length; i++) {
      var members = data.topics[i].members;
      for (var j = 0; j < members.length; j++) {
        if (members[j].citekey === citekey) { return members[j]; }
      }
    }
    return null;
  }

  return {
    ORIGIN_COLORS: ORIGIN_COLORS,
    ORIGIN_LABELS: ORIGIN_LABELS,
    byLabel: byLabel,
    adjacency: adjacency,
    visibleLabels: visibleLabels,
    nodeSize: nodeSize,
    elementsFor: elementsFor,
    cutTree: cutTree,
    positionsFor: positionsFor,
    groupCentre: groupCentre,
    thresholdForGroups: thresholdForGroups,
    candidatesFor: candidatesFor,
    findMember: findMember,
  };
});
