/* The side panel's HTML, built as strings.

   Split out of app.js so it can be tested without a DOM
   (tests/webapp/panel.test.js runs it under `node --test`). Every
   function here interpolates semi-trusted data -- a topic label may
   have ridden in through a PDF's extracted keywords, a title comes
   from the ledger -- so escaping is not incidental to this module, it
   is most of what it is for.

   Depends on graph.js for the origin vocabulary and the member lookup,
   and on absence.js for the containment reading and the withheld-edge
   arithmetic; index.html loads both before this file. */
"use strict";

(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./graph.js"), require("./absence.js"));
  } else {
    root.CHITRAGUPTA_APP = Object.assign(
      root.CHITRAGUPTA_APP || {}, factory(root.CHITRAGUPTA_APP, root.CHITRAGUPTA_APP)
    );
  }
})(typeof self !== "undefined" ? self : this, function (graph, absence) {
  /* An explicit five-character replace, not the textContent/innerHTML
     trick: serializing a text node escapes & < > but never quotes, and
     this function's output also lands inside double-quoted attributes
     (data-goto, data-label below) -- a label containing `"` closed the
     attribute and injected event-handler attributes, a stored XSS in
     the exported page (#636). */
  function escapeHtml(text) {
    return String(text == null ? "" : text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function paperCard(member) {
    var pct = Math.max(0, Math.min(100, Math.round(member.score * 100)));
    return '<div class="paper">' +
      '<p class="title">' + (escapeHtml(member.title) || "<em>(no title in ledger)</em>") + "</p>" +
      '<div class="meta"><code>' + escapeHtml(member.citekey) + "</code>" +
      '<div class="scorebar"><span style="width:' + pct + '%"></span></div>' +
      "<span>" + member.score.toFixed(2) + "</span></div></div>";
  }

  function linkedRows(data, topic) {
    var rows = "";
    data.edges_overlap.forEach(function (e) {
      var other = e.a === topic.label ? e.b : e.b === topic.label ? e.a : null;
      if (!other) { return; }
      rows += '<div class="linked-topic"><a tabindex="0" role="link" data-goto="' + escapeHtml(other) + '">' +
        escapeHtml(other) + "</a><div class=\"why\">shares " + e.shared.length +
        " paper" + (e.shared.length === 1 ? "" : "s") + ": " +
        escapeHtml(e.shared.join(", ")) + "</div></div>";
    });
    data.edges_semantic.forEach(function (e) {
      var other = e.a === topic.label ? e.b : e.b === topic.label ? e.a : null;
      if (!other) { return; }
      rows += '<div class="linked-topic"><a tabindex="0" role="link" data-goto="' + escapeHtml(other) + '">' +
        escapeHtml(other) + "</a><div class=\"why\">semantically near (" +
        e.similarity.toFixed(2) + "), bridged by " +
        escapeHtml(e.bridge.join(" and ")) + "</div></div>";
    });
    return rows || '<div class="linked-topic">no linked topics</div>';
  }

  function topicHtml(data, topic) {
    return "<h2>" + escapeHtml(topic.label) + "</h2>" +
      '<span class="origin-tag" style="background:' +
      (graph.ORIGIN_COLORS[topic.origin] || graph.ORIGIN_COLORS.emergent) + '">' +
      escapeHtml(graph.ORIGIN_LABELS[topic.origin] || topic.origin) + "</span>" +
      (topic.terms.length
        ? '<p class="terms">' + escapeHtml(topic.terms.join(" · ")) + "</p>" : "") +
      "<h3>Papers (" + topic.members.length + ")</h3>" +
      topic.members.map(paperCard).join("") +
      "<h3>Linked topics</h3>" + linkedRows(data, topic);
  }

  function edgeHtml(data, family, index) {
    var e, papers, why;
    if (family === "overlap") {
      e = data.edges_overlap[index];
      papers = e.shared;
      why = "These topics share " + papers.length + " paper" +
        (papers.length === 1 ? "" : "s") + " (jaccard " + e.jaccard.toFixed(2) +
        ", p = " + e.p_value.toExponential(1) + ").";
      // Both coefficients travel on every overlap edge for a reason;
      // naming the reading is the point, not printing two decimals.
      if (absence.containment(e)) {
        why += " Contained: nearly all of the smaller topic's papers are " +
          "inside the larger one (overlap " + e.overlap_coeff.toFixed(2) +
          ", Jaccard " + e.jaccard.toFixed(2) + ") — it reads as a sub-topic.";
      }
    } else {
      e = data.edges_semantic[index];
      papers = e.bridge;
      why = "These topics are semantically near (similarity " +
        e.similarity.toFixed(2) + "); the closest paper pair bridges them.";
    }
    var cards = papers.map(function (citekey) {
      var member = graph.findMember(data, citekey);
      return member ? paperCard(member) :
        '<div class="paper"><div class="meta"><code>' + escapeHtml(citekey) +
        "</code></div></div>";
    });
    return "<h2>" + escapeHtml(e.a) + " — " + escapeHtml(e.b) + "</h2>" +
      '<p class="terms">' + escapeHtml(why) + "</p>" +
      "<h3>" + (family === "overlap" ? "Shared papers" : "Bridge papers") + "</h3>" +
      cards.join("");
  }

  /* A collapsed group, or a compound parent, on click. The grouping is
     a cut of the stored merge tree made in this browser -- the panel
     says so, because `--json` reports no such grouping and a reader who
     quoted one as a corpus fact would be quoting the app's view state.
     The members are real topic labels and link straight through. */
  function groupHtml(group) {
    return "<h2>" + escapeHtml(group.label) + "</h2>" +
      '<p class="terms">' + group.members.length + " topic" +
      (group.members.length === 1 ? "" : "s") + ", grouped in your browser " +
      "by cutting the stored merge tree. Not a corpus claim: nothing is " +
      "written back, and <code>--json</code> reports no grouping.</p>" +
      "<h3>Topics in this group</h3>" +
      group.members.map(function (label) {
        return '<div class="linked-topic"><a tabindex="0" role="link" data-goto="' + escapeHtml(label) + '">' +
          escapeHtml(label) + "</a></div>";
      }).join("");
  }

  /* A bundled edge on click: every link it stands for, named. The two
     families are counted separately and never totalled -- a single
     number over both would be the fusion the design refuses. */
  function bundleHtml(data, pairs) {
    var overlap = pairs.filter(function (p) { return p.family === "overlap"; });
    var semantic = pairs.filter(function (p) { return p.family === "semantic"; });
    var rows = overlap.map(function (p) {
      var e = data.edges_overlap[p.index];
      return bundleRow(p, e, "shares " + e.shared.length + " paper" +
        (e.shared.length === 1 ? "" : "s") + ": " + e.shared.join(", "));
    }).concat(semantic.map(function (p) {
      var e = data.edges_semantic[p.index];
      return bundleRow(p, e, "semantically near (" + e.similarity.toFixed(2) +
        "), bridged by " + e.bridge.join(" and "));
    }));
    return "<h2>" + pairs.length + " link" + (pairs.length === 1 ? "" : "s") +
      ", bundled</h2>" +
      '<p class="terms">' + overlap.length + " over shared papers, " +
      semantic.length + " over semantic nearness. Counted apart because " +
      "they answer different questions.</p>" + rows.join("");
  }

  function bundleRow(pair, e, why) {
    return '<div class="linked-topic"><a tabindex="0" role="link" data-edge="' + pair.family + ":" + pair.index +
      '">' + escapeHtml(e.a) + " — " + escapeHtml(e.b) + "</a>" +
      '<div class="why">' + escapeHtml(why) + "</div></div>";
  }

  /* Why there is no edge between two pinned topics.

     The most instructive moment in this pipeline's own worked session
     is the gate computing p = 1.0 and withholding an edge between two
     topics that *do* share a paper, and no view has ever shown that
     reasoning. Three sentences, because there are three different
     answers and running them together would teach the wrong one:
     nothing shared at all; shared but unsurprising, which is the gate
     doing its job; and shared, surprising, and still unjoined -- which
     the page must *not* blame on the gate, because the stage's
     threshold is not carried in the payload and a stricter run is
     exactly what this looks like. */
  function absenceHtml(a, b, verdict) {
    var heading = "<h2>" + escapeHtml(a) + " — " + escapeHtml(b) + "</h2>";
    if (!verdict.shared.length) {
      return heading + '<p class="terms">These topics share no papers at all, ' +
        "so the overlap test had nothing to weigh. Any relation between them " +
        "would have to come from the semantic family.</p>";
    }
    var citekeys = verdict.shared.map(function (citekey) {
      return "<code>" + escapeHtml(citekey) + "</code>";
    }).join(", ");
    var count = verdict.shared.length + " paper" + (verdict.shared.length === 1 ? "" : "s");
    return heading + '<p class="terms">' +
      (verdict.p >= 0.01
        ? "These share " + citekeys + ", but sharing " + count +
          " between topics of size " + verdict.sizes.a + " and " + verdict.sizes.b +
          " in a " + verdict.docs + "-paper corpus is what chance predicts (p = " +
          verdict.p.toFixed(2) + "), so no edge was drawn."
        : "These share " + citekeys + " — " + count + " between topics of size " +
          verdict.sizes.a + " and " + verdict.sizes.b + " in a " + verdict.docs +
          "-paper corpus, which chance does not readily explain (p = " +
          verdict.p.toExponential(1) + "). This graph still carries no edge " +
          "between them, so the run that built it used a stricter cut-off than " +
          "this page can see: the threshold is not in the payload.") +
      "</p>";
  }

  /* The shape of a topic's neighbourhood, per edge family, side by
     side. Unlike everything else in this panel these numbers are
     computed here and now from the current view -- `--json` will not
     confirm them -- so the panel says so, and says what they mean: a
     dense neighbourhood is a theme, a sparse one is a bridge, and a
     topic that brokers over shared papers but not over vocabulary is a
     different animal from one that does the reverse. */
  function egoHtml(label, stats) {
    // Stored numbers (#713) are the corpus's own, confirmed by --json;
    // the in-browser fallback for an older payload keeps the original
    // caption, because the distinction is exactly what it states.
    var caption = stats.overlap.stored
      ? "How this topic sits among its neighbours, read from the " +
        "artefact -- the same numbers <code>--json</code> reports, " +
        "parameters alongside."
      : "How this topic sits among its neighbours, worked out " +
        "in your browser from the current view. Not a corpus claim: " +
        "<code>--json</code> reports none of it.";
    return "<h3>Neighbourhood of " + escapeHtml(label) + "</h3>" +
      '<p class="terms">' + caption + "</p>" +
      '<div class="ego-stats">' +
      statsColumn("Over shared papers", stats.overlap) +
      statsColumn("Over semantic nearness", stats.semantic) +
      "</div>";
  }

  function statsColumn(title, stats) {
    if (!stats.alters) {
      return "<div><h4>" + title + "</h4><p>no neighbours in this family</p></div>";
    }
    var reading = stats.density === null ? "one neighbour"
      : stats.density >= 0.5 ? "reads as a theme: its neighbours mostly connect"
        : "reads as a bridge: its neighbours mostly do not connect";
    return "<div><h4>" + title + "</h4>" +
      "<dl><dt>neighbours</dt><dd>" + stats.alters + "</dd>" +
      "<dt>ego density</dt><dd>" +
      (stats.density === null ? "&mdash;" : stats.density.toFixed(2)) + "</dd>" +
      "<dt>effective size</dt><dd>" + stats.effectiveSize.toFixed(2) + "</dd>" +
      "<dt>constraint</dt><dd>" + stats.constraint.toFixed(2) + "</dd></dl>" +
      "<p>" + reading + "</p></div>";
  }

  /* The co-membership grid: where clustering over shared papers and
     clustering over vocabulary disagree. Two lists, never one score,
     because the two disagreements read differently -- topics that talk
     alike and share nothing are a literature that has not met itself,
     and topics that share papers but split semantically are usually a
     terminology difference worth naming. */
  function disagreementHtml(grid) {
    var nothing = !grid.semanticOnly.length && !grid.overlapOnly.length;
    // Stored partitions (#712) are the corpus's own, confirmed by
    // --json; the in-browser clustering stays only for an export from
    // an older artefact, and keeps the original caption.
    var caption = grid.stored
      ? '<p class="terms">Both edge families clustered by the pipeline at ' +
        "inflation " + grid.inflation + " and read from the artefact -- " +
        "the same partitions <code>--json</code> reports.</p>"
      : '<p class="terms">Both edge families clustered in your browser at ' +
        "inflation " + grid.inflation + ", and compared. Not a corpus claim: " +
        "<code>--json</code> reports no clusters, and nothing is written back.</p>";
    // Under an origin filter the two halves of this panel answer to
    // different sets, and saying so is cheaper than a reader wondering
    // why a cluster count exceeds what they can see.
    if (grid.filtered) {
      caption += '<p class="terms">The clusters are the corpus\'s, over every ' +
        "topic; the pairs listed are those with both topics on the canvas under " +
        "your origin filter.</p>";
    }
    return "<h2>Where the two families disagree</h2>" + caption +
      (nothing
        ? "<p>At this inflation the two families agree about every pair: " +
          "no topic is grouped by one and split by the other.</p>"
        : disagreementList(
          "Talk alike, do not share papers", grid.semanticOnly,
          "one semantic cluster, different paper-sharing clusters"
        ) + disagreementList(
          "Share papers, talk differently", grid.overlapOnly,
          "one paper-sharing cluster, different semantic clusters"
        )) +
      (grid.dropped
        ? '<p class="terms">' + grid.dropped + " more pair" +
          (grid.dropped === 1 ? " is" : "s are") + " not listed; the lists are " +
          "capped so a large cluster cannot fill the panel.</p>"
        : "");
  }

  function disagreementList(title, pairs, why) {
    if (!pairs.length) { return ""; }
    return "<h3>" + title + "</h3>" + '<p class="terms">' + why + "</p>" +
      pairs.map(function (pair) {
        return '<div class="linked-topic"><a tabindex="0" role="link" data-goto="' + escapeHtml(pair.a) + '">' +
          escapeHtml(pair.a) + "</a> — <a tabindex=\"0\" role=\"link\" data-goto=\"" + escapeHtml(pair.b) + '">' +
          escapeHtml(pair.b) + "</a>" + '<div class="why">' +
          (pair.shared
            ? pair.shared + " shared paper" + (pair.shared === 1 ? "" : "s")
            : "no shared papers at all") + "</div></div>";
      }).join("");
  }

  /* One family's path between two pinned topics, hop by hop, each with
     the citekeys or the bridging pair that justify it. No total: a
     single distance over a family is uninterpretable, and one over both
     would be the fusion the design refuses. */
  /* `visible` is the origin filter's label set (#742). A stored route is
     free to run through a topic the filter hides, and the panel names
     it either way -- the walk is the corpus's, and hiding a hop would
     make the chain unexplainable -- but it says that it left the
     filter, so a topic that is named here and absent from the canvas
     reads as the route's doing rather than as a missing node. */
  function pathHtml(data, result, visible) {
    var family = result.family === "overlap" ? "shared papers" : "semantic nearness";
    if (!result.labels) {
      return "<h3>No path over " + family + "</h3>" +
        '<p class="terms">Nothing links these two over this family. That is an ' +
        "answer, not a failure -- try the other one.</p>";
    }
    if (!result.hops.length) {
      return "<h3>Over " + family + "</h3><p>Same topic.</p>";
    }
    var offCanvas = visible
      ? result.labels.filter(function (label) { return !visible.has(label); })
      : [];
    return "<h3>Over " + family + ", " + result.hops.length + " hop" +
      (result.hops.length === 1 ? "" : "s") + "</h3>" +
      (offCanvas.length
        ? '<p class="terms">This route leaves your origin filter: ' +
          offCanvas.map(escapeHtml).join(", ") +
          (offCanvas.length === 1 ? " is" : " are") + " named here but not drawn.</p>"
        : "") +
      result.hops.map(function (hop) {
        return '<div class="linked-topic"><a tabindex="0" role="link" data-goto="' + escapeHtml(hop.b) + '">' +
          escapeHtml(hop.a) + " → " + escapeHtml(hop.b) + "</a>" +
          '<div class="why">' + hop.strength.toFixed(2) + " · " +
          hop.evidence.map(function (citekey) {
            return "<code>" + escapeHtml(citekey) + "</code>";
          }).join(", ") + "</div></div>";
      }).join("");
  }

  /* A paper node on click: the paper itself, and every topic that holds
     it. A paper in more than one topic is *named* a bridge, because
     that is the reading a survey wants and the count alone does not say
     it. Null for a citekey the payload does not know -- there is no
     such thing as a paper this app can describe but not find. */
  function paperHtml(data, citekey) {
    var member = graph.findMember(data, citekey);
    if (!member) { return null; }
    var holders = data.topics.filter(function (t) {
      return t.members.some(function (m) { return m.citekey === citekey; });
    });
    return "<h2>" + escapeHtml(member.title || citekey) + "</h2>" +
      paperCard(member) +
      "<h3>In " + holders.length + " topic" + (holders.length === 1 ? "" : "s") + "</h3>" +
      (holders.length > 1
        ? '<p class="terms">This paper bridges them: it is a member of every ' +
          "one, which is why it is drawn once with a line to each.</p>"
        : "") +
      holders.map(function (t) {
        return '<div class="linked-topic"><a tabindex="0" role="link" data-goto="' + escapeHtml(t.label) + '">' +
          escapeHtml(t.label) + "</a></div>";
      }).join("");
  }

  function suggestionsHtml(candidates, activeIndex) {
    return candidates.map(function (c, i) {
      return '<li data-label="' + escapeHtml(c.label) + '"' +
        (i === activeIndex ? ' class="active"' : "") + ">" +
        "<span>" + escapeHtml(c.label) + '</span><span class="why">' +
        escapeHtml(c.why) + "</span></li>";
    }).join("");
  }

  /* The seed phrases no topic covers -- the terminal's `uncovered`
     list, shown rather than dropped (#717): a reader exploring the app
     deserves to learn that a seed came back empty, which is itself the
     "literature that has not met itself" observation. */
  function uncoveredHtml(uncovered) {
    return uncovered.map(function (phrase) {
      return "<div>" + escapeHtml(phrase) + "</div>";
    }).join("");
  }

  /* `visible` is the origin filter's label set (#742), and omitting it
     shows the tree whole. A merge is listed only while every topic it
     names is on the canvas: the stored tree itself is never recut --
     that would invent a grouping no stage computed -- but a row naming
     a topic the reader has filtered away is a row about nothing they
     can see. An end that is another merge's id is structure, not a
     topic, and is not looked up. */
  function hierarchyHtml(hierarchy, visible) {
    var ids = new Set(hierarchy.map(function (merge) { return merge.id; }));
    function drawn(end) { return ids.has(end) || !visible || visible.has(end); }
    return hierarchy.filter(function (merge) {
      return drawn(merge.a) && drawn(merge.b);
    }).map(function (merge) {
      return "<div>" + escapeHtml(merge.a) + " + " + escapeHtml(merge.b) +
        " (distance " + merge.distance.toFixed(2) + ")</div>";
    }).join("");
  }

  /* The origin filter's checkbox row. A class this export left out
     (`--origins`, #742) is disabled and says so: "filtered out at
     export" and "this corpus has none" are different facts, and a
     checkbox that merely does nothing when clicked tells the reader
     neither. */
  function originsHtml(controls, data) {
    var flag = "--origins " + (data.origins || []).join(",");
    return controls.map(function (control) {
      var why = control.shipped
        ? control.count + " topics"
        : "not in this export (" + flag + ")";
      return '<label class="origin-toggle' + (control.shipped ? "" : " excluded") + '"' +
        ' title="' + escapeHtml(why) + '">' +
        '<input type="checkbox" data-origin="' + escapeHtml(control.origin) + '"' +
        (control.checked && control.shipped ? " checked" : "") +
        (control.shipped ? "" : " disabled") + ">" +
        '<span class="swatch" style="background:' + control.color + '"></span>' +
        escapeHtml(control.origin) + "</label>";
    }).join("");
  }

  return {
    escapeHtml: escapeHtml,
    paperCard: paperCard,
    linkedRows: linkedRows,
    topicHtml: topicHtml,
    edgeHtml: edgeHtml,
    groupHtml: groupHtml,
    egoHtml: egoHtml,
    absenceHtml: absenceHtml,
    disagreementHtml: disagreementHtml,
    pathHtml: pathHtml,
    paperHtml: paperHtml,
    bundleHtml: bundleHtml,
    suggestionsHtml: suggestionsHtml,
    hierarchyHtml: hierarchyHtml,
    originsHtml: originsHtml,
    uncoveredHtml: uncoveredHtml,
  };
});
