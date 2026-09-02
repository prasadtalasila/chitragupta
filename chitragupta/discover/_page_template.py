"""The HTML shell for `corpus discover --html`: one self-contained page.

A separate module holding one string, for the same reason the
code-standards line limit exists at all: `_page.py` owns *what data the
page gets*, this owns *what the page looks like*, and the two change
for different reasons. Everything is inline -- CSS, JavaScript, the
data payload -- because the page must work from file:// with no network
forever; a CDN reference would rot and a fetch() would violate the
whole point of a static export.

The layout is a circle, not a force simulation, on purpose: at tens of
topics a circle with curved chords is legible, renders identically
every time (diffable screenshots), and costs no physics code to debug.
`__PAYLOAD__` is replaced by `_page.py` with JSON whose `<` is escaped,
so a title containing `</script>` cannot break out of the script tag.
"""

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Topic graph</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; display: flex; height: 100vh; }
  #canvas { flex: 2; min-width: 0; }
  #panel { flex: 1; overflow-y: auto; border-left: 1px solid #ccc; padding: 1rem; }
  #panel h2 { margin-top: 0; font-size: 1.1rem; }
  #panel .prov { color: #666; font-size: 0.85rem; }
  #panel li { margin-bottom: 0.4rem; font-size: 0.9rem; }
  .edge-overlap { stroke: #4f46e5; fill: none; }
  .edge-semantic { stroke: #9333ea; stroke-dasharray: 5 4; fill: none; }
  circle.topic { fill: #eef2ff; stroke: #4f46e5; cursor: pointer; }
  circle.topic.seed { fill: #f0fdf4; stroke: #16a34a; }
  circle.topic.selected { stroke-width: 4; }
  text.label { font-size: 12px; cursor: pointer; }
  #legend { position: absolute; left: 1rem; bottom: 1rem; background: #fff;
            border: 1px solid #ccc; padding: 0.5rem; font-size: 0.8rem; }
  details { margin-top: 1rem; }
  #tree ul { list-style: none; padding-left: 1rem; }
</style>
</head>
<body>
<div id="canvas"><svg id="svg" width="100%" height="100%"></svg>
  <div id="legend">
    solid = shared members &middot; dashed = semantically near<br>
    green = seed topic &middot; blue = emergent &middot; click a topic
  </div>
</div>
<div id="panel"><h2>Topic graph</h2>
  <p>Click a topic for its papers and neighbours.</p>
  <details id="treebox"><summary>Hierarchy</summary><div id="tree"></div></details>
</div>
<script id="data" type="application/json">__PAYLOAD__</script>
<script>
"use strict";
const DATA = JSON.parse(document.getElementById("data").textContent);
const svg = document.getElementById("svg");
const NS = "http://www.w3.org/2000/svg";
const box = svg.getBoundingClientRect();
const cx = box.width / 2, cy = box.height / 2;
const radius = Math.max(80, Math.min(cx, cy) - 120);
const pos = {};
DATA.topics.forEach((t, i) => {
  const angle = (2 * Math.PI * i) / DATA.topics.length - Math.PI / 2;
  pos[t.label] = { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) };
});
function chord(a, b, cls, width) {
  const p = document.createElementNS(NS, "path");
  const mx = (pos[a].x + pos[b].x) / 2 + (cx - (pos[a].x + pos[b].x) / 2) * 0.35;
  const my = (pos[a].y + pos[b].y) / 2 + (cy - (pos[a].y + pos[b].y) / 2) * 0.35;
  p.setAttribute("d", `M ${pos[a].x} ${pos[a].y} Q ${mx} ${my} ${pos[b].x} ${pos[b].y}`);
  p.setAttribute("class", cls);
  p.setAttribute("stroke-width", width);
  svg.appendChild(p);
}
DATA.edges_overlap.forEach(e => chord(e.a, e.b, "edge-overlap", 1 + 4 * e.overlap_coeff));
DATA.edges_semantic.forEach(e => chord(e.a, e.b, "edge-semantic", 1 + 2 * e.similarity));
function show(label) {
  document.querySelectorAll("circle.topic").forEach(c => c.classList.remove("selected"));
  const dot = document.getElementById("dot-" + label);
  if (dot) dot.classList.add("selected");
  const t = DATA.topics.find(t => t.label === label);
  const panel = document.getElementById("panel");
  const papers = t.members.map(m =>
    `<li><code>${esc(m.citekey)}</code> [${m.score.toFixed(2)}] ${esc(m.title)}</li>`).join("");
  const overlap = t.linked.overlap.map(e =>
    `<li>${esc(e.label)} &mdash; shared: ${e.shared.map(esc).join(", ")}</li>`).join("");
  const semantic = t.linked.semantic.map(e =>
    `<li>${esc(e.label)} &mdash; ${e.similarity.toFixed(2)}, bridge ` +
    `${esc(e.bridge[0])} &harr; ${esc(e.bridge[1])}</li>`).join("");
  panel.innerHTML =
    `<h2>${esc(label)}</h2><p class="prov">${esc(t.provenance)}, ${t.members.length} papers` +
    (t.terms.length ? ` &middot; ${t.terms.map(esc).join(", ")}` : "") + `</p>` +
    `<h3>Papers</h3><ul>${papers}</ul>` +
    `<h3>Shared members</h3><ul>${overlap || "<li>none</li>"}</ul>` +
    `<h3>Semantically near</h3><ul>${semantic || "<li>none</li>"}</ul>`;
}
function esc(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
DATA.topics.forEach(t => {
  const c = document.createElementNS(NS, "circle");
  c.setAttribute("cx", pos[t.label].x);
  c.setAttribute("cy", pos[t.label].y);
  c.setAttribute("r", 6 + 2.5 * Math.sqrt(t.members.length));
  c.setAttribute("class", "topic" + (t.provenance === "seed" ? " seed" : ""));
  c.setAttribute("id", "dot-" + t.label);
  c.addEventListener("click", () => show(t.label));
  svg.appendChild(c);
  const txt = document.createElementNS(NS, "text");
  const outward = pos[t.label].x >= cx;
  txt.setAttribute("x", pos[t.label].x + (outward ? 14 : -14));
  txt.setAttribute("y", pos[t.label].y + 4);
  txt.setAttribute("text-anchor", outward ? "start" : "end");
  txt.setAttribute("class", "label");
  txt.textContent = t.label;
  txt.addEventListener("click", () => show(t.label));
  svg.appendChild(txt);
});
(function tree() {
  if (!DATA.hierarchy.length) {
    document.getElementById("treebox").style.display = "none";
    return;
  }
  const children = {};
  const merged = new Set();
  DATA.hierarchy.forEach(m => {
    children[m.id] = [m.a, m.b];
    merged.add(m.a); merged.add(m.b);
  });
  const roots = DATA.hierarchy.map(m => m.id).filter(id => !merged.has(id));
  function render(node) {
    if (!children[node]) return `<li>${esc(node)}</li>`;
    return `<li>&#8226;<ul>${children[node].map(render).join("")}</ul></li>`;
  }
  document.getElementById("tree").innerHTML =
    `<ul>${roots.map(render).join("")}</ul>`;
})();
</script>
</body>
</html>
"""
