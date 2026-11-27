"""Central configuration for the research pipeline.

Defaults live in config.toml; any value can be overridden with an
environment variable of the same name (BIB_FILE=/other.bib ...).
"""

# Every setting is read as `config.NAME`, including those re-exported from
# config_load, config_enrich and config_path: the tier-1 stdlib-only
# commands import `config` alone (docs/ARCHITECTURE.md). The getters are
# config_load's own function objects, so tests patching
# `config_load._toml` reach them.

import importlib
import math
import os
import sys
from pathlib import Path

from chitragupta import config_load

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

# Two roots, the same directory in a git checkout and different once
# installed (docs/PACKAGING.md): PACKAGE_ROOT follows the code,
# PROJECT_ROOT follows the user's corpus, drafts and config.
PACKAGE_ROOT = Path(__file__).resolve().parent

# The project marker is the file this module already requires, so a user
# has nothing new to create.
PROJECT_MARKER = "config.toml"


def shipped(*parts: str) -> Path:
    """A file that ships with the code (CSL style, Vale rules, acronyms,
    Lua filters), resolved from the package, not the working directory.

    One seam, for when `assets/` moves under the package (#261).
    """
    return PACKAGE_ROOT.parent.joinpath(*parts)


def discover_project_root(
    cwd: "Path | None" = None, environ: "dict | None" = None
) -> "Path | None":
    """The project directory, or None when there is no project here.

    Order, first hit wins:

    1. `CHITRAGUPTA_PROJECT`, so an explicit answer always beats a
       discovered one. A relative value resolves against `cwd`.
    2. The nearest ancestor of the working directory holding a
       `config.toml` -- how an installed `chitragupta` finds the project
       the user is standing in.
    3. The directory above the package, when *it* holds one. This is the
       git checkout, and it is what keeps every existing invocation
       working from anywhere, exactly as deriving the root from
       `__file__` used to.

    Not `CONFIG_PATH`: naming a config file must not move the whole data
    root (`tests/test_config.py::test_custom_config_path`).
    """
    environ = os.environ if environ is None else environ
    explicit = environ.get("CHITRAGUPTA_PROJECT")
    if explicit:
        # Resolved (#966), or every derived path depends on a later cwd.
        return ((Path.cwd() if cwd is None else Path(cwd)) / explicit).resolve()
    start = (Path.cwd() if cwd is None else Path(cwd)).resolve()
    for candidate in (start, *start.parents):
        if (candidate / PROJECT_MARKER).is_file():
            return candidate
    beside_package = PACKAGE_ROOT.parent
    if (beside_package / PROJECT_MARKER).is_file():
        return beside_package
    return None


# The fallback makes the missing-config error name a recognisable path.
PROJECT_ROOT = discover_project_root() or PACKAGE_ROOT.parent
CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", str(PROJECT_ROOT / PROJECT_MARKER)))
# Here, not at config_load's import, so `importlib.reload(config)` re-reads.
config_load.load(CONFIG_PATH)

# An absolute override survives the join (pathlib), so env vars may be either.
BIB_FILE_PATH = PROJECT_ROOT / _get("BIB_FILE", "bib", "path", default="papers/bibliography.bib")

# Ignored since 7.0.0 (collections come from `cg-collections`); kept so
# sync can say so once.
LEGACY_COLLECTIONS_FIELD = bool(_get("BIB_COLLECTIONS_FIELD", "bib", "collections_field"))

CONTENT_DIR = PROJECT_ROOT / _get("CONTENT_DIR", "content", "dir", default="content")
PARSED_DIR = CONTENT_DIR / "parsed"
LEDGER_PATH = CONTENT_DIR / "ledger.sqlite"
# Review-layer reports, one directory per draft mirroring its path under
# DRAFTS_DIR. The skills' section-to-citekey JSON is drafting state and
# lives in the dossier instead.
REVIEW_DIR = CONTENT_DIR / "review"
# Drafts, and the dossier state that produced each (docs/DRAFT-ITERATION.md).
DRAFTS_DIR = CONTENT_DIR / "drafts"
DOSSIERS_DIR = CONTENT_DIR / "dossiers"
# A book's outline and sign-offs (docs/WRITE-A-BOOK.md). A book is a
# directory of drafts, so its own path is mirrored, not its parent's.
SPECS_DIR = CONTENT_DIR / "specs"
# Per-citekey TL;DR sidecars: per citekey, not per draft, so not mirrored.
TLDR_DIR = CONTENT_DIR / "tldr"
# BM25 index cache, keyed by a stat fingerprint so only changed docs re-tokenize.
RETRIEVAL_INDEX_PATH = CONTENT_DIR / "retrieval_index.json"


def _get_field_weight(field: str) -> float:
    """One `[retrieval]` field weight, validated at load.

    Rejected rather than coerced: a negative or infinite weight produces a
    ranking nobody can explain, far from the config line that caused it.
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


# Built from the field tuple so a field cannot lack a weight. Every
# default 1.0 reproduces the pre-#762 ranking; docs/RETRIEVAL.md has the
# measurement, including why `caption` and `table` were declined (#770).
RETRIEVAL_FIELD_WEIGHTS = {field: _get_field_weight(field) for field in ("title", "abstract")}


def _get_bm25_constant(key: str, default: float, upper: float) -> float:
    """One `[retrieval]` Okapi BM25 constant, validated at load (#788).

    Rejected rather than coerced, like _get_field_weight. `k1` below 0
    inverts saturation, and a non-finite value makes every score `nan`.
    `b` outside [0, 1] can flip the sign of the denominator for a short
    document, so a document without the term outranks one with it.
    """
    value = _get_float(f"RETRIEVAL_{key.upper()}", "retrieval", key, default=default)
    if not (math.isfinite(value) and 0.0 <= value <= upper):
        allowed = "at least 0" if upper == math.inf else f"between 0 and {upper:g}"
        raise ValueError(
            f"[retrieval].{key} must be a finite number {allowed}, not {value!r}. "
            f"{default} is what this project ships, and what #788's sweep examined."
        )
    return value


# Okapi BM25's `k1` (term-frequency saturation) and `b` (length
# normalization), shared with the passage scorer. The TREC defaults
# survived #788's sweep: `b` has no better value, and `k1` = 8.0 won only
# on the ground truth that favours it by construction (docs/RETRIEVAL.md).
# Configurable because another corpus may want different normalization.
RETRIEVAL_K1 = _get_bm25_constant("k1", 1.5, math.inf)
RETRIEVAL_B = _get_bm25_constant("b", 0.75, 1.0)

# Expand a query's acronyms (`DT` -> "digital twin") before ranking (#789).
# A switch, not a weight: full weight won every figure in the sweep. It
# expands `[style].acronyms` over the vendored floor, so the benefit comes
# with the user's own vocabulary.
ACRONYM_EXPANSION = _get_bool(
    "RETRIEVAL_ACRONYM_EXPANSION", "retrieval", "acronym_expansion", default=True
)
# Also search the corpus word one typo away from an unseen query word
# (#1232). Off: it moves existing drafts' rankings, and 964 logged agent
# queries held no genuine typo.
SPELLING_CORRECTION = _get_bool(
    "RETRIEVAL_SPELLING_CORRECTION", "retrieval", "spelling_correction", default=False
)
# The passage-level index (#769). A separate file because it is
# invalidated by the passage sidecar, not the parsed .txt.
RETRIEVAL_PASSAGE_INDEX_PATH = CONTENT_DIR / "retrieval_passage_index.json"
# N-gram fingerprints for overlap_index: one file per citekey plus a
# merged index.bin, stat-keyed like RETRIEVAL_INDEX_PATH.
OVERLAP_DIR = CONTENT_DIR / "overlap"
# Per-host, hand-edited, gitignored phrases the verbatim scan must not flag
# (docs/PLAGIARISM.md). Absent means no suppressions.
VERBATIM_ALLOWLIST_PATH = CONTENT_DIR / "verbatim_allowlist.toml"
# Project-wide terms no prose rule reports and the verbatim scan masks
# (#1187). Versioned with the project, unlike the allowlist.
STYLE_EXCEPTIONS_PATH = CONTENT_DIR / "style_exceptions.toml"
# Mutex for writes to content/ (runlock). Its own file, so locking does not
# force the ledger's commit points into one transaction.
PIPELINE_LOCK_PATH = CONTENT_DIR / "pipeline.lock.db"

# Folded to its spelling at load (#847): callers compare to "docling" by
# string, so `Docling` must fail at load, not compare unequal.
PARSER_BACKENDS = ("pdftotext", "docling")
PARSER = _get_choice("PARSER", "parser", "backend", default="pdftotext", choices=PARSER_BACKENDS)
# Docling OCR, off: it costs 2-5x (more at high worker counts) and mostly
# recovers publisher furniture and captions, though on one sampled document
# two whole tables. See config.toml's [parser].ocr before changing it.
PARSER_OCR = _get_bool("PARSER_OCR", "parser", "ocr", default=False)
# Docling formula recognition for the corpus parse (#651), separate from
# [enrich].docling_formulas because the two parses are independent layers.
# Off for cost, but with it off a formula is absent from the only text
# retrieval indexes: 148 of 497 documents carried the undecoded marker.
PARSER_FORMULAS = _get_bool("PARSER_FORMULAS", "parser", "formulas", default=False)


# Documents parsed at once; 1 is serial, no pool. Clamped by
# pdf_text.resolve_workers.
PARSER_WORKERS = _get_workers("PARSER_WORKERS", "parser", "workers", default=1)


# Pool start method, used only for docling with workers > 1. forkserver
# shares one torch+docling import (9.6s vs spawn's 11.3s to first
# document). Plain "fork" is refused: see pdf_text.start_method.
PARSER_START_METHODS = ("auto", "forkserver", "spawn")
PARSER_START_METHOD = _get_choice(
    "PARSER_START_METHOD", "parser", "start_method", default="auto", choices=PARSER_START_METHODS
)

# Per-document timeout, or None. Off: a safe value must clear the slowest
# legitimate document (here a 675-page book at 246s).
PARSER_DOCUMENT_TIMEOUT = _get_optional_float(
    "PARSER_DOCUMENT_TIMEOUT", "parser", "document_timeout"
)

# Give up when *no* document completes for this long: silence separates a
# hung worker from a slow document. On, because users hit wedged runs;
# loose (7x the slowest document), and affected documents are retried.
PARSER_STALL_TIMEOUT = _get_optional_float(
    "PARSER_STALL_TIMEOUT", "parser", "stall_timeout", default=1800.0
)

# Parse-quality guard: too many fused long words means the extractor
# merged words. pdftotext gives 0.01% and a removed backend gave 4.19%,
# so 1% sits clear of both.
PARSE_LONG_WORD_CHARS = _get_int("PARSE_LONG_WORD_CHARS", "parser", "long_word_chars", default=20)
PARSE_LONG_WORD_RATIO = _get_float(
    "PARSE_LONG_WORD_RATIO", "parser", "long_word_ratio", default=0.01
)
# Below this the ratio is noise.
PARSE_MIN_TOKENS = _get_int("PARSE_MIN_TOKENS", "parser", "min_tokens", default=200)


# The only [logging] setting: rotation is fixed in logging_setup, as nothing
# has needed it to vary per host.
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
LOGGING_LEVEL = _get_choice("LOGGING_LEVEL", "logging", "level", default="INFO", choices=LOG_LEVELS)
# No config.toml key; an env var only, so a subprocess test can redirect it.
LOGS_DIR = Path(os.environ.get("LOGS_DIR", str(PROJECT_ROOT / "logs")))

# citation_provenance bands: the fraction of a citing sentence's words
# found in the best passage. Round numbers: they order reading and are
# not a verdict. Below WEAK means "go look", never "wrong".
PROVENANCE_WEAK_SCORE = _get_float(
    "PROVENANCE_WEAK_SCORE", "provenance", "weak_score", default=0.20
)
PROVENANCE_GOOD_SCORE = _get_float(
    "PROVENANCE_GOOD_SCORE", "provenance", "good_score", default=0.50
)

# Heavier optional pipeline (pyproject.toml's "enrich" extra), per chitragupta/enrich/.
DOCLING_DIR = CONTENT_DIR / "docling"
# PDF stat fingerprint, so Docling's slow models re-run only on change.
DOCLING_CACHE_PATH = CONTENT_DIR / "docling_cache.json"
CHROMA_DIR = CONTENT_DIR / "chroma"

TOPICS_PATH = CONTENT_DIR / "topics.json"
# Whole-text embeddings keyed by content hash.
TOPIC_EMBED_CACHE_PATH = CONTENT_DIR / "topic_embed_cache.json"

# The author's topic phrases (TOML, hand-written) and their matches (JSON,
# generated). Neither need exist (seed_topics).
SEED_TOPICS_PATH = CONTENT_DIR / "seed_topics.toml"
TOPIC_SEEDS_PATH = CONTENT_DIR / "topic_seeds.json"
# extract-keywords output, in seed_topics.toml's shape. Regenerated each
# run, never hand-edited: promote a keeper into seed_topics.toml.
KEYWORDS_PATH = CONTENT_DIR / _get(
    "KEYWORDS_PATH", "enrich", "keywords_path", default="keywords.toml"
)
# The join of seeded and emergent topics, written by `converge`.
TOPIC_SET_PATH = CONTENT_DIR / "topic_set.json"
# Relations between topic_set.json's topics; read by `corpus discover`.
TOPIC_GRAPH_PATH = CONTENT_DIR / "topic_graph.json"
RENDERED_DIR = CONTENT_DIR / "rendered"

# Vendored so rendering needs no network and cannot silently renumber a
# reviewed draft (assets/csl/README.md).
_CSL_STYLE = _get("CSL_STYLE", "render", "csl", default="")
CSL_STYLE_PATH = (PROJECT_ROOT / _CSL_STYLE) if _CSL_STYLE else shipped("assets", "csl", "ieee.csl")

# Vendored for the same reason: a check whose rules differ per clone is
# not a check. Overridable for a house style.
_VALE_CONFIG = _get("VALE_CONFIG", "style", "vale_config", default="")
VALE_CONFIG_PATH = (
    (PROJECT_ROOT / _VALE_CONFIG) if _VALE_CONFIG else shipped("assets", "vale", "vale.ini")
)

# Fallback dialect when the dossier records none (docs/HOUSE-STYLE.md).
# Never an override: scope.md wins, and `draft style` names the source.
STYLE_LANGUAGE = _get("STYLE_LANGUAGE", "style", "language", default="")
# Collapse [3], [4], [5] to [3]-[6]: IEEE shows it, upstream ieee.csl
# does not, so render_output patches a temp copy.
RENDER_COLLAPSE_CITATIONS = _get_bool(
    "RENDER_COLLAPSE_CITATIONS", "render", "collapse_citations", default=True
)

# The author's acronym vocabulary, carried between drafts. Always merged
# over the vendored floor, never a replacement (assets/style/README.md).
ACRONYMS_DEFAULT_PATH = shipped("assets", "style", "acronyms.toml")
_ACRONYMS = _get("ACRONYMS", "style", "acronyms", default="")
ACRONYMS_PATH = (PROJECT_ROOT / _ACRONYMS) if _ACRONYMS else ACRONYMS_DEFAULT_PATH


# [retrieval]: tier-1 BM25 settings, runnable with bare `python`.

# Per-citekey passage cap (#769), matching EMBED_MAX_PASSAGES_PER_SOURCE.
MAX_PASSAGES_PER_SOURCE = _get_positive_int(
    "MAX_PASSAGES_PER_SOURCE",
    "retrieval",
    "max_passages_per_source",
    default=3,
)

# No over-fetch multiplier here, unlike Chroma's: BM25 ranks every
# passage, so the cap already walks the full list.
#
# Passages below this many tokens are not indexed: BM25 rewards a short
# dense match, so a heading or bibliography line would outrank real
# paragraphs. Measured in bench/bench_retrieval_passage.py, before #790
# grew token counts ~7%; not re-swept since.
MIN_PASSAGE_TOKENS = _get_positive_int(
    "MIN_PASSAGE_TOKENS",
    "retrieval",
    "min_passage_tokens",
    default=20,
)


# [enrich] and [discover] live in config_enrich (#848). Reloaded with this
# module, or a re-import would return values from the first load.
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


# Path containment (config_path). It reads `config.CONTENT_DIR` live, so
# the `isolated_config` fixture's patch reaches it.

# pylint: disable=unused-import,wrong-import-position
from chitragupta.config_path import (  # noqa: F401,E402
    OutsideContentDir,
    confined_path,
    mirrored_dir,
    require_inside_content,
    resolves_inside,
)

# pylint: enable=unused-import,wrong-import-position
