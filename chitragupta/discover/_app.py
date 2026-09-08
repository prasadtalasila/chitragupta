"""`corpus discover --app DIR`: the topic graph as an interactive app.

A directory rather than one file, because the interaction layer
(cytoscape.js, the type-ahead search, the paper panel) is corpus-
independent and ships verbatim from `assets/webapp/` -- only `data.js`
is derived. The whole directory can be downloaded and opened from
file:// with no server and no network: index.html references only its
own siblings, and the payload travels as a JS assignment because
fetch() of a local JSON file is blocked under file://.

Like `_page`, this is a pure renderer of the artefacts the terminal
views read -- `_page.build_payload` does the join, so the app can never
disagree with `--json`. The one thing added on top is `origin`: which
file each seed phrase came from, so the app can colour a hand-written
topic apart from a machine-suggested one. That annotation lives in
`_origin`, which explains why the graph artefact cannot answer the
question and which the `--origins` filter and the terminal views read
too -- one definition, four callers.
"""

import json
import shutil
from pathlib import Path

from chitragupta import config
from chitragupta.discover import _data, _origin, _page

# Order is not load order (index.html decides that); this is just the
# copy list. The interaction code is several files rather than one so
# that everything except the wiring can be tested without a browser --
# `node --test tests/webapp/*.test.js` -- leaving app.js as the
# cytoscape instance and the DOM events around them.
APP_FILES = (
    "index.html",
    "style.css",
    "absence.js",
    "graph.js",
    "ego.js",
    "families.js",
    "panel.js",
    "app.js",
    "vendor/cytoscape.min.js",
    "vendor/README.md",
)

DATA_PREFIX = "window.CHITRAGUPTA_TOPICS = "


def build_app_payload(graph: dict, topic_set: dict, terms: dict) -> dict:
    """`_page.build_payload` (the join, and its drift refusal) with each
    topic annotated by `origin`: seed | keyword | corroborated |
    emergent. The annotation itself lives in `_origin`, because the
    terminal views and the `--origins` filter read the same one (#742)."""
    payload = _page.build_payload(graph, topic_set, terms)
    _origin.annotate(payload["topics"])
    return payload


def write_app(path: str, origins: "set | None" = None) -> str:
    """Build the payload from the artefacts on disk and write the app
    directory: the static files copied verbatim from assets/webapp/,
    plus data.js. Raises `_data.MissingArtefact` exactly like the
    terminal views, so the CLI boundary translates it the same way;
    OSError (an unwritable target) is the caller's to translate, the
    same split `_page.write_page` has with the --html clause.

    `origins` is the `--origins` selection, and it filters what ships
    rather than what is drawn: the directory then contains what it says
    it contains. The payload records the classes that *can* appear under
    it, so the app can disable that class's picker row and say why,
    instead of doing nothing when it is clicked."""
    origins = origins or set(_origin.CLASSES)
    graph, topic_set = _origin.keep(_data.load_graph(), _data.load_topic_set(), origins)
    terms = _data.top_terms(topic_set)
    payload = build_app_payload(graph, topic_set, terms)
    payload["origins"] = [name for name in _origin.CLASSES if name in _origin.selected(origins)]

    target = Path(path)
    (target / "vendor").mkdir(parents=True, exist_ok=True)
    for name in APP_FILES:
        shutil.copyfile(config.shipped("assets", "webapp", *name.split("/")), target / name)
    # `<` escaped in the embedded JSON so no title or label can close
    # the script tag early -- the same one injection route, and the same
    # fix, as `_page.build_html`'s JSON island.
    embedded = json.dumps(payload).replace("<", "\\u003c")
    (target / "data.js").write_text(f"{DATA_PREFIX}{embedded};\n", encoding="utf-8")
    return str(target)
