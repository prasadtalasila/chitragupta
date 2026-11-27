"""Stage 1: Docling PDF parsing.

Layout-aware parsing into per-doc Markdown plus the `<doc>.passages.json`
sidecar for the whole corpus, always. Not made redundant by
`[parser].backend = "docling"` (one .txt per citekey for BM25), but when
that is set `_reuse_corpus_parse` adopts the corpus layer's parse instead
of converting twice; dependency runs enrichment -> corpus only.

With config.DOCLING_IMAGES on, each doc also gets figure bitmaps
(rendered by `_docling_crops`, #600) and a `<stem>.figures.json` index:
a reading aid, never draft content, since citing a paper grants no right
to reproduce its figures (DEVELOPER.md's "Figures and copyright").

parse_corpus() is incremental on a (size, mtime_ns) fingerprint with no
sha256 fallback, so a same-size, mtime-preserving edit stays stale; an
accepted gap, since this stage is opt-in. A missing output forces a
re-parse. `_CACHE_VERSION` and the recorded image and OCR settings
invalidate the whole cache when what is written changes.
"""

import importlib.util
import json
import logging
import os
from pathlib import Path
from typing import Any

from chitragupta import config, logging_setup, passages, pdf_text
from chitragupta.citekey_safety import citekey_path
from chitragupta.enrich._docling_cache import _load_cache, _save_cache
from chitragupta.enrich._docling_figures import write_figure_outputs
from chitragupta.enrich._docling_pool import _LazyConverter, _parse_with_pool
from chitragupta.enrich._docling_reuse import (
    _corpus_parse_available,
    _outputs_present,
    _reuse_corpus_parse,
)
from chitragupta.enrich.corpus import CorpusDoc

# Fixed name, not __name__, to stay inside the "chitragupta" logger tree
# logging_setup.configure() pins (see chitragupta/sync.py).
logger = logging.getLogger("chitragupta.enrich.docling_parse")

# A bib entry with no PDF (a standards page, a website) is not a parse
# failure: reported as `skipped:` (#586), not `error:`, which would make
# the stage `partial` forever and hide real failures among them.
NO_PDF_SKIP = "skipped: no PDF to parse -- a URL-only bibliography entry"

# A document abandoned by a pool that kept dying. Here, not in
# `_docling_pool.py`, so `stages.stage_docling` can read it to escalate
# to `error` (#584) without reaching into a private sibling.
POOL_DEATH_ERROR = "error: parse worker died before this document was parsed"


def _failure_status(doc: CorpusDoc, exc: Exception) -> str:
    """The status a batch records for a document that did not parse."""
    # Decided from the document, not by matching `exc`'s message; the same
    # predicate parse_doc tests, so the two cannot drift.
    return NO_PDF_SKIP if not doc.pdf_path else f"error: {exc}"


def _build_converter(threads: int | None = None) -> Any:
    """A configured converter: `do_ocr` set explicitly because Docling
    defaults to True and this project to False (config.toml's
    [parser].ocr). Picture bitmaps stay off *always* (see the return).
    Build one per *corpus* (see _docling_pool._LazyConverter).
    """
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    opts = PdfPipelineOptions()
    opts.do_ocr = config.PARSER_OCR
    # Explicit, so a docling default change can't flip it: off, a formula
    # reaches the .md and sidecar only as `formula-not-decoded` (#627).
    opts.do_formula_enrichment = config.DOCLING_FORMULAS
    opts.document_timeout = config.PARSER_DOCUMENT_TIMEOUT
    # Under the worker pool each process has its own GPU and CPU share;
    # left alone single-worker, so docling's own settings apply.
    device = pdf_text.worker_device()
    if threads is not None or device is not None:
        from docling.datamodel.accelerator_options import AcceleratorOptions

        kwargs = {}
        if threads is not None:
            kwargs["num_threads"] = threads
        if device is not None:
            kwargs["device"] = device
        opts.accelerator_options = AcceleratorOptions(**kwargs)
    # `generate_picture_images` is never set: docling holds every crop
    # until save_as_markdown (+8.95 GiB on one deck, #600), and the boxes
    # it still reports are all _docling_crops needs.
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
    )


def _fingerprint(doc: CorpusDoc) -> list:
    """(size, mtime_ns) of a doc's PDF -- the cache key parse_doc uses."""
    st = os.stat(doc.pdf_path)
    return [st.st_size, st.st_mtime_ns]


def _is_cached(doc: CorpusDoc, cache: dict) -> bool:
    """Whether parse_doc would skip this document.

    Duplicated from parse_doc because parse_corpus needs it *before*
    dispatch: a cached document sent to a worker pays a process and a
    model load for nothing.
    """
    try:
        return cache.get(doc.citekey) == _fingerprint(doc) and _outputs_present(doc.citekey)
    except OSError:
        return False


def _convert(doc: CorpusDoc, converter) -> "object":
    """Build a converter if none was handed in, convert, and raise before
    anything is written if the result is partial.
    """
    if converter is None:
        converter = _build_converter()
    result = converter.convert(doc.pdf_path)
    # A PARTIAL_SUCCESS would otherwise be written as complete and feed
    # embeddings and citation provenance, where a truncated source lets a
    # claim silently pass. Raised before writing, so it is retried.
    pdf_text.check_docling_status(result)
    return result.document


def _write_parse_outputs(doc: CorpusDoc, dl_doc, out_path: Path, stem: str) -> None:
    """The post-parse rewrite: the .md (plus figures.json with images on),
    and the passages.json sidecar every doc gets regardless.
    """
    out_path.write_text(dl_doc.export_to_markdown(), encoding="utf-8")
    if config.DOCLING_IMAGES:
        # The .md is already whole, placeholders included; figures are
        # purely additive.
        write_figure_outputs(
            doc, dl_doc, out_path, citekey_path(config.DOCLING_DIR, stem, ".figures.json")
        )

    # For every doc: citation_provenance quotes a real passage from it. In
    # this layer's own directory, since this parse uses its own OCR and
    # figure settings and must not overwrite the corpus layer's copy.
    passages_path = citekey_path(config.DOCLING_DIR, stem, ".passages.json")
    passages_path.write_text(
        json.dumps(passages.passage_records(dl_doc), indent=2), encoding="utf-8"
    )


def parse_doc(doc: CorpusDoc, cache: dict | None = None, converter=None) -> Path:
    """Parse one document.

    An explicit `cache` is mutated but NOT persisted (the caller owns save
    timing); cache=None persists immediately. `converter` is injected the
    same way: a loop of standalone calls reloads every model per
    document, which parse_corpus exists to avoid."""
    if not doc.pdf_path:
        raise ValueError(f"{doc.citekey}: no PDF to parse")

    owns_cache = cache is None
    if owns_cache:
        cache = _load_cache()

    config.DOCLING_DIR.mkdir(parents=True, exist_ok=True)
    stem = doc.citekey
    out_path = citekey_path(config.DOCLING_DIR, stem, ".md")

    fingerprint = _fingerprint(doc)
    if cache.get(doc.citekey) == fingerprint and _outputs_present(stem):
        return out_path

    # Before the converter: an already-parsed document costs a file copy.
    if _reuse_corpus_parse(doc, out_path, stem):
        cache[doc.citekey] = fingerprint
        if owns_cache:
            _save_cache(cache)
        return out_path

    dl_doc = _convert(doc, converter)
    _write_parse_outputs(doc, dl_doc, out_path, stem)

    cache[doc.citekey] = fingerprint
    if owns_cache:
        _save_cache(cache)
    return out_path


def parse_corpus(docs: list[CorpusDoc]) -> dict[str, str]:
    """Returns {citekey: 'ok' | 'error: ...'} -- never raises for a single doc failure.

    Parallelised by [parser].workers like chitragupta/sync.py. Every
    start method re-imports the caller's __main__ in each worker, so a
    calling script must guard its top level with
    `if __name__ == "__main__":` or the pool dies with BrokenProcessPool.
    """
    # Probed once, not per document (#509/m-40): otherwise every document
    # fails "No module named 'docling'" and the stage says `partial`.
    if importlib.util.find_spec("docling") is None:
        # By name, not `pdf_text.is_available()`, which answers for
        # `config.PARSER`; this stage always uses docling.
        reason = (
            "skipped: docling is not installed, so this stage cannot run "
            "-- pip install 'chitragupta-cli[enrich]'"
        )
        logging_setup.say(logger, f"  {reason}", level=logging.WARNING)
        return {doc.citekey: reason for doc in docs if doc.pdf_path}

    cache = _load_cache()
    status = {}

    # Already-parsed documents stay out of `pending` like cached ones.
    # A citekey set (the ledger's primary key), not a list of docs, to
    # avoid a quadratic dataclass comparison.
    reusable = {
        d.citekey
        for d in docs
        if d.pdf_path and not _is_cached(d, cache) and _corpus_parse_available(d)
    }
    if reusable:
        logging_setup.say(
            logger,
            f"  reusing the corpus layer's docling parse for "
            f"{len(reusable)} document(s) -- no second parse needed",
        )

    pending = [
        d for d in docs if d.pdf_path and not _is_cached(d, cache) and d.citekey not in reusable
    ]
    workers, complaint = pdf_text.resolve_workers(len(pending), docling=True)
    if complaint:
        logging_setup.say(logger, complaint, level=logging.WARNING)

    if workers > 1:
        _parse_with_pool(docs, pending, cache, status, workers)
    else:
        converter = _LazyConverter()
        for i, doc in enumerate(docs, 1):
            # Opened before the slow call, or a serial run looks hung (#50).
            logging_setup.say(logger, f"  [{i}/{len(docs)}] {doc.citekey}")
            try:
                out_path = parse_doc(doc, cache=cache, converter=converter)
                status[doc.citekey] = f"ok: {out_path}"
            except Exception as exc:  # noqa: BLE001  # report per-doc, don't abort the batch
                status[doc.citekey] = _failure_status(doc, exc)
    _save_cache(cache)
    return status
