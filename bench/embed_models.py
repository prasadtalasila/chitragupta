"""SPECTER2 encoder seam for Arm B. Unlike the three drop-in models,
SPECTER2 never sees a passage chunk -- every mode (base, proximity,
adhoc_query) takes only title+abstract on the document side, per
allenai/specter2_base's own model card. adhoc_query is the one
asymmetric exception: it encodes a short raw query string as-is,
compared against documents encoded with the proximity adapter.

The abstract has no home in the ledger -- chitragupta/ledger.py's
_BIB_FIELDS_KEPT drops it on purpose. abstract_for() recovers it from
content/docling/<citekey>.passages.json instead: the text between an
"Abstract" section_header and the next one. Measured on this host: 132
of the 497 citekeys with a docling sidecar (27%) carry that header --
but that 497 is the parsed-text subset, not the 642-citekey ledger this
benchmark's own run ranks SPECTER2 over (the other 145 have no PDF text
and so no sidecar to look in). Against the full 642, the same 132 is
132/642 = 21%; quote whichever population matches the claim being made,
not the other one. The rest fall back to title-only, SPECTER2's own
documented behaviour for a missing abstract.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from chitragupta import ledger, passages  # noqa: E402

PAPER_CACHE_PATH = Path(__file__).resolve().parent / "results" / "specter2_paper_cache.json"

_TOKENIZER = None
_MODEL = None
_ACTIVE_ADAPTER = None


def title_for(con, citekey):
    row = con.execute("SELECT title FROM items WHERE citekey = ?", (citekey,)).fetchone()
    return row[0] if row and row[0] else ""


def abstract_for(con, citekey):
    """Text between an "Abstract" section_header and the next one, or ""
    if the sidecar has none -- the common case, and not an error."""
    found, _reason = passages.source_passages(con, citekey)
    collecting = False
    parts = []
    for passage in found:
        if passage.label == "section_header":
            if collecting:
                break
            collecting = bool(passage.text and
                              passage.text.strip().lower().rstrip(".") == "abstract")
            continue
        if collecting and passage.label == "text" and passage.text:
            parts.append(passage.text)
    return " ".join(parts)


def _load(adapter_name, hf_repo):
    global _TOKENIZER, _MODEL, _ACTIVE_ADAPTER
    from transformers import AutoTokenizer
    from adapters import AutoAdapterModel

    if _MODEL is None:
        _TOKENIZER = AutoTokenizer.from_pretrained("allenai/specter2_base")
        _MODEL = AutoAdapterModel.from_pretrained("allenai/specter2_base")
    if _ACTIVE_ADAPTER != adapter_name:
        _MODEL.load_adapter(hf_repo, source="hf", load_as=adapter_name, set_active=True)
        _ACTIVE_ADAPTER = adapter_name
    return _TOKENIZER, _MODEL


def _encode(texts, adapter_name, hf_repo):
    tokenizer, model = _load(adapter_name, hf_repo)
    inputs = tokenizer(texts, padding=True, truncation=True, return_tensors="pt",
                       return_token_type_ids=False, max_length=512)
    output = model(**inputs)
    return output.last_hidden_state[:, 0, :].tolist()


def embed_paper(citekeys):
    """One proximity-adapter vector per citekey. Cached to disk by
    citekey, since a synced corpus's title+abstract text does not change
    between benchmark runs -- re-encoding all ~501 papers on every row
    that needs SPECTER2 would pay the same cost three times over for no
    reason.

    The cache has no invalidation key: unlike chitragupta/enrich/embed_index.py's
    build_index(), which keys its own cache by a per-chunk text_hash
    specifically to avoid this, PAPER_CACHE_PATH is keyed by citekey
    alone -- no model id, adapter name, or text hash. It will keep
    serving a stale vector after a re-parse or corpus re-sync changes a
    paper's title or recovered abstract. Delete PAPER_CACHE_PATH by hand
    when that happens; this script does not detect it for you."""
    con = ledger.connect()
    cache = (json.loads(PAPER_CACHE_PATH.read_text(encoding="utf-8"))
             if PAPER_CACHE_PATH.exists() else {})
    missing = [c for c in citekeys if c not in cache]
    if missing:
        tokenizer, _model = _load("proximity", "allenai/specter2")
        rows = [(citekey, title_for(con, citekey), abstract_for(con, citekey))
                for citekey in missing]
        texts = [title + tokenizer.sep_token + abstract for _, title, abstract in rows]
        vectors = _encode(texts, "proximity", "allenai/specter2")
        for (citekey, _title, abstract), vector in zip(rows, vectors):
            cache[citekey] = {"vector": vector,
                              "abstract_source": "docling" if abstract else "title-only"}
        PAPER_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        PAPER_CACHE_PATH.write_text(json.dumps(cache), encoding="utf-8")
    return {c: cache[c]["vector"] for c in citekeys}


def embed_query(text):
    return _encode([text], "adhoc_query", "allenai/specter2_adhoc_query")[0]


def self_check():
    """title_for() and abstract_for() work against a real citekey this
    host is known to have an Abstract header for, and abstract_for()
    degrades to "" rather than raising for a citekey that isn't real --
    the two facts embed_paper() depends on before it ever loads a model."""
    con = ledger.connect()
    title = title_for(con, "lugaresi_digital_2025")
    assert title, "title_for() found no title for a citekey known to be in the ledger"
    abstract = abstract_for(con, "lugaresi_digital_2025")
    assert abstract, (
        "abstract_for() found no Abstract section for lugaresi_digital_2025 -- "
        "this host's content/docling/lugaresi_digital_2025.passages.json is known to have one"
    )
    assert abstract_for(con, "not_a_real_citekey") == "", (
        "abstract_for() should return '' for an unknown citekey, not raise"
    )


if __name__ == "__main__":
    self_check()
    print("self_check() passed")
