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
    suggestionsHtml: suggestionsHtml,
    hierarchyHtml: hierarchyHtml,
  };
});
