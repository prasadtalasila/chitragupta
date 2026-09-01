"""The incremental-parse cache: a per-citekey (size, mtime_ns)
fingerprint, keyed against the settings that change what a cached
entry means.

Split from `chitragupta/enrich/docling_parse.py` (#441). Self-contained:
neither function calls back into that module, so the dependency runs
one way -- `docling_parse.py` imports `_load_cache`/`_save_cache`,
nothing here imports `docling_parse`.

Deliberately not shared with `chitragupta/retrieval_cache.py`'s own
`_load_cache`/`_save_cache`, despite the matching names and shape: that
one needs a per-writer-unique temp name for concurrent subagents; this
one does not, because `enrich.py` runs this stage from a single
process. Two copies of a five-line pattern, not one copy imported
across a layer boundary that has no reason to exist.
"""

import json
import logging
import os

from chitragupta import config, logging_setup

logger = logging.getLogger("chitragupta.enrich.docling_parse")

# Bump when a change to what parse_doc() *writes* makes an existing .md
# stale even though its PDF hasn't changed -- the (size, mtime_ns)
# fingerprint below only sees the input, never the output shape, so
# without this an option change silently serves last run's files
# forever. Mirrors chitragupta/retrieval.py's _INDEX_SCHEMA_VERSION.
# config.DOCLING_IMAGES is stored alongside it for the same reason:
# it's a *runtime* toggle, so it can't be folded into this constant.
# 2: added <stem>.passages.json, so a cache written by version 1 has
# no sidecar for citation_provenance to read even though its .md is
# current.
_CACHE_VERSION = 2


def _load_cache() -> dict:
    """Corrupt or unexpected-shape cache data is treated as empty rather
    than raised -- see chitragupta/retrieval.py's _load_cache for the same
    defensive shape, applied here so a truncated write (e.g. a killed
    mid-run process) doesn't take down every doc in the next parse_corpus
    call, just cost it one avoidable re-parse per doc.

    A version or image-setting mismatch invalidates the whole cache
    rather than any one entry: both change what every .md in
    config.DOCLING_DIR should contain, not just one document's. Scale is
    one such setting -- the worker converter key at
    `_docling_pool.py:87` already includes it, and a fingerprint-unchanged
    PDF re-converted at a different `DOCLING_IMAGE_SCALE` produces
    differently-sized bitmaps -- but the comparison here omitted it, so a
    scale change silently kept serving old bitmaps for every doc this
    cache still considered fresh (#504, m-46)."""
    try:
        data = json.loads(config.DOCLING_CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    if (
        data.get("version") != _CACHE_VERSION
        or data.get("images") != config.DOCLING_IMAGES
        or data.get("ocr") != config.PARSER_OCR
        or data.get("image_scale") != config.DOCLING_IMAGE_SCALE
    ):
        return {}
    items = data.get("items")
    if not isinstance(items, dict):
        return {}
    return {
        citekey: fp
        for citekey, fp in items.items()
        if isinstance(fp, list) and len(fp) == 2 and all(isinstance(n, int) for n in fp)
    }


def _save_cache(cache: dict) -> None:
    """Atomic write-then-replace so a process killed mid-save leaves the
    previous, still-valid cache in place instead of a torn file --
    doesn't need chitragupta/retrieval.py's per-writer-unique temp name (its
    concurrent-subagent scenario doesn't apply: enrich.py runs
    this stage from a single process).

    A failure to persist (permission, disk full) is reported, not
    raised (PR #10 review): by the time this runs, the expensive part
    -- Docling itself -- has already succeeded, so failing the whole
    parse over a cache write is worse than the alternative of just
    re-paying that one doc's parse cost next call."""
    try:
        config.DOCLING_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = config.DOCLING_CACHE_PATH.with_suffix(".json.tmp")
        payload = {
            "version": _CACHE_VERSION,
            "images": config.DOCLING_IMAGES,
            "ocr": config.PARSER_OCR,
            "image_scale": config.DOCLING_IMAGE_SCALE,
            "items": cache,
        }
        tmp_path.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(tmp_path, config.DOCLING_CACHE_PATH)
    except OSError as exc:
        logging_setup.say(
            logger,
            f"  WARNING: couldn't persist Docling's incremental cache "
            f"({exc}) -- next run will re-parse what was already done "
            "this run.",
            level=logging.WARNING,
        )
