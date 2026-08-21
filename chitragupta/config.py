"""Central configuration for the research pipeline.

Defaults live in config.toml (repo root); any value can be overridden
with an environment variable of the same name (e.g.
BIB_FILE=/path/to/other.bib python -m chitragupta.corpus sync) without editing the file.
tomllib is stdlib since Python 3.11, so this adds no dependency.
"""

import math
import os
import tomllib
from pathlib import Path

# Two roots, because `REPO_ROOT` was doing two unrelated jobs under one
# name and they stop being the same directory the moment this code is
# installed rather than cloned (docs/PACKAGING.md).
#
#   PACKAGE_ROOT  -- where the code is. Follows the code.
#   PROJECT_ROOT  -- where the user's corpus, drafts and config are.
#                    Follows the user.
#
# In a git checkout they are the same directory and nothing about this
# module's behaviour changes; that equality is what let the split land
# before anything was renamed.
PACKAGE_ROOT = Path(__file__).resolve().parent

# The marker that identifies a project directory. Deliberately the file
# this module already refuses to start without, so there is nothing new
# for a user to create -- and a real file rather than a heuristic, so
# "am I in a project?" has one answer rather than a guess.
PROJECT_MARKER = "config.toml"


def shipped(*parts: str) -> Path:
    """A file that ships with the code, not with the user's project.

    The CSL style, the Vale rules and the default acronym list are the
    project's own vendored assets: a user gets them by installing, never
    by authoring them. They therefore resolve from the code's location,
    not the user's working directory.

    One function rather than a constant because it is the single seam
    that changes when `assets/` moves under the import package (#261) and
    this becomes an `importlib.resources` call. Today the assets are a
    sibling of the package, so this reaches up one level; every caller is
    already written against the seam rather than against that fact.
    """
    return PACKAGE_ROOT.parent.joinpath(*parts)


def discover_project_root(cwd: "Path | None" = None,
                          environ: "dict | None" = None) -> "Path | None":
    """The project directory, or None when there is no project here.

    Order, first hit wins:

    1. `CHITRAGUPTA_PROJECT`, so an explicit answer always beats a
       discovered one.
    2. The nearest ancestor of the working directory holding a
       `config.toml` -- how an installed `chitragupta` finds the project
       the user is standing in.
    3. The directory above the package, when *it* holds one. This is the
       git checkout, and it is what keeps every existing invocation
       working from anywhere, exactly as deriving the root from
       `__file__` used to.

    Note what is deliberately *not* here: `CONFIG_PATH`. That variable
    has always meant "read this file", never "the project lives beside
    this file" -- `tests/test_config.py::test_custom_config_path` pins
    that a custom config still resolves a relative `[bib] path` against
    the checkout. Folding it in would silently move a user's whole data
    root as a side effect of naming a config file.
    """
    environ = os.environ if environ is None else environ
    explicit = environ.get("CHITRAGUPTA_PROJECT")
    if explicit:
        return Path(explicit)
    start = (Path.cwd() if cwd is None else Path(cwd)).resolve()
    for candidate in (start, *start.parents):
        if (candidate / PROJECT_MARKER).is_file():
            return candidate
    beside_package = PACKAGE_ROOT.parent
    if (beside_package / PROJECT_MARKER).is_file():
        return beside_package
    return None


# Falls back to the directory above the package when no project was
# found, so the error below names the path a checkout would have used --
# `cp config.toml.example config.toml` is only actionable if the message
# points somewhere the reader recognises.
PROJECT_ROOT = discover_project_root() or PACKAGE_ROOT.parent
CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", str(PROJECT_ROOT / PROJECT_MARKER)))

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


# PROJECT_ROOT / <absolute path> correctly collapses to the absolute path
# (pathlib behavior), so env var overrides may be absolute or relative.
BIB_FILE_PATH = PROJECT_ROOT / _get("BIB_FILE", "bib", "path", default="papers/bibliography.bib")

# Which BibTeX field carries Zotero collection membership. `groups` is
# JabRef's, and what Better BibTeX writes under "Export JabRef-specific
# fields" -- see chitragupta/bib_collections.py for why that option is the only
# way collections reach a .bib at all. Configurable rather than hardcoded
# because a user whose exporter puts them somewhere else (a `keywords`
# convention, say) should not have to patch the parser to be read.
BIB_COLLECTIONS_FIELD = _get("BIB_COLLECTIONS_FIELD", "bib", "collections_field",
                             default="groups").strip().lower()

CONTENT_DIR = PROJECT_ROOT / _get("CONTENT_DIR", "content", "dir", default="content")
PARSED_DIR = CONTENT_DIR / "parsed"
LEDGER_PATH = CONTENT_DIR / "ledger.sqlite"
# Every report the review layer writes, one directory per draft,
# mirroring the draft's own path under DRAFTS_DIR: a draft at
# content/drafts/<topic>/survey.md has its provenance, verbatim and
# coverage reports at content/review/<topic>/survey.<aid>.md, alongside
# the .tex/.pdf renders of each. See chitragupta/review/__init__.py and
# docs/ARCHITECTURE.md's "Layer 4: the review layer".
#
# Named for the layer, not for one of its three aids: all three write
# here. The genre skills' own section-to-citekey JSON is not a review
# artefact and does not -- it is drafting state, and lives in the
# dossier directory.
REVIEW_DIR = CONTENT_DIR / "review"
# Where a genre skill saves its draft, and where chitragupta/dossier/ keeps the
# working state that produced it -- one dossier directory per draft,
# mirroring the draft's own path under DRAFTS_DIR (docs/DRAFT-ITERATION.md).
# Separate from REVIEW_DIR, which holds reports generated *from* a
# finished draft rather than the state that produced it.
DRAFTS_DIR = CONTENT_DIR / "drafts"
DOSSIERS_DIR = CONTENT_DIR / "dossiers"
# The outline a book is generated from, one directory per book, mirroring
# the book's own directory under DRAFTS_DIR -- content/drafts/twins/ has
# its outline and its sign-off record at content/specs/twins/. See
# chitragupta/spec.py and docs/BOOKS.md.
#
# Mirrored one level differently from the three above, and deliberately:
# those mirror a *draft*, so they carry the draft's parent directory; a
# book is a directory of drafts, so its own path is what carries over.
SPECS_DIR = CONTENT_DIR / "specs"
# Cached BM25 term-frequency index for chitragupta/retrieval.py -- keyed by a
# cheap per-item fingerprint (parsed-file stat, not content), so a
# search() call only re-tokenizes docs whose text actually changed since
# the last run, mirroring chitragupta/ledger.py's own stat-before-hash skip logic.
RETRIEVAL_INDEX_PATH = CONTENT_DIR / "retrieval_index.json"
# Cached n-gram fingerprints for chitragupta/overlap_index.py -- content/overlap/docs/
# holds one file per citekey, content/overlap/index.bin the merged corpus
# index. Both are keyed by (pdf_hash, parsed-file size/mtime_ns), the same
# stat-before-hash shape as RETRIEVAL_INDEX_PATH above.
OVERLAP_DIR = CONTENT_DIR / "overlap"
# Boilerplate phrases (acronyms, fixed phrasing, defined terms, whole
# paragraphs) chitragupta/review/verbatim_check.py's `scan` should never flag --
# see docs/PLAGIARISM.md. Per-host, hand-edited data, like content/library.bib:
# gitignored, absent on a fresh clone (scan treats that as "no
# suppressions configured", not an error), and never what one host waved
# through is not another host's decision to make. Fixed under CONTENT_DIR
# rather than independently relocatable like BIB_FILE_PATH -- there's no
# case for pointing this at a second location.
VERBATIM_ALLOWLIST_PATH = CONTENT_DIR / "verbatim_allowlist.toml"
# Mutex for anything that writes content/ -- see chitragupta/runlock.py. A
# dedicated sqlite file rather than the ledger, so that locking a run
# doesn't force the ledger's five commit points into one transaction.
PIPELINE_LOCK_PATH = CONTENT_DIR / "pipeline.lock.db"

# Which backend chitragupta/pdf_text.py dispatches to -- see config.toml's
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
# and chitragupta/pdf_text.resolve_workers for the arithmetic.
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
# chitragupta/pdf_text.start_method.
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

# Parse-quality guard (chitragupta/pdf_text.quality_warning): a PDF extractor
# that sets its glyph-spacing tolerance too coarse fuses adjacent words
# together, which chitragupta/retrieval.py's whitespace tokenizer then cannot
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
# chitragupta/logging_setup.py for what lands here and why it is one file.
LOGS_DIR = Path(os.environ.get("LOGS_DIR", str(PROJECT_ROOT / "logs")))

# chitragupta/review/citation_provenance.py band thresholds: the fraction of a citing
# sentence's distinctive words that must appear in the best-matching
# source passage. Round numbers on purpose -- they set reading order for
# a human, not a pass/fail line, so precision here would be false
# precision. Below WEAK a finding is reported as "no support found",
# which means "go look", never "this citation is wrong".
PROVENANCE_WEAK_SCORE = _get_float("PROVENANCE_WEAK_SCORE", "provenance",
                                   "weak_score", default=0.20)
PROVENANCE_GOOD_SCORE = _get_float("PROVENANCE_GOOD_SCORE", "provenance",
                                   "good_score", default=0.50)

# Heavier optional pipeline (pyproject.toml's "enrich" Poetry group), per chitragupta/enrich/.
DOCLING_DIR = CONTENT_DIR / "docling"
# Per-doc (size, mtime_ns) PDF fingerprint, so docling_parse.parse_doc()
# only re-runs Docling's layout/OCR models -- the slowest stage in this
# pipeline -- for a PDF that's new or has actually changed since the last
# call, mirroring chitragupta/ledger.py's own stat-before-hash skip logic.
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

# The author's own list of topic phrases, and what matching them against
# the corpus produced. TOML in, JSON out, which is this repository's
# standing split rather than a choice made here: the first is hand-written
# and wants comments, the second is written by a program and read by one.
# Neither has to exist -- a library with no seed file gets the emergent,
# unseeded topic model it has always had (chitragupta/seed_topics.py).
SEED_TOPICS_PATH = CONTENT_DIR / "seed_topics.toml"
TOPIC_SEEDS_PATH = CONTENT_DIR / "topic_seeds.json"
# Cosine similarity a document must reach, against a seed phrase's own
# embedding, to be listed under it -- and the same floor BERTopic's
# zero-shot assignment uses, since both measure the same thing in the
# same space with the same model. One key rather than two because two
# would invite them to drift apart and mean nothing together.
#
# Note what this threshold is not: a gate. docs/HOUSE-STYLE.md's R3 keeps
# continuous scores out of pass/fail decisions, and nothing here fails a
# run, blocks a draft or refuses a citekey. It decides how long a list a
# human reads, and they can move it and look again.
#
# A floor, not the selection rule -- and the distinction is what the real
# corpus taught. Selection is per-phrase ranking (SEED_TOPIC_MAX_PAPERS
# below); this only discards matches too weak to be worth ranking at all.
#
# It governs the seed-topic report, and nothing else. It briefly also
# drove BERTopic's zero-shot assignment, which was wrong twice over: the
# two measure the same quantity but make different decisions, and the
# zero-shot path itself is gone -- seeds no longer steer the clustering at
# all, so an author can name any number of them without costing a single
# emergent topic. See chitragupta/enrich/topic_model.py.
#
# Measured over 497 real documents and 14 real Zotero collection names,
# every phrase turned out to have its own score scale, so no single
# absolute cutoff can serve them: "Standards" peaked at 0.295 across the
# whole corpus while "Digital Twin" had a *median* of 0.338. A 0.35 cutoff
# therefore returned nothing at all for a genuine 25-paper topic and 238
# papers for a broad one. Ranking each phrase against itself is immune to
# that; a floor is not, which is why the floor is now low enough to bite
# only on noise.
#
# 0.15 specifically: of four deliberately shelf-like collection names in
# that run, the two with no semantic content at all -- "Others" and a
# person's name, "Karen Wilcox" -- peaked at 0.143 and 0.112, so this
# keeps a seed that means nothing returning nothing rather than its 25
# nearest neighbours.
#
# Stated precisely because the looser claim is tempting and false: the
# other two ("Reviews and Surveys", "opinions") do clear this floor and do
# return papers. A shelf label that is *also* a description of a paper is
# not distinguishable from a topic by score, and this floor does not try
# to. Which names go in the list stays the author's decision, which is the
# answer docs/HOUSE-STYLE.md gives and not a gap in this number.
SEED_TOPIC_MIN_SIMILARITY = _get_float(
    "SEED_TOPIC_MIN_SIMILARITY", "enrich", "seed_topic_min_similarity", default=0.15,
)
# How many papers a single seed topic may list, best-scoring first. The
# actual selection rule: each phrase is ranked against its own scores, so
# a generic word and a domain term both yield a readable list instead of
# nothing and half the corpus respectively.
#
# 25 is a reading length, not an accuracy claim -- this artefact exists to
# be read by a person deciding what to draft, and a topic answering with
# 238 papers has told them nothing. Raise it when a topic is genuinely
# broad and you want the tail.
SEED_TOPIC_MAX_PAPERS = int(_get_float(
    "SEED_TOPIC_MAX_PAPERS", "enrich", "seed_topic_max_papers", default=25,
))
# How fine the emergent topic structure is. The two knobs that decide it,
# in config rather than hardcoded, because the right depth is a property
# of the corpus and its owner rather than of this code.
#
# Defaults chosen by sweeping this project's own 497-document corpus,
# where the previous hardcoded values (10 and unset) were not a tuning
# choice but a ceiling: every clustering parameter saturated at n_docs>=20,
# so a 497-paper corpus and a 5000-paper one both got the settings written
# for a 20-paper one. Measured, holding everything else fixed:
#
#     min_cluster_size=10   13 topics, 27% outliers, median 19 papers
#     min_cluster_size=5    25 topics, 19% outliers, median 13
#     min_cluster_size=3    50 topics, 12% outliers, median 6
#     =3 with min_samples=2 75 topics, 10% outliers, median 5
#
# Note the outlier rate *falls* as the topics get finer: the coarse
# setting was both under-clustering and discarding more of the corpus,
# which is why this is a defect being fixed rather than a preference.
#
# Still clamped down for a small corpus at the point of use -- UMAP's
# spectral initialisation genuinely fails when n_neighbors >= n_samples,
# which is what the original formula existed for. What it never did was
# scale *up*.
TOPIC_MIN_CLUSTER_SIZE = int(_get_float(
    "TOPIC_MIN_CLUSTER_SIZE", "enrich", "topic_min_cluster_size", default=3,
))
# HDBSCAN's own default is min_cluster_size; lowering it makes the
# clustering less conservative and leaves fewer documents as outliers.
TOPIC_MIN_SAMPLES = int(_get_float(
    "TOPIC_MIN_SAMPLES", "enrich", "topic_min_samples", default=2,
))
# UMAP's neighbourhood size, the other half of granularity: smaller
# reads more local structure and yields more, finer topics.
TOPIC_NEIGHBORS = int(_get_float(
    "TOPIC_NEIGHBORS", "enrich", "topic_neighbors", default=10,
))

# Whether the bertopic stage also records, per document, every topic it
# belongs to rather than only the one id fit_transform returns. That
# scalar cannot express a paper genuinely about two things: on 497 real
# documents, 140 belong to more than one topic and the scalar discards
# 222 memberships outright.
#
# Recorded from HDBSCAN's own soft clustering, which is the only
# mechanism of four measured that agrees with the clustering it is
# describing -- its assignment appears in the memberships it produces for
# 100% of documents and leads for 99%, against 30-45% for every
# centroid-distance rule. See chitragupta/enrich/topic_model.py.
#
# Recorded for every run since the zero-shot path was removed: BERTopic
# only swaps its clusterer for a placeholder in that mode, so there is
# always a real one to ask.
TOPIC_DISTRIBUTION = _get_bool(
    "TOPIC_DISTRIBUTION", "enrich", "topic_distribution", default=True,
)
# How strong a topic must be *relative to the document's own strongest*
# to be recorded under it, and how many may be kept at all.
#
# Relative, not an absolute weight, and for the second time in this
# feature the real corpus is what settled it. An absolute 0.05 floor
# recorded 6.99 topics per document out of 7 -- every paper under every
# topic, the dense matrix an absolute floor was supposed to prevent. The
# reason is the same one that broke a fixed cosine cutoff for seed
# phrases: the scale moves. Weights sum to about 1 across however many
# topics BERTopic found, so a fixed floor means something entirely
# different at 7 topics than at 70, and nothing at all at 200.
#
# A document's own strongest weight is the scale that travels. 0.5 keeps
# a genuine second topic -- on a planted two-topic document the winner
# took 0.570 and the real second 0.319, well over half -- while dropping
# the long tail of a document that is diffuse rather than plural.
TOPIC_MEMBERSHIP_RATIO = _get_float(
    "TOPIC_MEMBERSHIP_RATIO", "enrich", "topic_membership_ratio", default=0.5,
)
# The cap, for a document whose weights are near-uniform because BERTopic
# was not confident about it at all: every topic then clears the ratio,
# and "belongs to all 7" is noise wearing the shape of an answer.
TOPIC_MEMBERSHIP_MAX = int(_get_float(
    "TOPIC_MEMBERSHIP_MAX", "enrich", "topic_membership_max", default=3,
))
RENDERED_DIR = CONTENT_DIR / "rendered"

# The CSL style pandoc's --citeproc formats citations and the bibliography
# with. Vendored (assets/csl/) rather than fetched, so rendering works with
# no network and so a style change can never silently renumber a draft that
# was already reviewed -- see assets/csl/README.md.
_CSL_STYLE = _get("CSL_STYLE", "render", "csl", default="")
CSL_STYLE_PATH = ((PROJECT_ROOT / _CSL_STYLE) if _CSL_STYLE
                  else shipped("assets", "csl", "ieee.csl"))

# The Vale configuration `python -m chitragupta.draft style` checks a draft
# against, vendored at assets/vale/ for the reason assets/csl/ieee.csl is:
# a style fetched at run time is not the style that was reviewed, and a
# check whose rules differ per clone is not a check. Overridable so a user
# can point at their own house style without editing what ships.
_VALE_CONFIG = _get("VALE_CONFIG", "style", "vale_config", default="")
VALE_CONFIG_PATH = ((PROJECT_ROOT / _VALE_CONFIG) if _VALE_CONFIG
                    else shipped("assets", "vale", "vale.ini"))

# A fallback dialect for a draft whose dossier records none -- the
# standing preference docs/HOUSE-STYLE.md calls for under "What persists
# across drafts", where a user who has chosen en-GB four times has a
# default and re-choosing it is friction rather than a decision.
#
# It is a fallback, never an override: scope.md wins, because a thesis at
# an Indian university and an IEEE submission legitimately differ and the
# per-draft record is the one that knows which this is. Empty by default,
# and `chitragupta.draft style` names which source a dialect came from, so a draft
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

# The acronym vocabulary a genre skill reads at step 0, so an author's
# own domain expansions travel from one draft to the next instead of
# being re-derived or re-asked in chat every time -- docs/HOUSE-STYLE.md,
# "What persists across drafts". Same declaration shape as
# CSL_STYLE_PATH/VALE_CONFIG_PATH: a vendored default in assets/, one
# config.toml key. Unlike those two, resolving this is never a full
# replacement -- chitragupta/acronyms.py always loads ACRONYMS_DEFAULT_PATH and
# merges ACRONYMS_PATH's file over it when the two differ, because a
# user's own vocabulary and this project's PDF/CPU/URL floor are
# additive, not alternatives. See assets/style/README.md.
ACRONYMS_DEFAULT_PATH = shipped("assets", "style", "acronyms.toml")
_ACRONYMS = _get("ACRONYMS", "style", "acronyms", default="")
ACRONYMS_PATH = (PROJECT_ROOT / _ACRONYMS) if _ACRONYMS else ACRONYMS_DEFAULT_PATH

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
# chitragupta/render_output.py already imports chitragupta/citation_gate.py, so a shared
# helper in either of those two would close a cycle. This module imports
# nothing from chitragupta/ and owns CONTENT_DIR, which makes "is this path inside
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

    Lives here rather than in either caller because `chitragupta/render_output.py`
    is committed to stdlib plus `config`/`citation_gate`/`references` so a
    genre skill can render under bare `python` -- it cannot import
    `chitragupta/dossier/`, and before this the rule was written out three times
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
