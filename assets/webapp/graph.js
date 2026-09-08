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
  var api = typeof module === "object" && module.exports
    ? factory(require("./absence.js"))
    : factory(root.CHITRAGUPTA_APP);
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.CHITRAGUPTA_APP = Object.assign(root.CHITRAGUPTA_APP || {}, api);
  }
})(typeof self !== "undefined" ? self : this, function (absence) {
  /* Null prototypes on every table keyed by data-derived strings
     (topic labels, origins): on a plain object a topic literally
     labelled "__proto__" reads back Object.prototype -- truthy, so it
     slips past `||` fallbacks and has no .add -- which crashed the
     whole render (#636). */
  var ORIGIN_COLORS = Object.assign(Object.create(null), {
    seed: "#2e7d32",
    keyword: "#b8860b",
    corroborated: "#00695c",
    emergent: "#1565c0",
  });
  var ORIGIN_LABELS = Object.assign(Object.create(null), {
    seed: "seed topic",
    keyword: "keyword topic",
    corroborated: "corroborated topic",
    emergent: "emergent topic",
  });
  /* The reader's order, not the machine's: how much of a human is in
     the topic, most first. The origin picker, the legend and the CLI's
     --origins help all follow it. */
  var ORIGIN_CLASSES = ["seed", "keyword", "corroborated", "emergent"];

  /* The two edge families, in the legend's order, with the words the
     reader was actually shown. `overlap` and `semantic` are field names
     in data.js; nobody outside this file needs to see them, and the
     picker rows carry the legend's own key -- a solid line and a dashed
     one -- so a row can be matched to a line on the canvas.

     Never fused, here as everywhere: this table is what lets the reader
     ask one family's question at a time, which the terminal's
     `discover --path --family` has always allowed and the app did not. */
  var FAMILY_CLASSES = ["overlap", "semantic"];
  var FAMILY_LABELS = Object.assign(Object.create(null), {
    overlap: "shares papers",
    semantic: "semantically near",
  });
  var FAMILY_KEYS = Object.assign(Object.create(null), {
    overlap: "solid",
    semantic: "dashed",
  });

  function familyEdges(data, family) {
    return (family === "overlap" ? data.edges_overlap : data.edges_semantic) || [];
  }

  /* Which families this corpus actually has edges for, and so which the
     app opens with. A family with no edges anywhere is not something
     the reader switched off, and a picker row that merely does nothing
     when ticked tells them neither -- the same distinction the origin
     row draws for a class `--origins` left out.

     A payload with no edges at all offers both: there is nothing to
     filter, and every row dead with no row saying why is worse. */
  function shippedFamilies(data) {
    var held = FAMILY_CLASSES.filter(function (family) {
      return familyEdges(data, family).length > 0;
    });
    return held.length ? held : FAMILY_CLASSES.slice();
  }

  /* One row per family for the header: its human name, its legend key,
     how many edges it holds here, whether it holds any at all, and
     whether it is on. */
  function familyControls(data, active) {
    var shipped = shippedFamilies(data);
    return FAMILY_CLASSES.map(function (family) {
      return {
        family: family,
        name: FAMILY_LABELS[family],
        key: FAMILY_KEYS[family],
        count: familyEdges(data, family).length,
        shipped: shipped.indexOf(family) >= 0,
        checked: active.has(family),
      };
    });
  }

  /* The families a view asks for, with an absent carrier meaning both.
     Every caller written before the picker existed passes a view with
     no `families` -- and one of them is `elementsFor(data, visible,
     selected)` with no view at all -- so "not said" has to mean the
     union rather than nothing, or those canvases lose all their edges. */
  function familiesOf(view) {
    return (view && view.families) || FAMILY_CLASSES;
  }

  /* Which classes this export could contain (#742): `--origins` filters
     what ships, so a class the flag left out is not merely absent from
     this corpus. An older data.js predates the field, and "all four"
     is the honest reading of a payload that does not say.

     Sets and lookups below are all null-prototype or Array#indexOf for
     the #636 reason above: `origin` is data-derived. */
  function shippedOrigins(data) {
    return data.origins && data.origins.length ? data.origins : ORIGIN_CLASSES;
  }

  function originOf(topic) {
    // A topic with no annotation still belongs on the canvas: silently
    // absent is worse than in the wrong colour.
    return ORIGIN_CLASSES.indexOf(topic.origin) >= 0 ? topic.origin : "emergent";
  }

  function labelsWithOrigins(data, active) {
    var labels = new Set();
    data.topics.forEach(function (t) {
      if (active.has(originOf(t))) { labels.add(t.label); }
    });
    return labels;
  }

  /* The hop rings are walked over the whole payload, so a neighbour two
     hops out can be a topic the origin filter has taken off the canvas.
     Intersecting here keeps one universe: what is drawn, what is dimmed
     and what the type-ahead offers all answer to the same set. */
  function restrictTo(labels, universe) {
    var kept = new Set();
    labels.forEach(function (label) {
      if (universe.has(label)) { kept.add(label); }
    });
    return kept;
  }

  /* One row per class for the header: its colour, its human name, how
     many topics it holds here, whether it shipped at all, and whether
     it is ticked. */
  function originControls(data, active) {
    var shipped = shippedOrigins(data);
    var counts = Object.create(null);
    (data.topics || []).forEach(function (t) {
      var origin = originOf(t);
      counts[origin] = (counts[origin] || 0) + 1;
    });
    return ORIGIN_CLASSES.map(function (origin) {
      return {
        origin: origin,
        name: ORIGIN_LABELS[origin],
        color: ORIGIN_COLORS[origin],
        count: counts[origin] || 0,
        shipped: shipped.indexOf(origin) >= 0,
        checked: active.has(origin),
      };
    });
  }

  /* The selection after a picker row moves, or null when it would empty
     the canvas -- an empty graph reads as an empty corpus, so the last
     member cannot be unticked. Non-destructive: the caller still holds
     the old selection to restore the tick from.

     One function for both axes. It was `nextOrigins` while origins were
     the only filter; the logic never mentioned an origin, and the edge
     families need exactly the same refusal -- with no family on there
     would be no graph at all, not even the union the rings used to
     walk. */
  function nextSelection(active, key, on) {
    var next = new Set(active);
    if (on) { next.add(key); } else { next.delete(key); }
    return next.size ? next : null;
  }

  function byLabel(topics) {
    var index = Object.create(null);
    topics.forEach(function (t) { index[t.label] = t; });
    return index;
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
      /* Relabelled from the members that survived, not from the ones the
         cut put in the group: with an origin class filtered out (#742) a
         box could otherwise lead with the name of a topic no longer on
         the canvas, and count "+29" others the reader cannot find. The
         cut itself is untouched -- the tree is still the stage's. */
      shown.push({
        group: group,
        members: members,
        label: members.length === group.members.length
          ? group.label
          : groupLabel(members, data.topics),
      });
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
          label: entry.label || entry.group.label,
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
  function bundleEdges(data, drawnAs, collapsedIds, families) {
    var bundles = Object.create(null);
    var order = [];
    function fold(family, i, a, b, width, surprise) {
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
      // Most surprising wins, as width takes the strongest: a bundle
      // drawn at the average hides the link worth looking at.
      if (surprise !== null) {
        bundle.data.surprise = Math.max(bundle.data.surprise || 0, surprise);
      }
      bundle.data.pairs.push({ family: family, index: i });
    }
    /* A family the picker has switched off is skipped whole, and its
       edge list is never rebuilt: the plain-edge id below is "ov-" or
       "se-" plus an index into `data.edges_overlap` /
       `data.edges_semantic`, and that is how the panel finds a clicked
       edge again in the payload. Filtering by copying the array into a
       shorter one would leave every id pointing at its neighbour's
       evidence -- the panel would name the wrong shared papers and
       nothing would look wrong. */
    var enabled = families || FAMILY_CLASSES;
    if (enabled.indexOf("overlap") >= 0) {
      data.edges_overlap.forEach(function (e, i) {
        fold("overlap", i, e.a, e.b, 1.5 + 6 * e.overlap_coeff, absence.surpriseOpacity(e.p_value));
      });
    }
    if (enabled.indexOf("semantic") >= 0) {
      data.edges_semantic.forEach(function (e, i) {
        // No p-value on this family, and none is borrowed: opacity means
        // "how surprising" only where the gate actually ran.
        fold("semantic", i, e.a, e.b, 1 + 3 * e.similarity, null);
      });
    }
    // An edge between two topics that are both drawn as themselves is
    // not a bundle: hand it back in its plain form, so nothing changes
    // for the part of the graph the reader has expanded.
    return order.map(function (bundle) {
      if (bundle.data.count > 1 || collapsedIds.has(bundle.data.source) ||
          collapsedIds.has(bundle.data.target)) {
        return bundle;
      }
      var pair = bundle.data.pairs[0];
      var plain = {
        group: "edges",
        data: {
          id: (pair.family === "overlap" ? "ov-" : "se-") + pair.index,
          source: bundle.data.source, target: bundle.data.target,
          family: pair.family, width: bundle.data.width, index: pair.index,
        },
      };
      if (bundle.data.surprise !== undefined) { plain.data.surprise = bundle.data.surprise; }
      return plain;
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

  /* `visible` is the reader's focus -- the pinned topics and what
     relates to them. With `view.context === "dim"` it stops being a
     filter and becomes an *emphasis* set: everything in `view.all`
     stays on the canvas and the rest is drawn faint, so the reader
     keeps their sense of how much of the corpus they are looking at.
     "hide" is the old hard filter, kept as a toggle. */
  /* ---------- papers as nodes ----------

     Membership is the pipeline's most concrete fact and the app has
     always shown it as a list. Expanded onto the canvas, a paper in
     three topics *is* a shape rather than a citekey repeated in three
     panels.

     A paper node is a third kind of node and its lines a third kind of
     edge. Neither is overlap and neither is semantic: those are claims
     about a pair of topics, and membership says nothing about either.
     Ids are prefixed because nodes share one namespace and a topic
     label is only semi-trusted -- a topic literally called
     "paper:dt2022" must not become the same node as the paper. */

  /* The prefix has to be one no topic label carries, because a topic
     labelled "paper:dt2022" would otherwise *be* the node for the paper
     dt2022 -- and a topic label is only semi-trusted data that can
     arrive from a PDF's extracted keywords. So it is computed from the
     payload rather than fixed: lengthen it until nothing collides. It
     terminates because the label set is finite. */
  function paperPrefix(topics) {
    var prefix = "paper:";
    while (topics.some(function (t) { return t.label.indexOf(prefix) === 0; })) {
      prefix = "paper:" + prefix;
    }
    return prefix;
  }

  function paperId(data, citekey) {
    return paperPrefix(data.topics) + citekey;
  }

  function citekeyOf(data, id) {
    var prefix = paperPrefix(data.topics);
    return id.indexOf(prefix) === 0 ? id.slice(prefix.length) : null;
  }
  // Opt-in and bounded: 131 topics fully expanded is several hundred
  // nodes and thousands of lines. The UI quotes this number rather than
  // silently drawing less than was asked for.
  var EXPANSION_CAP = 3;

  function paperElements(data, visible, expanded) {
    var open = data.topics
      .filter(function (t) { return visible.has(t.label) && expanded.has(t.label); })
      .slice(0, EXPANSION_CAP);
    if (!open.length) { return []; }
    var holders = Object.create(null);
    data.topics.forEach(function (t) {
      t.members.forEach(function (m) {
        (holders[m.citekey] = holders[m.citekey] || []).push(t.label);
      });
    });
    var prefix = paperPrefix(data.topics);
    var nodes = Object.create(null);
    var edges = [];
    open.forEach(function (t) {
      t.members.forEach(function (m) {
        var id = prefix + m.citekey;
        nodes[id] = nodes[id] || {
          group: "nodes",
          data: {
            id: id,
            kind: "paper",
            label: m.citekey,
            title: m.title,
            score: Math.max(0, Math.min(1, m.score)),
            topics: (holders[m.citekey] || []).length,
            // Bridging is about what is *on the canvas*. On a real
            // corpus almost every paper belongs to several topics, so
            // colouring by the corpus-wide count paints everything the
            // same and says nothing; what the reader can see is a
            // paper joined to more than one of the topics they opened.
            drawn: 0,
          },
        };
        nodes[id].data.drawn += 1;
        edges.push({
          group: "edges",
          data: {
            id: "mb-" + t.label + "-" + m.citekey,
            source: t.label,
            target: id,
            family: "member",
          },
        });
      });
    });
    return Object.keys(nodes).map(function (id) { return nodes[id]; }).concat(edges);
  }

  function elementsFor(data, visible, selected, view) {
    var pinned = selected.length > 0;
    var dimming = pinned && view && view.context === "dim" && Boolean(view.all);
    var universe = dimming ? view.all : visible;
    function dim(label) { return dimming && !visible.has(label) ? 1 : 0; }

    /* One layout regime at a time. Grouping is for browsing the whole
       corpus; the ego view is for reading one neighbourhood, and it
       needs the topics themselves, not the boxes they happen to sit in.
       Suspending the cut here rather than in the wiring means the rule
       is testable, and means a caller cannot half-apply it. */
    var resolved = resolveView(data, universe, pinned ? null : view);
    var els = groupNodes(resolved.groups, resolved.collapsedIds);
    var parentOf = Object.create(null);
    resolved.groups.forEach(function (entry) {
      if (resolved.collapsedIds.has(entry.group.id)) { return; }
      entry.members.forEach(function (label) { parentOf[label] = entry.group.id; });
    });
    data.topics.forEach(function (t) {
      if (!universe.has(t.label)) { return; }
      if (resolved.drawnAs[t.label] !== t.label) { return; }
      var node = topicNode(t, selected, parentOf[t.label]);
      if (dimming) { node.data.dim = dim(t.label); }
      els.push(node);
    });
    var edges = bundleEdges(
      data, resolved.drawnAs, resolved.collapsedIds, familiesOf(view)
    );
    if (dimming) {
      // An edge is only as bright as its dimmer end: a line running out
      // of the focus into the context has to read as leaving it.
      edges.forEach(function (edge) {
        edge.data.dim = Math.max(dim(edge.data.source), dim(edge.data.target));
      });
    }
    var expanded = (view && view.expanded) || new Set();
    return els.concat(edges, paperElements(data, universe, expanded));
  }

  /* `active` is the origin filter (#742), and omitting it means every
     class: the type-ahead must not offer a topic the canvas is not
     showing, because pinning one puts the app in a state elementsFor
     never sees. */
  function candidatesFor(data, selected, query, active) {
    var needle = query.trim().toLowerCase();
    if (!needle) { return []; }
    var out = [];
    data.topics.forEach(function (t) {
      if (selected.indexOf(t.label) >= 0) { return; }
      if (active && !active.has(originOf(t))) { return; }
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

  /* Sticky node focus: what clicking a node does to the
     latched id, with no cytoscape or DOM in the decision so the
     toggle/move/release cases are each one assertion under
     `node --test` rather than a browser-only behaviour. `clickedId`
     is null for a background tap, which always releases regardless
     of what was latched. */
  function nextLatch(current, clickedId) {
    if (clickedId == null) { return null; }
    if (current === clickedId) { return null; }
    return clickedId;
  }

  /* Esc's precedence: the type-ahead list, when open, always
     wins -- closing it is today's behaviour and stays unchanged. Chips
     are never touched here; clearing them is a destructive act the
     request deliberately gives its own gesture rather than a
     fall-through. */
  function escapeAction(suggestionsOpen, latched) {
    if (suggestionsOpen) { return "closeSuggestions"; }
    if (latched) { return "releaseLatch"; }
    return "none";
  }

  return {
    ORIGIN_COLORS: ORIGIN_COLORS,
    ORIGIN_LABELS: ORIGIN_LABELS,
    ORIGIN_CLASSES: ORIGIN_CLASSES,
    shippedOrigins: shippedOrigins,
    labelsWithOrigins: labelsWithOrigins,
    restrictTo: restrictTo,
    originControls: originControls,
    nextSelection: nextSelection,
    FAMILY_CLASSES: FAMILY_CLASSES,
    FAMILY_LABELS: FAMILY_LABELS,
    FAMILY_KEYS: FAMILY_KEYS,
    shippedFamilies: shippedFamilies,
    familyControls: familyControls,
    byLabel: byLabel,
    nodeSize: nodeSize,
    elementsFor: elementsFor,
    EXPANSION_CAP: EXPANSION_CAP,
    paperId: paperId,
    citekeyOf: citekeyOf,
    cutTree: cutTree,
    positionsFor: positionsFor,
    groupCentre: groupCentre,
    thresholdForGroups: thresholdForGroups,
    candidatesFor: candidatesFor,
    findMember: findMember,
    nextLatch: nextLatch,
    escapeAction: escapeAction,
  };
});
