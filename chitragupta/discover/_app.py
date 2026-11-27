"""`corpus discover --app DIR`: the topic graph as an interactive app.

A directory because the interaction layer ships verbatim from
`assets/webapp/` and only `data.js` is derived. It opens from file://
with no server: the payload is a JS assignment, since fetch() of local
JSON is blocked there. `_page.build_payload` does the join, so it cannot
disagree with `--json`; `origin` (from `_origin`) is added on top.
"""

import json
import shutil
from pathlib import Path

from chitragupta import config
from chitragupta.discover import _data, _origin, _page

# A copy list, not load order (index.html decides). Split into several
# files so all but the wiring is testable without a browser (node
# --test); browser_smoke.test.js drives the rest headless.
APP_FILES = (
    "index.html",
    "style.css",
    "payload.js",
    "absence.js",
    "graph.js",
    "ego.js",
    "families.js",
    "panel.js",
    "cy_style.js",
    "search.js",
    "pickers.js",
    "canvas.js",
    "sidepanel.js",
    "app.js",
    "vendor/cytoscape.min.js",
    "vendor/README.md",
)

DATA_PREFIX = "window.CHITRAGUPTA_TOPICS = "


def build_app_payload(graph: dict, topic_set: dict, terms: dict) -> dict:
    """`_page.build_payload` (the join, and its drift refusal) with each
    topic annotated by `origin` from `_origin` (#742)."""
    payload = _page.build_payload(graph, topic_set, terms)
    _origin.annotate(payload["topics"])
    return payload


def write_app(path: str, origins: "set | None" = None) -> str:
    """Build the payload from the artefacts on disk and write the app
    directory: assets/webapp/ copied verbatim, plus data.js. Raises
    `_data.MissingArtefact` like the terminal views; OSError is the
    caller's to translate.

    `origins` filters what ships, not what is drawn. The payload records
    the classes that *can* appear, so the app can disable a picker row
    and say why."""
    origins = origins or set(_origin.CLASSES)
    graph, topic_set = _origin.keep(_data.load_graph(), _data.load_topic_set(), origins)
    terms = _data.top_terms(topic_set)
    payload = build_app_payload(graph, topic_set, terms)
    payload["origins"] = [name for name in _origin.CLASSES if name in _origin.selected(origins)]
    return write_app_dir(path, payload)


def write_app_dir(path: str, payload: dict) -> str:
    """Write an already-built payload out as the app directory; separate
    so browser_smoke.test.js can export a hand-built payload the same way."""
    target = Path(path)
    (target / "vendor").mkdir(parents=True, exist_ok=True)
    for name in APP_FILES:
        shutil.copyfile(config.shipped("assets", "webapp", *name.split("/")), target / name)
    # `<` escaped so no label can close the script tag (as `_page`).
    embedded = json.dumps(payload).replace("<", "\\u003c")
    (target / "data.js").write_text(f"{DATA_PREFIX}{embedded};\n", encoding="utf-8")
    return str(target)
