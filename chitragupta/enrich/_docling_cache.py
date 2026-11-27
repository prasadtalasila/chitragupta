"""The incremental-parse cache: a per-citekey (size, mtime_ns)
fingerprint, keyed against the settings that change what a cached
entry means.

Not shared with `chitragupta/retrieval_cache.py`'s look-alike: that one
needs a per-writer-unique temp name for concurrent subagents; this stage
runs from a single process.
"""

import json
import logging
import os

from chitragupta import config, logging_setup

logger = logging.getLogger("chitragupta.enrich.docling_parse")

# Bump when what parse_doc() *writes* changes: the fingerprint sees only
# the input, so an option change would serve last run's files forever.
# config.DOCLING_IMAGES is stored beside it as a runtime toggle.
# 2: added <stem>.passages.json. 3: sidecars carry table and formula
# records (#627).
_CACHE_VERSION = 3


def _load_cache() -> dict:
    """Load the cache; corrupt or unexpected-shape data reads as empty,
    costing one re-parse per doc rather than the whole run.

    A version, image-setting or image-scale mismatch invalidates the
    whole cache, since it changes every .md; scale was once omitted and
    kept serving old bitmaps (#504, m-46). `UnicodeDecodeError` too: a
    write killed inside a multi-byte character fails before json (#967)."""
    try:
        data = json.loads(config.DOCLING_CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    if (
        data.get("version") != _CACHE_VERSION
        or data.get("images") != config.DOCLING_IMAGES
        or data.get("ocr") != config.PARSER_OCR
        or data.get("image_scale") != config.DOCLING_IMAGE_SCALE
        or data.get("formulas") != config.DOCLING_FORMULAS
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
    """Atomic write-then-replace, so a killed save leaves the previous
    cache. A failure to persist is reported, not raised (PR #10 review):
    Docling has already succeeded, and a re-parse next call is cheaper
    than failing the parse."""
    try:
        config.DOCLING_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = config.DOCLING_CACHE_PATH.with_suffix(".json.tmp")
        payload = {
            "version": _CACHE_VERSION,
            "images": config.DOCLING_IMAGES,
            "ocr": config.PARSER_OCR,
            "image_scale": config.DOCLING_IMAGE_SCALE,
            "formulas": config.DOCLING_FORMULAS,
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
