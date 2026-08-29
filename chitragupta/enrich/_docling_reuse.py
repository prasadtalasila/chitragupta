"""Adopting the corpus layer's own Docling parse instead of repeating
it, and checking that every output this stage is supposed to write is
actually present.

Split from `chitragupta/enrich/docling_parse.py` (#441). Self-contained:
neither function calls back into that module, so the dependency runs
one way -- `docling_parse.py` imports `_outputs_present`,
`_corpus_parse_available` and `_reuse_corpus_parse`, nothing here
imports `docling_parse`.
"""

import os
import re
from pathlib import Path

from chitragupta import config, passages
from chitragupta.enrich.corpus import CorpusDoc


def _outputs_present(stem: str) -> bool:
    """Every file this stage writes for `stem`, not just the .md.

    The fingerprint only says the *input* PDF is unchanged. Checking one
    output was enough when the .md was the only one; now a deleted or
    corrupted `<stem>.passages.json` (or `<stem>.figures.json`, with
    images on) would be skipped over on every subsequent run and stay
    missing forever, because the .md it is paired with is still there.
    """
    expected = [
        config.DOCLING_DIR / f"{stem}.md",
        config.DOCLING_DIR / f"{stem}.passages.json",
    ]
    if config.DOCLING_IMAGES:
        expected.append(config.DOCLING_DIR / f"{stem}.figures.json")
    return all(path.exists() for path in expected)


def _corpus_parse_available(doc: CorpusDoc) -> bool:
    """Whether the corpus layer has already Docling-parsed this document.

    The signal is the corpus layer's own passage sidecar. Only a Docling
    parse writes one -- `pdftotext` returns no records, and
    `pdf_text.extract_text` clears any stale sidecar before every parse --
    so its presence means `content/parsed/<citekey>.txt` is Docling
    Markdown rather than column-spliced flat text.

    Refused in three cases:

    - a document the corpus layer has not written parsed text for
      (`text_path` unset -- e.g. a bib entry with no PDF attachment, or
      one whose parse failed);
    - `config.DOCLING_IMAGES`, because the corpus layer writes no figure
      bitmaps and no `<stem>.figures.json`, and adopting a parse that
      lacks them would leave this stage's own output incomplete;
    - artefacts older than the PDF, which means the PDF has been replaced
      since the corpus layer read it.

    One gap, stated rather than hidden: this cannot tell which
    `[parser].ocr` setting produced the corpus text. But that staleness
    already exists in `content/parsed/` the moment the setting changes --
    adopting it here propagates it rather than creating it, and the fix is
    the same either way (`python -m chitragupta.corpus sync --reparse`).
    """
    if config.DOCLING_IMAGES or not doc.text_path:
        return False
    parsed = Path(doc.text_path)
    sidecar = passages.sidecar_path(doc.citekey)
    try:
        pdf_mtime = os.stat(doc.pdf_path).st_mtime_ns
        return min(parsed.stat().st_mtime_ns, sidecar.stat().st_mtime_ns) >= pdf_mtime
    except OSError:
        # Either artefact missing, or an unreadable PDF -- parse it.
        return False


def _reuse_corpus_parse(doc: CorpusDoc, out_path: Path, stem: str) -> bool:
    """Write this stage's outputs from the corpus layer's, without parsing.

    The dependency runs the way this repository allows it to: the
    enrichment layer reads the corpus layer's artefacts, never the
    reverse. Nothing in `chitragupta/` outside this package changes shape to make
    it possible, and a corpus layer that has never run docling simply
    leaves this returning False.

    What makes the two interchangeable is that both converters are built
    from the same two settings (`config.PARSER_OCR`,
    `config.PARSER_DOCUMENT_TIMEOUT`) and, with picture bitmaps off, ask
    Docling for the same thing -- so for one PDF they produce the same
    document. The passage sidecar is then literally the same records from
    the same `passages.passage_records()`, and the Markdown differs only
    by the form feeds the corpus layer asks for and this layer does not.
    Removing them, and collapsing the blank run each one leaves behind,
    gives back what `export_to_markdown()` would have returned -- the same
    normalisation `strip_image_refs` already applies before embedding.

    Worth what it saves: a full second parse of every document the corpus
    layer has already parsed, measured at 6.65s per PDF serial
    (docs/PERFORMANCE.md).
    """
    if not _corpus_parse_available(doc):
        return False
    # Both reads before either write, and a damaged one declines the reuse
    # instead of raising. A sidecar truncated mid-write by a killed
    # process can split a multi-byte character, which fails to decode --
    # chitragupta/passages.py's reader already tolerates exactly that, for the
    # same reason. Here the cost of not tolerating it would be worse than
    # a fallback: parse_doc would report a hard error for a document whose
    # PDF is sitting right there, perfectly parseable.
    try:
        markdown = Path(doc.text_path).read_text(encoding="utf-8", errors="replace")
        records = passages.sidecar_path(doc.citekey).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    # Each form feed becomes the paragraph break it sits inside, rather
    # than being deleted: Docling writes them surrounded by blank lines,
    # but a form feed flush against the text either side would otherwise
    # fuse the last word of one page onto the first word of the next.
    # encoding spelled out on the way back down, not just on the way up:
    # write_text without one encodes with the *platform* encoding, so any
    # non-ASCII paper fails with UnicodeEncodeError under a C-locale host.
    out_path.write_text(re.sub(r"\n{3,}", "\n\n", markdown.replace("\f", "\n\n")), encoding="utf-8")
    (config.DOCLING_DIR / f"{stem}.passages.json").write_text(records, encoding="utf-8")
    return True
