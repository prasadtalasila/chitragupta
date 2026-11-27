"""Adopting the corpus layer's own Docling parse instead of repeating
it, and checking that every output this stage is supposed to write is
actually present.
"""

import json
import os
import re
from pathlib import Path

from chitragupta import config, passages
from chitragupta.citekey_safety import citekey_path
from chitragupta.enrich.corpus import CorpusDoc


def _outputs_present(stem: str) -> bool:
    """Every file this stage writes for `stem`, not just the .md.

    The fingerprint watches only the PDF, so a missing sidecar would
    otherwise stay missing forever. The passage sidecar is asked whether
    it *reads*, not whether it exists (#967).
    """
    expected = [citekey_path(config.DOCLING_DIR, stem, ".md")]
    if config.DOCLING_IMAGES:
        expected.append(citekey_path(config.DOCLING_DIR, stem, ".figures.json"))
    sidecar = citekey_path(config.DOCLING_DIR, stem, ".passages.json")
    return all(path.exists() for path in expected) and passages.sidecar_state(sidecar) == "ok"


def _corpus_parse_available(doc: CorpusDoc) -> bool:
    """Whether the corpus layer has already Docling-parsed this document.

    Signalled by its passage sidecar, which only a Docling parse writes.
    Refused with no parsed text, with `config.DOCLING_IMAGES` (the corpus
    layer writes no figures), or when artefacts are older than the PDF.
    Cannot tell which `[parser].ocr` produced it; that staleness already
    exists in `content/parsed/`, fixed by `sync --reparse` either way.
    """
    if config.DOCLING_IMAGES or not doc.text_path:
        return False
    parsed = Path(doc.text_path)
    sidecar = passages.sidecar_path(doc.citekey)
    try:
        pdf_mtime = os.stat(doc.pdf_path).st_mtime_ns
        return min(parsed.stat().st_mtime_ns, sidecar.stat().st_mtime_ns) >= pdf_mtime
    except OSError:
        # Either artefact missing, or an unreadable PDF: parse it.
        return False


def _reuse_corpus_parse(doc: CorpusDoc, out_path: Path, stem: str) -> bool:
    """Write this stage's outputs from the corpus layer's, without parsing.

    Enrichment reads corpus artefacts, never the reverse. Both converters
    use the same settings, so the sidecar is the same records and the
    Markdown differs only by form feeds, removed here. Saves a full second
    parse (6.65s per PDF serial, docs/PERFORMANCE.md).
    """
    if not _corpus_parse_available(doc):
        return False
    # Both reads before either write; a damaged one declines rather than
    # raises (#967): a torn sidecar would be stamped with a fingerprint no
    # later sync moves, and declining costs only one parse.
    try:
        markdown = Path(doc.text_path).read_text(encoding="utf-8", errors="replace")
        records = passages.read_records(passages.sidecar_path(doc.citekey))
    except (OSError, passages.SidecarUnreadable):
        return False
    if records is None:
        # Cleared since `_corpus_parse_available` looked.
        return False
    # A form feed becomes the paragraph break it sits in, or a flush one
    # would fuse two pages' words. Explicit encoding on write: the
    # platform default fails on non-ASCII under a C locale.
    out_path.write_text(re.sub(r"\n{3,}", "\n\n", markdown.replace("\f", "\n\n")), encoding="utf-8")
    citekey_path(config.DOCLING_DIR, stem, ".passages.json").write_text(
        json.dumps(records, indent=2), encoding="utf-8"
    )
    return True
