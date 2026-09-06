/* The side panel's HTML, built as strings.

   Split out of app.js so it can be tested without a DOM
   (tests/webapp/panel.test.js runs it under `node --test`). Every
   function here interpolates semi-trusted data -- a topic label may
   have ridden in through a PDF's extracted keywords, a title comes
   from the ledger -- so escaping is not incidental to this module, it
   is most of what it is for.

   Depends on graph.js for the origin vocabulary and the member lookup;
   index.html loads that file first. */
"use strict";

(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./graph.js"));
  } else {
    root.CHITRAGUPTA_APP = Object.assign(
      root.CHITRAGUPTA_APP || {}, factory(root.CHITRAGUPTA_APP)
    );
  }
})(typeof self !== "undefined" ? self : this, function (graph) {
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
      rows += '<div class="linked-topic"><a data-goto="' + escapeHtml(other) + '">' +
        escapeHtml(other) + "</a><div class=\"why\">shares " + e.shared.length +
        " paper" + (e.shared.length === 1 ? "" : "s") + ": " +
        escapeHtml(e.shared.join(", ")) + "</div></div>";
    });
    data.edges_semantic.forEach(function (e) {
      var other = e.a === topic.label ? e.b : e.b === topic.label ? e.a : null;
      if (!other) { return; }
      rows += '<div class="linked-topic"><a data-goto="' + escapeHtml(other) + '">' +
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
        return '<div class="linked-topic"><a data-goto="' + escapeHtml(label) + '">' +
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
    return '<div class="linked-topic"><a data-edge="' + pair.family + ":" + pair.index +
      '">' + escapeHtml(e.a) + " — " + escapeHtml(e.b) + "</a>" +
      '<div class="why">' + escapeHtml(why) + "</div></div>";
  }

  /* The shape of a topic's neighbourhood, per edge family, side by
     side. Unlike everything else in this panel these numbers are
     computed here and now from the current view -- `--json` will not
     confirm them -- so the panel says so, and says what they mean: a
     dense neighbourhood is a theme, a sparse one is a bridge, and a
     topic that brokers over shared papers but not over vocabulary is a
     different animal from one that does the reverse. */
  function egoHtml(label, stats) {
    return "<h3>Neighbourhood of " + escapeHtml(label) + "</h3>" +
      '<p class="terms">How this topic sits among its neighbours, worked out ' +
      "in your browser from the current view. Not a corpus claim: " +
      "<code>--json</code> reports none of it.</p>" +
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

  function suggestionsHtml(candidates, activeIndex) {
    return candidates.map(function (c, i) {
      return '<li data-label="' + escapeHtml(c.label) + '"' +
        (i === activeIndex ? ' class="active"' : "") + ">" +
        "<span>" + escapeHtml(c.label) + '</span><span class="why">' +
        escapeHtml(c.why) + "</span></li>";
    }).join("");
  }

  function hierarchyHtml(hierarchy) {
    return hierarchy.map(function (merge) {
      return "<div>" + escapeHtml(merge.a) + " + " + escapeHtml(merge.b) +
        " (distance " + merge.distance.toFixed(2) + ")</div>";
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
    bundleHtml: bundleHtml,
    suggestionsHtml: suggestionsHtml,
    hierarchyHtml: hierarchyHtml,
  };
});
