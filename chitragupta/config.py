"""Central configuration for the research pipeline.

Defaults live in config.toml (repo root); any value can be overridden
with an environment variable of the same name (e.g.
BIB_FILE=/path/to/other.bib python -m chitragupta.corpus sync) without editing the file.
tomllib is stdlib since Python 3.11, so this adds no dependency.
"""

# Three pieces have moved out, each re-exported so every `config.NAME`
# still resolves: path containment (#441, -> chitragupta/config_path.py),
# the TOML load with the typed getters (#848, -> chitragupta/config_load.py)
# and the [enrich]/[discover] knobs (#848, -> chitragupta/config_enrich.py).
# What stays is project-root discovery, every path under CONTENT_DIR, and
# the corpus, drafting and review settings -- which took this module off
# docs/CODE-STANDARDS.md's C2 register.
#
# The getters moved together with `_toml`, because a getter reads `_toml`
# from its own module's globals: `tests/test_config.py` patches
# `config_load._toml` and then calls the getters as `config._get(...)`,
# which works because the name below is the same function object. The
# two [retrieval] validators (`_get_field_weight`, `_get_bm25_constant`)
# stay here beside the settings they exist for.
#
# Every setting is still read as `config.NAME`: `render_output`,
# `citation_gate`, `style_check` and `acronyms` are tier-1, stdlib-only
# commands (docs/ARCHITECTURE.md) committed to importing only `config`
# alongside each other, not a second settings module.

import importlib
import math
import os
import sys
from pathlib import Path

from chitragupta import config_load, scaffold_guard

from chitragupta.config_load import (
    _get,
    _get_bool,
    _get_choice,
    _get_float,
    _get_int,
    _get_optional_float,
    _get_positive_int,
    _get_workers,
)

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

    The CSL style, the Vale rules, the default acronym list and the
    pandoc Lua filters are the project's own vendored assets: a user
    gets them by installing, never by authoring them. They therefore
    resolve from the code's location, not the user's working directory.

    One function rather than a constant because it is the single seam
    that changes when `assets/` moves under the import package (#261) and
    this becomes an `importlib.resources` call. Today the assets are a
    sibling of the package, so this reaches up one level; every caller is
    already written against the seam rather than against that fact.
    """
    return PACKAGE_ROOT.parent.joinpath(*parts)


def discover_project_root(
    cwd: "Path | None" = None, environ: "dict | None" = None
) -> "Path | None":
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


# #891 gap 1: refuses before anything below if this module's own location
# sits inside a root `chitragupta/init.py`'s SCAFFOLD_MARKER names as
# scaffolded -- the planted-package shape. Checked against this module's
# own `__file__` alone, deliberately before PROJECT_ROOT is discovered
# below: that discovery follows CHITRAGUPTA_PROJECT, which answers "where
# does the user's data live" and must not also decide which `chitragupta`
# is trusted (see chitragupta/scaffold_guard.py's own docstring). Split
# out rather than inlined, like config_load/config_path/config_enrich
# below -- see that module's docstring for why it cannot import this one
# back.
scaffold_guard.refuse_if_shadowed(Path(__file__))

# Falls back to the directory above the package when no project was
# found, so the error below names the path a checkout would have used --
# `cp config.toml.example config.toml` is only actionable if the message
# points somewhere the reader recognises.
PROJECT_ROOT = discover_project_root() or PACKAGE_ROOT.parent
CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", str(PROJECT_ROOT / PROJECT_MARKER)))
# Called here, on every import of this module, rather than at
# config_load's own import: `importlib.reload(config)` has to re-read the
# file, and a reload re-runs this body but not config_load's.
config_load.load(CONFIG_PATH)

# PROJECT_ROOT / <absolute path> correctly collapses to the absolute path
# (pathlib behavior), so env var overrides may be absolute or relative.
BIB_FILE_PATH = PROJECT_ROOT / _get("BIB_FILE", "bib", "path", default="papers/bibliography.bib")

# Which BibTeX field carries Zotero collection membership. `groups` is
# JabRef's, and what Better BibTeX writes under "Export JabRef-specific
# fields" -- see chitragupta/bib_collections.py for why that option is the only
# way collections reach a .bib at all. Configurable rather than hardcoded
# because a user whose exporter puts them somewhere else (a `keywords`
# convention, say) should not have to patch the parser to be read.
BIB_COLLECTIONS_FIELD = (
    _get("BIB_COLLECTIONS_FIELD", "bib", "collections_field", default="groups").strip().lower()
)

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
# chitragupta/spec.py and docs/WRITE-A-BOOK.md.
#
# Mirrored one level differently from the three above, and deliberately:
# those mirror a *draft*, so they carry the draft's parent directory; a
# book is a directory of drafts, so its own path is what carries over.
SPECS_DIR = CONTENT_DIR / "specs"
# Per-citekey TL;DR sidecars chitragupta/tldr.py writes and reads -- one
# JSON file per citekey, keyed to a fingerprint of that citekey's parsed
# text (chitragupta/tldr.py's own docstring has why). Its own directory
# rather than DOSSIERS_DIR: a summary is not part of any one draft's
# working state, it is per-citekey, so it does not mirror a draft's path
# the way DOSSIERS_DIR/REVIEW_DIR/RENDERED_DIR do.
TLDR_DIR = CONTENT_DIR / "tldr"
# Cached BM25 term-frequency index for chitragupta/retrieval.py -- keyed by a
# cheap per-item fingerprint (parsed-file stat, not content), so a
# search() call only re-tokenizes docs whose text actually changed since
# the last run, mirroring chitragupta/ledger.py's own stat-before-hash skip logic.
RETRIEVAL_INDEX_PATH = CONTENT_DIR / "retrieval_index.json"


def _get_field_weight(field: str) -> float:
    """One `[retrieval]` field weight, validated at load.

    Rejected rather than coerced, like _get_workers and
    _get_optional_float: a negative weight makes BM25's term-frequency
    saturation return a negative contribution, and an infinite one makes
    every document carrying the field tie at inf. Both surface far from
    the config line that caused them -- as a ranking nobody can explain
    rather than as an error -- which is the failure mode this project
    keeps choosing to move forward.
    """
    weight = _get_float(
        f"RETRIEVAL_WEIGHT_{field.upper()}", "retrieval", f"weight_{field}", default=1.0
    )
    if not 0.0 <= weight < math.inf:
        raise ValueError(
            f"[retrieval].weight_{field} must be a finite number at least 0, not {weight!r}. "
            "1.0 leaves ranking exactly as it is."
        )
    return weight


# Per-field BM25 weights, keyed by chitragupta/retrieval_scoring.py's
# FIELDS -- built from that tuple so a field cannot exist without a
# weight or a weight without a field. Every default is 1.0, which
# reproduces the pre-#762 ranking exactly; docs/RETRIEVAL.md carries the
# measurement that would justify any other number -- and the one that
# declined a third field, since issue #770 asked for `caption` and
# `table` here and neither survived it.
RETRIEVAL_FIELD_WEIGHTS = {field: _get_field_weight(field) for field in ("title", "abstract")}


def _get_bm25_constant(key: str, default: float, upper: float) -> float:
    """One `[retrieval]` Okapi BM25 constant, validated at load (#788).

    Rejected rather than coerced, like _get_field_weight above and for
    the same reason: neither constant fails anywhere near the config line
    that set it.

    - **`k1` below 0 inverts term-frequency saturation**, so a paper
      saying "digital twin" nine times scores *below* one saying it once.
      Not finite is worse: `inf` and `nan` both make every score `nan`,
      and a sort over `nan` is arbitrary rather than wrong in a
      direction anyone could notice.
    - **`b` outside [0, 1] is not a stronger length normalization, it is
      a broken one.** The normalizer is `1 - b + b * (dl / avgdl)`, which
      goes negative for a short document once `b` passes 1 -- flipping
      the sign of BM25's denominator, so a document containing the term
      ranks below one that does not.

    Hence two bounded ends here where the field weights have one. `upper`
    is `math.inf` for `k1`, whose upper end is genuinely open; the
    finiteness check is what that end still needs.
    """
    value = _get_float(f"RETRIEVAL_{key.upper()}", "retrieval", key, default=default)
    if not (math.isfinite(value) and 0.0 <= value <= upper):
        allowed = "at least 0" if upper == math.inf else f"between 0 and {upper:g}"
        raise ValueError(
            f"[retrieval].{key} must be a finite number {allowed}, not {value!r}. "
            f"{default} is what this project ships, and what #788's sweep examined."
        )
    return value


# Okapi BM25's two free parameters, for chitragupta/retrieval_scoring.py
# -- `k1` sets how fast term frequency saturates, `b` how strongly a
# document's length is normalized. Both apply to the passage unit
# (chitragupta/retrieval_passages.py) as well, which shares that scorer.
#
# The defaults are the textbook TREC values, and #788 is what turned them
# from *inherited* into *examined*: swept one parameter at a time on this
# project's own corpus. They did not move, and the reason is recorded
# rather than assumed. `b` has no better value -- 0.75 is the recall peak,
# and the one setting that beats it on nDCG loses two queries of recall.
# `k1` does: the sweep prefers 8.0 over 1.5, by seven queries. It was not
# adopted because only one of this repository's two BM25 ground truths
# could be built on the measuring host, and it is the one structurally
# unable to decide this -- its query is a paper's own author keywords and
# its answer is that paper, so weakening term-frequency saturation is
# favoured by construction. bench/RESULTS.md carries the table and
# docs/RETRIEVAL.md the reading of it.
#
# Configurable regardless, because the next corpus is not this one: a
# bibliography of four-page papers and one that is half books want
# different length normalization, which is exactly what `b` is for.
RETRIEVAL_K1 = _get_bm25_constant("k1", 1.5, math.inf)
RETRIEVAL_B = _get_bm25_constant("b", 0.75, 1.0)

# Whether a query's acronyms are expanded from the tier-1 acronym
# vocabulary before it is ranked (#789) -- `DT` also searching for the
# words "digital twin", so an abbreviation reaches the papers that spell
# the term out.
#
# **A switch, not a dial, and that is a measurement.** An earlier
# revision of this made it a weight, so an added term could score at a
# fraction of one the caller typed; the sweep behind docs/RETRIEVAL.md
# found full weight the best of 0.25/0.5/1.0 on every figure, which
# leaves a dial whose only supported setting is its maximum. A user who
# wants less than that wants a different vocabulary, not a smaller
# number.
#
# On by default. What it expands is `[style].acronyms` merged over the
# vendored floor, so on a host that has written no acronyms file it is
# five general-computing entries and changes nothing measurable; the
# benefit arrives with the user's own vocabulary, which is why
# `chitragupta init` scaffolds `content/acronyms.toml`.
ACRONYM_EXPANSION = _get_bool(
    "RETRIEVAL_ACRONYM_EXPANSION", "retrieval", "acronym_expansion", default=True
)
# The same, for chitragupta/retrieval_passages.py's passage-level index
# (#769). A separate file rather than a second key inside
# RETRIEVAL_INDEX_PATH above:
# the two are invalidated by different things -- the document index by
# the parsed .txt, this one by the passage sidecar beside it -- and a
# shared file would make either rebuild discard the other's work.
RETRIEVAL_PASSAGE_INDEX_PATH = CONTENT_DIR / "retrieval_passage_index.json"
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
# switching off the default. Folded to its spelling at load like the
# other enums, because sync.py, sync_pool.py and ledger_upsert.py compare
# it to "docling" by string: a written `Docling` used to load verbatim
# and compare unequal in each, rather than fail at load naming the
# alternatives as a typo in the other enums does (#847).
PARSER_BACKENDS = ("pdftotext", "docling")
PARSER = _get_choice("PARSER", "parser", "backend", default="pdftotext", choices=PARSER_BACKENDS)
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
# Whether the docling backend also runs its formula recognition model,
# so a paper's equations reach content/parsed/*.txt as decoded LaTeX
# rather than the literal marker `<!-- formula-not-decoded -->` (#651).
#
# The corpus layer's own toggle, deliberately separate from
# [enrich].docling_formulas (DOCLING_FORMULAS, in config_enrich.py) even though both
# set the same docling option: they configure two independent parses,
# and this one is meaningful to a user who never runs the enrichment
# layer at all. Reading the [enrich] key from here would cross the layer
# boundary docs/ARCHITECTURE.md draws.
#
# Off by default for the same economics as OCR above -- an extra model
# download and an extra pass per page. It matters more than that ratio
# suggests, though: retrieval.py indexes only content/parsed/*.txt, so
# with this off a formula is absent from the one artefact a drafting
# skill can read. Measured before #651: 148 of 497 documents carried the
# marker and none carried decoded LaTeX.
PARSER_FORMULAS = _get_bool("PARSER_FORMULAS", "parser", "formulas", default=False)


# How many documents sync parses at once. 1 keeps the historical, strictly
# serial behaviour -- no pool, no subprocesses -- so raising this is an
# opt-in. See config.toml.example's [parser].workers comment for how the
# requested value is clamped against what the host can actually sustain,
# and chitragupta/pdf_text.resolve_workers for the arithmetic.
PARSER_WORKERS = _get_workers("PARSER_WORKERS", "parser", "workers", default=1)


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
PARSER_START_METHOD = _get_choice(
    "PARSER_START_METHOD", "parser", "start_method", default="auto", choices=PARSER_START_METHODS
)

# Give up on a single document after this many seconds, or None for no
# limit. Applies to both backends, by the mechanism each one has:
# docling's own PdfPipelineOptions.document_timeout, and a subprocess
# timeout for pdftotext -- sync's, and the three on-demand runs outside it
# (passages, verbatim_check._corpus, enrich.embed_text; #824). Off by
# default -- any value has to clear the slowest legitimate document in
# the corpus, and this project's is a
# 675-page book that took 246s on its own, so a number that is safe here
# is not necessarily safe elsewhere.
PARSER_DOCUMENT_TIMEOUT = _get_optional_float(
    "PARSER_DOCUMENT_TIMEOUT", "parser", "document_timeout"
)

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
    "PARSER_STALL_TIMEOUT", "parser", "stall_timeout", default=1800.0
)

# Parse-quality guard (chitragupta/pdf_text.quality_warning): a PDF extractor
# that sets its glyph-spacing tolerance too coarse fuses adjacent words
# together, which chitragupta/retrieval.py's whitespace tokenizer then cannot
# match against. Measured over the same 10 PDFs, pdftotext produced
# 0.01% such tokens and a since-removed backend produced 4.19% -- three
# orders of magnitude apart -- so 1% sits well clear of both.
PARSE_LONG_WORD_CHARS = _get_int("PARSE_LONG_WORD_CHARS", "parser", "long_word_chars", default=20)
PARSE_LONG_WORD_RATIO = _get_float(
    "PARSE_LONG_WORD_RATIO", "parser", "long_word_ratio", default=0.01
)
# Below this many words the ratio is too noisy to mean anything (a
# cover page, or a scan that yielded almost no text).
PARSE_MIN_TOKENS = _get_int("PARSE_MIN_TOKENS", "parser", "min_tokens", default=200)


# How much the pipeline writes to logs/pipeline.log (see LOGS_DIR
# below) -- one of the standard library's own level names. Deliberately
# the only [logging] setting: rotation size/backup count are fixed in
# logging_setup.py rather than exposed here, since nothing so far has
# needed them to vary per host.
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
LOGGING_LEVEL = _get_choice("LOGGING_LEVEL", "logging", "level", default="INFO", choices=LOG_LEVELS)
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
PROVENANCE_WEAK_SCORE = _get_float(
    "PROVENANCE_WEAK_SCORE", "provenance", "weak_score", default=0.20
)
PROVENANCE_GOOD_SCORE = _get_float(
    "PROVENANCE_GOOD_SCORE", "provenance", "good_score", default=0.50
)

# Heavier optional pipeline (pyproject.toml's "enrich" Poetry group), per chitragupta/enrich/.
DOCLING_DIR = CONTENT_DIR / "docling"
# Per-doc (size, mtime_ns) PDF fingerprint, so docling_parse.parse_doc()
# only re-runs Docling's layout/OCR models -- the slowest stage in this
# pipeline -- for a PDF that's new or has actually changed since the last
# call, mirroring chitragupta/ledger.py's own stat-before-hash skip logic.
DOCLING_CACHE_PATH = CONTENT_DIR / "docling_cache.json"
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
# The extract-keywords stage's output: phrases the corpus's own papers
# declared on their Keywords:/Index Terms lines, in the same
# `topics = [...]` shape as SEED_TOPICS_PATH so seed_topics.load() reads
# either. A *generated* artifact, regenerated fresh on every run --
# unlike seed_topics.toml it is never hand-edited, and a phrase worth
# keeping permanently is promoted into seed_topics.toml instead.
# Resolved under CONTENT_DIR unless given absolute, the same rule
# CONTENT_DIR itself follows for PROJECT_ROOT.
KEYWORDS_PATH = CONTENT_DIR / _get(
    "KEYWORDS_PATH", "enrich", "keywords_path", default="keywords.toml"
)
# The join of the two topic answers: the phrases the author wrote, and
# the topics the corpus turned out to have. Written by the `converge`
# stage from artefacts the earlier stages already produced, so it re-runs
# no clustering and no matching of its own.
TOPIC_SET_PATH = CONTENT_DIR / "topic_set.json"
# The topic graph: relations between the topics topic_set.json already
# holds. Written by the `topic-graph` stage; read by `corpus discover`.
TOPIC_GRAPH_PATH = CONTENT_DIR / "topic_graph.json"
RENDERED_DIR = CONTENT_DIR / "rendered"

# The CSL style pandoc's --citeproc formats citations and the bibliography
# with. Vendored (assets/csl/) rather than fetched, so rendering works with
# no network and so a style change can never silently renumber a draft that
# was already reviewed -- see assets/csl/README.md.
_CSL_STYLE = _get("CSL_STYLE", "render", "csl", default="")
CSL_STYLE_PATH = (PROJECT_ROOT / _CSL_STYLE) if _CSL_STYLE else shipped("assets", "csl", "ieee.csl")

# The Vale configuration `python -m chitragupta.draft style` checks a draft
# against, vendored at assets/vale/ for the reason assets/csl/ieee.csl is:
# a style fetched at run time is not the style that was reviewed, and a
# check whose rules differ per clone is not a check. Overridable so a user
# can point at their own house style without editing what ships.
_VALE_CONFIG = _get("VALE_CONFIG", "style", "vale_config", default="")
VALE_CONFIG_PATH = (
    (PROJECT_ROOT / _VALE_CONFIG) if _VALE_CONFIG else shipped("assets", "vale", "vale.ini")
)

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


# ---------------------------------------------------------------------
# [retrieval] -- the tier-1 BM25 path's own settings. Deliberately its
# own section rather than more [enrich] keys: everything below runs under
# bare `python` with no venv and no model, which is the distinction that
# decides whether a setting can be honoured at all on a given host.
# ---------------------------------------------------------------------

# The most passages retrieval_passages.search() will return from a single
# citekey (#769). The document-level retrieval.search() needs no such
# key: it is one-result-per-citekey by construction, so a cap there would
# be a no-op. Same default and same reasoning as
# EMBED_MAX_PASSAGES_PER_SOURCE (config_enrich.py), and deliberately the same shape --
# the two paths cap for one reason and should read as one idea.
MAX_PASSAGES_PER_SOURCE = _get_positive_int(
    "MAX_PASSAGES_PER_SOURCE",
    "retrieval",
    "max_passages_per_source",
    default=3,
)

# There is deliberately no `passage_overfetch_multiplier` beside the cap,
# and the omission is the interesting half. EMBED_OVERFETCH_MULTIPLIER
# exists because Chroma hands back a *pre-truncated* candidate list, so a
# cap applied to it can only shorten the result rather than promote
# another paper's chunk into the window -- the failure #305 existed to
# fix. Nothing truncates here: `_bm25_scores` scores every indexed
# passage in memory, so the cap walks the fully ranked list and takes the
# first k that fit, which is what an infinite over-fetch would buy. A
# multiplier would be a knob whose every setting gave the same answer.
#
# Passages shorter than this many tokens (after retrieval's own
# tokenizer, so stopwords and single-character words are already gone --
# two-character ones rank since #790) are
# not indexed. BM25's length normalization *rewards* a short dense
# match, which is harmless at document scale and not at passage scale: a
# three-word heading or a one-line bibliography entry whose words are the
# query outscores every real paragraph in the corpus. A floor is the
# cheap half of the answer; excluding section_header/title passages
# outright is the other half, and that one is structural rather than
# configurable. Default measured in bench/bench_retrieval_passage.py --
# and measured *before* #790 lowered the tokenizer's length floor to 2,
# which grew every passage's token count by about 7%. The number did not
# move; what it counts did, so this floor now admits passages the sweep
# behind it excluded. Re-sweeping it is a separate measurement, and the
# constant is a defensible default rather than a re-derived one until
# someone runs it.
MIN_PASSAGE_TOKENS = _get_positive_int(
    "MIN_PASSAGE_TOKENS",
    "retrieval",
    "min_passage_tokens",
    default=20,
)


# --------------------------------------------------------------------------
# [enrich] and [discover]
# --------------------------------------------------------------------------
#
# The enrichment and discovery knobs live in chitragupta/config_enrich.py
# (#848) and are re-exported here, so each is still read as `config.NAME`.
# The paths those stages write stay above, beside every other path under
# CONTENT_DIR, because they are derived from it.
#
# Reloaded when this module is: `importlib.reload(config)` re-runs this
# body, but a plain import of a module already in `sys.modules` would hand
# back the values it computed the first time, from whatever config.toml
# and environment were current then.
if "chitragupta.config_enrich" in sys.modules:
    importlib.reload(sys.modules["chitragupta.config_enrich"])

# pylint: disable=unused-import,wrong-import-position
from chitragupta.config_enrich import (  # noqa: F401,E402
    DOCLING_IMAGES,
    DOCLING_IMAGE_SCALE,
    DOCLING_FORMULAS,
    SEED_TOPIC_MIN_SIMILARITY,
    SEED_TOPIC_MAX_PAPERS,
    KEYWORD_TOP_N,
    KEYWORD_MIN_DF,
    TOPIC_EXCLUDE_AUTHOR_NAMES,
    TOPIC_MIN_CLUSTER_SIZE,
    TOPIC_MIN_SAMPLES,
    TOPIC_NEIGHBORS,
    TOPIC_DISTRIBUTION,
    TOPIC_MEMBERSHIP_RATIO,
    TOPIC_MEMBERSHIP_MAX,
    TOPIC_CONVERGE_SIMILARITY,
    TOPIC_GRAPH_P_VALUE,
    TOPIC_GRAPH_NEIGHBORS,
    DISCOVER_MIN_SIMILARITY,
    EMBEDDING_MODEL,
    EMBED_TOP_K,
    EMBED_MAX_PASSAGES_PER_SOURCE,
    EMBED_OVERFETCH_MULTIPLIER,
    RERANK,
    RERANK_MODEL,
    ENTAILMENT_MODEL,
    SUPPORT_PREMISE_TOPK,
)

# pylint: enable=unused-import,wrong-import-position


# --------------------------------------------------------------------------
# Path containment
# --------------------------------------------------------------------------
#
# Split into chitragupta/config_path.py (#441): "is this path inside the
# content directory" no longer needs to live in this file's own body to
# stay reachable as config.OutsideContentDir/resolves_inside/mirrored_dir/
# require_inside_content -- every one of this project's existing call
# sites keeps working through the re-export below. config_path.py reads
# CONTENT_DIR back off this module (a live `config.CONTENT_DIR` attribute
# lookup, not a bare name snapshotted at its own import time), which is
# what keeps `tests/conftest.py`'s `isolated_config` fixture -- which
# patches `config.CONTENT_DIR` directly -- visible to it.

# pylint: disable=unused-import,wrong-import-position
from chitragupta.config_path import (  # noqa: F401,E402
    OutsideContentDir,
    confined_path,
    mirrored_dir,
    require_inside_content,
    resolves_inside,
)

# pylint: enable=unused-import,wrong-import-position
