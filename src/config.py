"""Central configuration for the research pipeline.

Defaults live in config.toml (repo root); any value can be overridden
with an environment variable of the same name (e.g.
BIB_FILE=/path/to/other.bib python -m src.corpus sync) without editing the file.
tomllib is stdlib since Python 3.11, so this adds no dependency.
"""

import math
import os
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", str(REPO_ROOT / "config.toml")))

# config.toml is gitignored per-host data (every user edits the parser
# backend, the paths, the worker count), so a fresh clone genuinely does
# not have one -- this is the first thing a new user hits, not an edge
# case. Deliberately a hard failure rather than a silent fallback to
# config.toml.example: a host quietly running settings its owner never
# chose is a worse failure than one that refuses to start, and it is the
# kind that surfaces days later as "why did it parse with the wrong
# backend". The message carries the literal command because nothing about
# a bare FileNotFoundError traceback suggests the fix.
try:
    with open(CONFIG_PATH, "rb") as _f:
        _toml = tomllib.load(_f)
except FileNotFoundError as _exc:
    raise FileNotFoundError(
        f"No config file at {CONFIG_PATH}. This repo tracks "
        "config.toml.example and gitignores config.toml, so a fresh clone "
        "has to make its own:\n"
        "    cp config.toml.example config.toml\n"
        "then edit it (parser backend, paths, worker count) to suit this "
        "host. Set the CONFIG_PATH env var to use a file somewhere else."
    ) from _exc


def _get(env_var: str, *toml_path: str, default: str = "") -> str:
    if env_var in os.environ:
        return os.environ[env_var]
    node = _toml
    for key in toml_path:
        if not isinstance(node, dict):
            return default
        node = node.get(key, {})
    return node if isinstance(node, str) else default


def _get_float(env_var: str, *toml_path: str, default: float) -> float:
    if env_var in os.environ:
        return float(os.environ[env_var])
    node = _toml
    for key in toml_path:
        if not isinstance(node, dict):
            return default
        node = node.get(key, {})
    if isinstance(node, (int, float)) and not isinstance(node, bool):
        return float(node)
    return default


def _get_optional_float(env_var: str, *toml_path: str,
                        default: "float | None" = None) -> "float | None":
    """A positive duration in seconds, or None for "no limit".

    _get_float can't express this: it requires a float default, and
    spelling "off" as 0 in a config file reads as "zero seconds", which
    is the opposite of what it means. The off switch is therefore an
    explicit word -- an empty value, "off", "none" or "false" -- and 0 is
    rejected outright rather than quietly reinterpreted.

    `default` applies when the setting is absent entirely. An explicit
    "off" still means off -- the two cases have to stay distinguishable,
    or a setting with a non-None default could never be switched off.

    Validated at load, like _get_workers, so a bad value is reported
    where it was written rather than as a strange timeout much later.
    """
    raw = _raw_setting(env_var, toml_path)
    if raw is None:
        return default
    # Checked for both sources, not just the environment: the shipped
    # config.toml.example writes `document_timeout = "off"`, so the TOML
    # path is the one every new user actually takes.
    if isinstance(raw, str):
        raw = raw.strip()
        if raw.lower() in ("", "off", "none", "false"):
            return None  # explicitly off, regardless of `default`
    # Built once, raised from three places: the three failure modes -- a
    # non-numeric type, an unparseable string, a non-positive or infinite
    # number -- all deserve the same message, and stating it three times
    # is how the copies drift.
    complaint = ValueError(
        f"{'/'.join(toml_path)} (or {env_var}) must be a positive number of "
        f'seconds, or "off", not {raw!r}.'
    )
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        raise complaint
    try:
        seconds = float(raw)
    except ValueError:
        raise complaint from None
    if not math.isfinite(seconds) or seconds <= 0:
        raise complaint
    return seconds


def _raw_setting(env_var: str, toml_path: tuple[str, ...]):
    """The unparsed value of one setting: the env var if set, else the
    TOML node at `toml_path`, else None. Shared lookup for the getters
    that need to distinguish "absent" from every real value."""
    if env_var in os.environ:
        return os.environ[env_var]
    node = _toml
    for key in toml_path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def _get_bool(env_var: str, *toml_path: str, default: bool) -> bool:
    """Env vars arrive as strings, so "false"/"0"/"no" have to be read as
    False -- bool("false") is True, which would make every documented way
    of turning a setting off via the environment silently turn it on."""
    if env_var in os.environ:
        return os.environ[env_var].strip().lower() in ("1", "true", "yes", "on")
    node = _toml
    for key in toml_path:
        if not isinstance(node, dict):
            return default
        node = node.get(key, {})
    return node if isinstance(node, bool) else default


# REPO_ROOT / <absolute path> correctly collapses to the absolute path
# (pathlib behavior), so env var overrides may be absolute or relative.
BIB_FILE_PATH = REPO_ROOT / _get("BIB_FILE", "bib", "path", default="papers/bibliography.bib")

# Which BibTeX field carries Zotero collection membership. `groups` is
# JabRef's, and what Better BibTeX writes under "Export JabRef-specific
# fields" -- see src/bib_collections.py for why that option is the only
# way collections reach a .bib at all. Configurable rather than hardcoded
# because a user whose exporter puts them somewhere else (a `keywords`
# convention, say) should not have to patch the parser to be read.
BIB_COLLECTIONS_FIELD = _get("BIB_COLLECTIONS_FIELD", "bib", "collections_field",
                             default="groups").strip().lower()

CONTENT_DIR = REPO_ROOT / _get("CONTENT_DIR", "content", "dir", default="content")
PARSED_DIR = CONTENT_DIR / "parsed"
LEDGER_PATH = CONTENT_DIR / "ledger.sqlite"
# Every report the review layer writes, one directory per draft,
# mirroring the draft's own path under DRAFTS_DIR: a draft at
# content/drafts/<topic>/survey.md has its provenance, verbatim and
# coverage reports at content/review/<topic>/survey.<aid>.md, alongside
# the .tex/.pdf renders of each. See src/review/__init__.py and
# docs/ARCHITECTURE.md's "Layer 4: the review layer".
#
# Named for the layer, not for one of its three aids: all three write
# here. The genre skills' own section-to-citekey JSON is not a review
# artefact and does not -- it is drafting state, and lives in the
# dossier directory.
REVIEW_DIR = CONTENT_DIR / "review"
# Where a genre skill saves its draft, and where src/dossier.py keeps the
# working state that produced it -- one dossier directory per draft,
# mirroring the draft's own path under DRAFTS_DIR (docs/DRAFT-ITERATION.md).
# Separate from REVIEW_DIR, which holds reports generated *from* a
# finished draft rather than the state that produced it.
DRAFTS_DIR = CONTENT_DIR / "drafts"
DOSSIERS_DIR = CONTENT_DIR / "dossiers"
# Cached BM25 term-frequency index for src/retrieval.py -- keyed by a
# cheap per-item fingerprint (parsed-file stat, not content), so a
# search() call only re-tokenizes docs whose text actually changed since
# the last run, mirroring src/ledger.py's own stat-before-hash skip logic.
RETRIEVAL_INDEX_PATH = CONTENT_DIR / "retrieval_index.json"
# Cached n-gram fingerprints for src/overlap_index.py -- content/overlap/docs/
# holds one file per citekey, content/overlap/index.bin the merged corpus
# index. Both are keyed by (pdf_hash, parsed-file size/mtime_ns), the same
# stat-before-hash shape as RETRIEVAL_INDEX_PATH above.
OVERLAP_DIR = CONTENT_DIR / "overlap"
# Boilerplate phrases (acronyms, fixed phrasing, defined terms, whole
# paragraphs) src/review/verbatim_check.py's `scan` should never flag --
# see docs/PLAGIARISM.md. Per-host, hand-edited data, like content/library.bib:
# gitignored, absent on a fresh clone (scan treats that as "no
# suppressions configured", not an error), and never what one host waved
# through is not another host's decision to make. Fixed under CONTENT_DIR
# rather than independently relocatable like BIB_FILE_PATH -- there's no
# case for pointing this at a second location.
VERBATIM_ALLOWLIST_PATH = CONTENT_DIR / "verbatim_allowlist.toml"
# Mutex for anything that writes content/ -- see src/runlock.py. A
# dedicated sqlite file rather than the ledger, so that locking a run
# doesn't force the ledger's five commit points into one transaction.
PIPELINE_LOCK_PATH = CONTENT_DIR / "pipeline.lock.db"

# Which backend src/pdf_text.py dispatches to -- see config.toml's
# [parser] comment for the tradeoffs (speed, page-boundary loss) before
# switching off the default.
PARSER_BACKENDS = ("pdftotext", "docling")
PARSER = _get("PARSER", "parser", "backend", default="pdftotext")
# Whether the docling backend runs its OCR stage. Docling's own default
# is on; this project's is off -- a speed/completeness trade-off, not a
# free win. Measured over the full corpus, OCR costs 2.08x serially but
# 3.91x at 12 workers and 4.79x at 24: it is CPU-bound, so it competes
# with the parallelism. (An older 2.46x figure came from a 16-PDF serial
# sample.) Turning it off changed the extracted text of 8 of 16 sampled
# documents,
# because OCR is what reads text embedded as *bitmaps*. Mostly that text
# is publisher furniture and figure captions; on one document it was two
# whole tables. See config.toml's [parser].ocr comment, or README's
# "OCR: off by default" section, before changing it either way. (The full
# write-up is bench/RESULTS.md, which is developer-only and not shipped.)
PARSER_OCR = _get_bool("PARSER_OCR", "parser", "ocr", default=False)


def _get_workers(env_var: str, *toml_path: str, default: int) -> "int | str":
    """A positive int, or the literal "auto" -- the only setting here
    that isn't a plain str/float/bool.

    Validated at load rather than where the pool is built, because the
    symptom of a bad value there ("0 workers", "-1 workers") surfaces far
    from its cause. `bool` is rejected explicitly: TOML's `workers = true`
    parses as a bool, and bool is an int subclass in Python, so without
    this it would quietly mean "1 worker" instead of being called out.
    """
    if env_var in os.environ:
        raw = os.environ[env_var]
    else:
        node = _toml
        for key in toml_path:
            if not isinstance(node, dict):
                node = None
                break
            node = node.get(key)
        raw = node
    if raw is None:
        return default
    if isinstance(raw, str):
        if raw.strip().lower() == "auto":
            return "auto"
        raw = raw.strip()
    if isinstance(raw, bool) or not isinstance(raw, (int, str)):
        raise ValueError(
            f"{'/'.join(toml_path)} (or {env_var}) must be a positive integer "
            f'or "auto", not {raw!r}.'
        )
    try:
        workers = int(raw)
    except ValueError:
        raise ValueError(
            f"{'/'.join(toml_path)} (or {env_var}) must be a positive integer "
            f'or "auto", not {raw!r}.'
        ) from None
    if workers < 1:
        raise ValueError(
            f"{'/'.join(toml_path)} (or {env_var}) must be a positive integer "
            f'or "auto", not {raw!r}.'
        )
    return workers


# How many documents sync parses at once. 1 keeps the historical, strictly
# serial behaviour -- no pool, no subprocesses -- so raising this is an
# opt-in. See config.toml.example's [parser].workers comment for how the
# requested value is clamped against what the host can actually sustain,
# and src/pdf_text.resolve_workers for the arithmetic.
PARSER_WORKERS = _get_workers("PARSER_WORKERS", "parser", "workers", default=1)


def _get_start_method(env_var: str, *toml_path: str, default: str) -> str:
    """One of PARSER_START_METHODS.

    Its own loader rather than a bare _get so a typo ("forkserv") is
    reported here, naming the alternatives, instead of surfacing as a
    ValueError out of multiprocessing.get_context() once a pool is
    already being built -- same reasoning as _get_workers.
    """
    raw = _get(env_var, *toml_path, default=default).strip().lower()
    if raw not in PARSER_START_METHODS:
        raise ValueError(
            f"{'/'.join(toml_path)} (or {env_var}) must be one of "
            f"{', '.join(PARSER_START_METHODS)}, not {raw!r}."
        )
    return raw


# How the docling worker pool creates its processes. "auto" picks
# forkserver where the platform has it and spawn everywhere else; the
# other two force one. Only ever consulted when [parser].workers > 1 and
# the backend is docling, since nothing else uses a process pool.
#
# Measured, wall clock for a pool to reach its first parsed document:
# forkserver 9.6s against spawn 11.3s at four workers. The saving is one
# shared import of torch+docling rather than one per worker; the model
# load that dominates the rest is per process either way. End to end this
# is a fixed 1.3-2.2s, which is ~10% of an eight-document run and under
# 1% of a full-corpus one. Plain "fork" is deliberately not offered -- see
# src/pdf_text.start_method.
PARSER_START_METHODS = ("auto", "forkserver", "spawn")
PARSER_START_METHOD = _get_start_method(
    "PARSER_START_METHOD", "parser", "start_method", default="auto")

# Give up on a single document after this many seconds, or None for no
# limit. Applies to both backends, by the mechanism each one has:
# docling's own PdfPipelineOptions.document_timeout, and a subprocess
# timeout for pdftotext. Off by default -- any value has to clear the
# slowest legitimate document in the corpus, and this project's is a
# 675-page book that took 246s on its own, so a number that is safe here
# is not necessarily safe elsewhere.
PARSER_DOCUMENT_TIMEOUT = _get_optional_float(
    "PARSER_DOCUMENT_TIMEOUT", "parser", "document_timeout")

# Give up on a parallel run when *no* document at all has completed for
# this long, or None to wait forever. Not a per-document deadline: with
# several workers on a real corpus completions arrive constantly, so
# total silence discriminates a hung worker from a merely slow document
# far better than any per-document number could -- which matters because
# the slowest legitimate document here takes 246s.
#
# On by default, unlike most safety valves in this file, because the
# failure it catches is one a user actually hit: a wedged run that never
# finishes and cannot be interrupted. The default is deliberately loose
# (7x that slowest document), and the cost of a false positive is now
# small -- since v1.2.0 the affected documents are marked failed and
# retried on the next run, rather than lost.
PARSER_STALL_TIMEOUT = _get_optional_float(
    "PARSER_STALL_TIMEOUT", "parser", "stall_timeout", default=1800.0)

# Parse-quality guard (src/pdf_text.quality_warning): a PDF extractor
# that sets its glyph-spacing tolerance too coarse fuses adjacent words
# together, which src/retrieval.py's whitespace tokenizer then cannot
# match against. Measured over the same 10 PDFs, pdftotext produced
# 0.01% such tokens and a since-removed backend produced 4.19% -- three
# orders of magnitude apart -- so 1% sits well clear of both.
PARSE_LONG_WORD_CHARS = int(_get_float("PARSE_LONG_WORD_CHARS", "parser",
                                       "long_word_chars", default=20))
PARSE_LONG_WORD_RATIO = _get_float("PARSE_LONG_WORD_RATIO", "parser",
                                   "long_word_ratio", default=0.01)
# Below this many words the ratio is too noisy to mean anything (a
# cover page, or a scan that yielded almost no text).
PARSE_MIN_TOKENS = int(_get_float("PARSE_MIN_TOKENS", "parser", "min_tokens", default=200))


def _get_log_level(env_var: str, *toml_path: str, default: str) -> str:
    """One of LOG_LEVELS, case-insensitive on input, canonical on output.

    Own loader rather than a bare _get, same reasoning as
    _get_start_method: a typo ("WARN" instead of "WARNING") is reported
    here, naming the alternatives, instead of surfacing later as a
    logging module error once a handler is already being configured.
    """
    raw = _get(env_var, *toml_path, default=default).strip().upper()
    if raw not in LOG_LEVELS:
        raise ValueError(
            f"{'/'.join(toml_path)} (or {env_var}) must be one of "
            f"{', '.join(LOG_LEVELS)}, not {raw!r}."
        )
    return raw


# How much the pipeline writes to logs/pipeline.log (see LOGS_DIR
# below) -- one of the standard library's own level names. Deliberately
# the only [logging] setting: rotation size/backup count are fixed in
# logging_setup.py rather than exposed here, since nothing so far has
# needed them to vary per host.
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
LOGGING_LEVEL = _get_log_level("LOGGING_LEVEL", "logging", "level", default="INFO")
# No config.toml key, unlike the paths above -- a fixed, predictable
# location alongside the source tree rather than another per-host
# setting to document. Still an env-var override though, same mechanism
# CONFIG_PATH above uses (plain os.environ.get, not _get, since there's
# no [logging].dir to also check) -- every other path constant in this
# file gets one, and a real subprocess CLI test needs to point this
# somewhere other than this checkout's own logs/. Gitignored; see
# src/logging_setup.py for what lands here and why it is one file.
LOGS_DIR = Path(os.environ.get("LOGS_DIR", str(REPO_ROOT / "logs")))

# src/review/citation_provenance.py band thresholds: the fraction of a citing
# sentence's distinctive words that must appear in the best-matching
# source passage. Round numbers on purpose -- they set reading order for
# a human, not a pass/fail line, so precision here would be false
# precision. Below WEAK a finding is reported as "no support found",
# which means "go look", never "this citation is wrong".
PROVENANCE_WEAK_SCORE = _get_float("PROVENANCE_WEAK_SCORE", "provenance",
                                   "weak_score", default=0.20)
PROVENANCE_GOOD_SCORE = _get_float("PROVENANCE_GOOD_SCORE", "provenance",
                                   "good_score", default=0.50)

# Heavier optional pipeline (pyproject.toml's "enrich" Poetry group), per src/enrich/.
DOCLING_DIR = CONTENT_DIR / "docling"
# Per-doc (size, mtime_ns) PDF fingerprint, so docling_parse.parse_doc()
# only re-runs Docling's layout/OCR models -- the slowest stage in this
# pipeline -- for a PDF that's new or has actually changed since the last
# call, mirroring src/ledger.py's own stat-before-hash skip logic.
DOCLING_CACHE_PATH = CONTENT_DIR / "docling_cache.json"
# Whether docling_parse.py also extracts figure bitmaps (into
# content/docling/<doc>_artifacts/) plus a <doc>.figures.json index of
# page/caption/citation for each. Changing this invalidates the whole
# Docling cache -- it changes what every .md should contain, so the next
# run re-parses the corpus from scratch. See DEVELOPER.md's "Figures".
DOCLING_IMAGES = _get_bool("DOCLING_IMAGES", "enrich", "docling_images", default=False)
# Render scale for those bitmaps; 2.0 is ~144 DPI, legible for reading a
# figure back while checking a draft without storing print-resolution PNGs.
DOCLING_IMAGE_SCALE = _get_float("DOCLING_IMAGE_SCALE", "enrich",
                                 "docling_image_scale", default=2.0)
CHROMA_DIR = CONTENT_DIR / "chroma"

TOPICS_PATH = CONTENT_DIR / "topics.json"
# Per-doc whole-text embedding cache keyed by content hash, so
# topic_model.run_topic_model() only re-encodes docs whose text actually
# changed since the last run -- see that module's docstring.
TOPIC_EMBED_CACHE_PATH = CONTENT_DIR / "topic_embed_cache.json"
RENDERED_DIR = CONTENT_DIR / "rendered"

# The CSL style pandoc's --citeproc formats citations and the bibliography
# with. Vendored (assets/csl/) rather than fetched, so rendering works with
# no network and so a style change can never silently renumber a draft that
# was already reviewed -- see assets/csl/README.md.
CSL_STYLE_PATH = REPO_ROOT / _get("CSL_STYLE", "render", "csl", default="assets/csl/ieee.csl")

# The Vale configuration `python -m src.draft style` checks a draft
# against, vendored at assets/vale/ for the reason assets/csl/ieee.csl is:
# a style fetched at run time is not the style that was reviewed, and a
# check whose rules differ per clone is not a check. Overridable so a user
# can point at their own house style without editing what ships.
VALE_CONFIG_PATH = REPO_ROOT / _get("VALE_CONFIG", "style", "vale_config",
                                    default="assets/vale/vale.ini")

# A fallback dialect for a draft whose dossier records none -- the
# standing preference docs/HOUSE-STYLE.md calls for under "What persists
# across drafts", where a user who has chosen en-GB four times has a
# default and re-choosing it is friction rather than a decision.
#
# It is a fallback, never an override: scope.md wins, because a thesis at
# an Indian university and an IEEE submission legitimately differ and the
# per-draft record is the one that knows which this is. Empty by default,
# and `src.draft style` names which source a dialect came from, so a draft
# checked against this is never checked against it silently.
STYLE_LANGUAGE = _get("STYLE_LANGUAGE", "style", "language", default="")
# Whether a run of consecutive citation numbers collapses ([3]-[6] rather
# than [3], [4], [5], [6]). IEEE's own guide shows the collapsed form, but
# upstream ieee.csl doesn't produce it; render_output.py injects the one
# attribute that does, into a temp copy. False renders whatever the style
# on disk says, unmodified.
RENDER_COLLAPSE_CITATIONS = _get_bool(
    "RENDER_COLLAPSE_CITATIONS", "render", "collapse_citations", default=True
)

EMBEDDING_MODEL = _get(
    "EMBEDDING_MODEL", "enrich", "embedding_model",
    default="sentence-transformers/all-MiniLM-L6-v2",
)


# --------------------------------------------------------------------------
# Path containment
# --------------------------------------------------------------------------
#
# Lives here rather than in any one tool because all three of the tier-1,
# stdlib-only tools need it and none of them can import each other:
# src/render_output.py already imports src/citation_gate.py, so a shared
# helper in either of those two would close a cycle. This module imports
# nothing from src/ and owns CONTENT_DIR, which makes "is this path inside
# the content directory" its question to answer.


class OutsideContentDir(RuntimeError):
    """A path a tool was asked to read or write lies outside CONTENT_DIR.

    Raised rather than worked around. Every path this pipeline reads or
    writes lives under `content/`, which is what makes a `dossier export`
    or a copy of that one directory a complete record of the work -- a
    draft kept somewhere else is invisible to backup, to `dossier`, and
    to every later revision.
    """


def resolves_inside(path: Path, root: Path) -> bool:
    """Whether `path` really lives under `root`, once both are resolved.

    Resolving both sides is the whole point: it is what makes a symlink
    and a `..` component answer for where they actually land rather than
    for how they are spelled.
    """
    return Path(path).resolve().is_relative_to(Path(root).resolve())


def mirrored_dir(path: Path, source_root: Path, target_root: Path) -> "Path | None":
    """`target_root` carrying `path`'s own place under `source_root`.

    The one rule four directories under `content/` obey: a draft at
    `content/drafts/<topic>/survey.md` has its renders at
    `content/rendered/<topic>/`, its dossier at
    `content/dossiers/<topic>/survey/`, and its review reports at
    `content/review/<topic>/`. One topic directory, one draft's worth of
    everything.

    Returns `None` when `path` is not under `source_root`, rather than
    picking an answer, because the callers disagree about what that means
    and each is right for itself. `render_output._output_dir` and
    `review.report_path` fall back to the flat target directory: both
    accept an input that is legitimately elsewhere under `content/`, and
    writing its output flat is a better answer than refusing to produce
    any. `dossier.dossier_dir` raises, because a dossier written
    somewhere unmirrored would be found by nothing later. Policy stays
    with the caller; only the rule lives here.

    Note this says nothing about which inputs a caller will *accept* --
    that is a separate decision each one makes for itself, before it gets
    here (`render_output` and `references` confine reads to `content/`
    with `require_inside_content`, and `review.require_reviewable` does
    the same for the three review aids).

    Only the part of `path` *below* `source_root` is ever carried over,
    and both sides are resolved before being compared, so the result can
    hold neither a `..` nor a symlink's spelling. It is still the
    caller's job to check the result resolves inside `target_root`:
    `source_root` and `target_root` are configuration, and a symlinked
    one can land outside without any argument being at fault.

    Lives here rather than in either caller because `src/render_output.py`
    is committed to stdlib plus `config`/`citation_gate`/`references` so a
    genre skill can render under bare `python` -- it cannot import
    `src/dossier.py`, and before this the rule was written out three times
    and missed in a fourth place (`citation_provenance`), which is how
    two drafts named `survey.md` came to share one report.
    """
    try:
        relative = Path(path).resolve().relative_to(Path(source_root).resolve())
    except ValueError:
        return None
    return Path(target_root) / relative.parent


def require_inside_content(path: Path, what: str = "draft") -> Path:
    """Returns `path`, having refused it if it resolves outside CONTENT_DIR."""
    if not resolves_inside(path, CONTENT_DIR):
        raise OutsideContentDir(
            f"{path} resolves to {Path(path).resolve()}, outside the content "
            f"directory {CONTENT_DIR.resolve()}. This pipeline reads and writes "
            f"only under content/, so that one directory is the whole record of "
            f"the work -- move the {what} under content/drafts/ (where the genre "
            f"skills save one, and the only place whose path is mirrored into "
            f"content/rendered/), or point [content].dir in config.toml at the "
            f"tree you are really working in."
        )
    return Path(path)
