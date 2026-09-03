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
file each seed phrase came from (`content/seed_topics.toml`, the
extracted `content/keywords.toml`, or both), so the app can colour a
hand-written topic apart from a machine-suggested one. The graph
artefact cannot answer that -- `_seed_phrases()` unions the two files
before the stages run, so `topic_set.json` records them all as
provenance "seed" -- and the two TOML files are the only record left.
"""

import json
import shutil
from pathlib import Path

from chitragupta import config, seed_topics
from chitragupta.discover import _data, _page

APP_FILES = (
    "index.html",
    "style.css",
    "app.js",
    "vendor/cytoscape.min.js",
    "vendor/README.md",
)

DATA_PREFIX = "window.CHITRAGUPTA_TOPICS = "


def _origin(topic: dict, hand: set, extracted: set) -> str:
    """Where this topic's phrase came from. Emergent topics keep their
    provenance whatever the files say -- a BERTopic label colliding with
    a keyword is a coincidence, not a seeding. A seed topic in neither
    file (the files moved after the stages ran) degrades to "seed": the
    artefact's own provenance is still true, and refusing would make the
    app stricter than every other view of the same data."""
    if topic["provenance"] != "seed":
        return "emergent"
    key = topic["label"].casefold()
    if key in hand:
        return "both" if key in extracted else "seed"
    if key in extracted:
        return "keyword"
    return "seed"


def build_app_payload(graph: dict, topic_set: dict, terms: dict) -> dict:
    """`_page.build_payload` (the join, and its drift refusal) with each
    topic annotated by `origin`: seed | keyword | both | emergent."""
    payload = _page.build_payload(graph, topic_set, terms)
    hand = {phrase.casefold() for phrase in seed_topics.load()}
    extracted = {phrase.casefold() for phrase in seed_topics.load(config.KEYWORDS_PATH)}
    for topic in payload["topics"]:
        topic["origin"] = _origin(topic, hand, extracted)
    return payload


def write_app(path: str) -> str:
    """Build the payload from the artefacts on disk and write the app
    directory: the static files copied verbatim from assets/webapp/,
    plus data.js. Raises `_data.MissingArtefact` exactly like the
    terminal views, so the CLI boundary translates it the same way;
    OSError (an unwritable target) is the caller's to translate, the
    same split `_page.write_page` has with the --html clause."""
    graph = _data.load_graph()
    topic_set = _data.load_topic_set()
    terms = _data.top_terms(topic_set)
    payload = build_app_payload(graph, topic_set, terms)

    target = Path(path)
    (target / "vendor").mkdir(parents=True, exist_ok=True)
    for name in APP_FILES:
        shutil.copyfile(
            config.shipped("assets", "webapp", *name.split("/")), target / name
        )
    # `<` escaped in the embedded JSON so no title or label can close
    # the script tag early -- the same one injection route, and the same
    # fix, as `_page.build_html`'s JSON island.
    embedded = json.dumps(payload).replace("<", "\\u003c")
    (target / "data.js").write_text(f"{DATA_PREFIX}{embedded};\n", encoding="utf-8")
    return str(target)
