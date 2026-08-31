"""Stage 1: Docling PDF parsing.

Layout-aware parsing (headings, tables, reading order) -- a step up from
the corpus layer's plain pdftotext. Needs `docling` from
pyproject.toml's "enrich" Poetry group, in a venv; bulky (its own
layout/OCR models), so this is the stage most likely to be slow or fail
on a small/CPU-only host. Output is Markdown, written per-doc so a
failure on one document doesn't lose progress on the others.

Not the same thing as `[parser].backend = "docling"`, and not made
redundant by it. That setting points chitragupta/pdf_text.py at the same library
to produce one .txt per citekey for BM25; this stage produces structured
Markdown plus the `<doc>.passages.json` sidecar for the whole corpus,
always, whatever that setting says.

What it no longer does is repeat work the corpus layer has already done.
When that setting *is* `docling`, `_reuse_corpus_parse` adopts the
existing parse for a citekey instead of converting the PDF a second time.
The dependency runs one way only, which is the way this package is
allowed to depend: the enrichment layer reads the corpus layer's
artefacts, and nothing in the corpus layer is shaped to make that
possible (see `pdf_text.docling_process_pool`'s docstring for the same
rule applied to imports: this module builds its process pool through
that shared helper rather than importing chitragupta.sync's).

With config.DOCLING_IMAGES on, each doc also gets its figure bitmaps
(in `<stem>_artifacts/`, written by Docling itself) and a
`<stem>.figures.json` index giving each figure's page, caption, and the
string to cite it by. Those images are a reading aid for checking a
draft against its sources -- never draft content, since citing a paper
grants no right to reproduce its figures. See DEVELOPER.md's "Figures
and copyright".

parse_corpus() is incremental: a per-citekey (size, mtime_ns) fingerprint
is cached to config.DOCLING_CACHE_PATH, so a PDF that's unchanged since
the last call skips straight past DocumentConverter -- the slowest stage
in this whole pipeline (373s for 5 PDFs, per DEVELOPER.md's own known-gaps
note this closes). Unlike chitragupta/ledger.py's stat-before-hash, there's no
sha256 fallback here: a same-size edit that also preserves mtime (e.g.
`cp --preserve=timestamps`) slips past this check and the .md stays
stale until something else invalidates the cache entry (deleting it, or
deleting the .md itself -- see below). That's a real gap, not a free
trade-off the way it is in ledger.py (there, hashing is the fallback
that stat merely defers); accepted here because Docling is opt-in
(`enrich.py --stages docling`, not part of `sync`) and a source
this stale-cache-prone is rare enough not to warrant sha256-hashing every
PDF up front just to guard against it. The cache also re-checks that the
expected output file still exists before trusting a fingerprint match,
so manually deleting a .md file forces a re-parse instead of leaving it
silently missing forever.

That fingerprint only sees the *input* PDF, though, so it cannot notice
a change to what this module writes. `_CACHE_VERSION` and the recorded
`config.DOCLING_IMAGES` and `config.PARSER_OCR` settings cover that
second axis: any one of them differing from the cache file invalidates
the whole cache rather than any single entry, since all three change
what every .md should contain.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

from chitragupta import config, logging_setup, passages, pdf_text
from chitragupta.enrich._docling_cache import _load_cache, _save_cache
from chitragupta.enrich._docling_figures import _figure_records, _relativise_image_refs
from chitragupta.enrich._docling_pool import _LazyConverter, _parse_with_pool
from chitragupta.enrich._docling_reuse import (
    _corpus_parse_available,
    _outputs_present,
    _reuse_corpus_parse,
)
from chitragupta.enrich.corpus import CorpusDoc

# Fixed name, not __name__: this module has no __main__ block of its
# own, but naming the logger explicitly keeps it inside the "chitragupta"
# tree logging_setup.configure() pins permissive -- the same trap
# chitragupta/sync.py documents at its own getLogger call.
logger = logging.getLogger("chitragupta.enrich.docling_parse")


def _build_converter(threads: int | None = None) -> Any:
    """Always configured, never bare: `do_ocr` has to be set explicitly
    because Docling's own default is True and this project's is False
    (see config.toml's [parser].ocr for the measurement behind that).
    Picture bitmaps stay off unless config.DOCLING_IMAGES asks for them --
    they're what costs the extra decode time and the artifacts directory.

    Callers should build one of these per *corpus*, not per document:
    DocumentConverter keeps its `initialized_pipelines` cache on the
    instance, so a converter per document re-initialises the layout,
    table and OCR models every time -- 16.5s of measured cold start, on a
    corpus of 501 PDFs. That figure no longer reproduces on docling
    2.117.0, where rebuilding per PDF costs 0.7% (bench/RESULTS.md,
    2026-08-30); the reuse is kept regardless, since the cost belongs to
    the installed docling rather than to this code.
    """
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    opts = PdfPipelineOptions()
    opts.do_ocr = config.PARSER_OCR
    opts.document_timeout = config.PARSER_DOCUMENT_TIMEOUT
    # Under parse_corpus's worker pool each process has claimed its own
    # GPU (pdf_text.init_worker) and been given a share of the host's
    # CPUs. Left alone in the single-worker case, so a default run gets
    # Docling's own accelerator settings unchanged.
    device = pdf_text.worker_device()
    if threads is not None or device is not None:
        from docling.datamodel.accelerator_options import AcceleratorOptions

        kwargs = {}
        if threads is not None:
            kwargs["num_threads"] = threads
        if device is not None:
            kwargs["device"] = device
        opts.accelerator_options = AcceleratorOptions(**kwargs)
    if config.DOCLING_IMAGES:
        opts.generate_picture_images = True
        opts.images_scale = config.DOCLING_IMAGE_SCALE
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
    )


def _fingerprint(doc: CorpusDoc) -> list:
    """(size, mtime_ns) of a doc's PDF -- the cache key parse_doc uses."""
    st = os.stat(doc.pdf_path)
    return [st.st_size, st.st_mtime_ns]


def _is_cached(doc: CorpusDoc, cache: dict) -> bool:
    """Whether parse_doc would skip this document.

    Duplicated from parse_doc's own check rather than refactored out of
    it, because parse_corpus needs the answer *before* dispatching work
    to a pool -- a cached document must not be sent to a worker, or the
    run pays a process and a model load to discover there was nothing to
    do. A stat is nanoseconds next to that.
    """
    try:
        return cache.get(doc.citekey) == _fingerprint(doc) and _outputs_present(doc.citekey)
    except OSError:
        return False


def _convert(doc: CorpusDoc, converter) -> "object":
    """Converter selection plus the conversion itself: builds one only if
    the caller didn't hand one in (a fully-cached run never reaches this
    at all), then raises before anything is written if Docling's result
    is partial rather than complete.
    """
    # Built here rather than in parse_doc, so a fully-cached run never
    # loads Docling's models at all.
    if converter is None:
        converter = _build_converter()
    result = converter.convert(doc.pdf_path)
    # Same hole chitragupta/pdf_text.py closed in v1.2.0, on the other call site:
    # convert(raises_on_error=True) raises only on FAILURE, so a
    # PARTIAL_SUCCESS would otherwise be written to
    # content/docling/<doc>.md as though complete -- and that .md feeds
    # embeddings, topic modelling and citation provenance, where a
    # truncated source is one a claim can be checked against and silently
    # pass. Raised before anything is written, so the document stays
    # uncached and is retried next run.
    pdf_text.check_docling_status(result)
    return result.document


def _write_parse_outputs(doc: CorpusDoc, dl_doc, out_path: Path, stem: str) -> None:
    """The post-parse rewrite: the .md (plus figures.json with images on),
    and the passages.json sidecar every doc gets regardless.
    """
    if config.DOCLING_IMAGES:
        from docling_core.types.doc import ImageRefMode

        # save_as_markdown (not export_to_markdown) so Docling writes the
        # PNGs itself, into <stem>_artifacts/ beside the .md, and points
        # each reference at them. It writes those references as absolute
        # paths, so _relativise_image_refs rewrites them afterwards --
        # see its docstring.
        dl_doc.save_as_markdown(out_path, image_mode=ImageRefMode.REFERENCED)
        image_names = _relativise_image_refs(out_path)
        figures_path = config.DOCLING_DIR / f"{stem}.figures.json"
        figures_path.write_text(
            json.dumps(_figure_records(doc, dl_doc, image_names), indent=2), encoding="utf-8"
        )
    else:
        out_path.write_text(dl_doc.export_to_markdown(), encoding="utf-8")

    # Written for every doc, images on or off: chitragupta/review/citation_provenance.py
    # reads it to quote a real passage rather than a window sliced out of
    # column-spliced flat text. Cheap next to the parse that produced it.
    # Same records the corpus layer writes, from chitragupta/passages.py's one
    # definition of what a passage is -- but under this layer's own
    # directory, because this parse runs under its own OCR and figure
    # settings and must not overwrite the corpus layer's copy.
    passages_path = config.DOCLING_DIR / f"{stem}.passages.json"
    passages_path.write_text(
        json.dumps(passages.passage_records(dl_doc), indent=2), encoding="utf-8"
    )


def parse_doc(doc: CorpusDoc, cache: dict | None = None, converter=None) -> Path:
    """cache, when passed explicitly (parse_corpus does this), is
    mutated in place but NOT persisted by this call -- the caller owns
    save timing. Call with cache=None (the default) for a one-off parse
    that should persist its own result immediately.

    converter follows the same injected-or-owned shape, for the same
    reason cache does: parse_corpus builds one and hands it to every
    document, because building one per document reloads every model per
    document. A standalone call builds its own -- but note that a loop
    of standalone parse_doc() calls pays that cost per document, which is
    what parse_corpus exists to avoid."""
    if not doc.pdf_path:
        raise ValueError(f"{doc.citekey}: no PDF to parse")

    owns_cache = cache is None
    if owns_cache:
        cache = _load_cache()

    config.DOCLING_DIR.mkdir(parents=True, exist_ok=True)
    stem = doc.citekey
    out_path = config.DOCLING_DIR / f"{stem}.md"

    fingerprint = _fingerprint(doc)
    if cache.get(doc.citekey) == fingerprint and _outputs_present(stem):
        return out_path

    # Before the converter, for the same reason as the cache check above:
    # a document the corpus layer has already parsed costs a file copy
    # here instead of a second run of the slowest stage in the repository.
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

    Parallelised by [parser].workers exactly like chitragupta/sync.py, and for
    the same reason: this is the slowest stage in the repository, and a
    first run over a real corpus is measured in tens of minutes. The
    default of 1 keeps the historical serial path, converter reuse and
    all.

    One constraint that comes with the worker pool: every start method it
    can pick (see pdf_text.docling_process_pool) re-imports the calling program's
    __main__ in each worker -- forkserver preloads torch and docling in
    its server process, but the worker still runs spawn's preparation
    step. A script that calls this must therefore guard its top level
    with `if __name__ == "__main__":`, or every worker re-runs it on
    startup and the pool dies with BrokenProcessPool.
    chitragupta/enrich/__main__.py and chitragupta/sync.py both do; an ad-hoc script
    that doesn't will fail immediately rather than subtly.
    """
    cache = _load_cache()
    status = {}

    # A document the corpus layer already parsed is kept out of `pending`
    # for the same reason a cached one is: it must not be sent to a
    # worker, or the run pays a process and a model load to discover
    # there was nothing to parse. parse_doc does the actual adoption,
    # in whichever process ends up calling it.
    # A set of citekeys rather than a list of docs: `d not in [...]` would
    # compare every doc against every reusable one, which is quadratic in
    # the corpus and compares whole dataclasses to do it. A citekey is
    # unique by construction: it is the ledger's primary key.
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
    workers, complaint = pdf_text.resolve_workers(len(pending))
    if complaint:
        logging_setup.say(logger, complaint, level=logging.WARNING)

    if workers > 1:
        _parse_with_pool(docs, pending, cache, status, workers)
    else:
        converter = _LazyConverter()
        for doc in docs:
            try:
                out_path = parse_doc(doc, cache=cache, converter=converter)
                status[doc.citekey] = f"ok: {out_path}"
            except Exception as exc:  # noqa: BLE001  # report per-doc, don't abort the batch
                status[doc.citekey] = f"error: {exc}"
    _save_cache(cache)
    return status
