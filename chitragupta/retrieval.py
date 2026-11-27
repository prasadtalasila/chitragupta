"""BM25-ranked keyword retrieval over the shared corpus layer.

The default retrieval genre skills call (AGENTS.md's "Retrieval"),
stdlib-only. `enrich/embed_index.py` is a drop-in *replacement* with the
same `search(query, k)` shape, never fused with this (docs/RETRIEVAL.md).

Reads `content/parsed/*.txt` (and this layer's sidecar, only for
`_reference_cut`), never `content/docling/`, so the enrichment layer
never changes what BM25 ranks, and it never imports this module.
`parsed_path` is read only when `status` is `'parsed'` (#490).

Okapi BM25 rather than raw term frequency, which has no length
normalization. Per-document term stats are cached on disk
(config.RETRIEVAL_INDEX_PATH) by a parsed-file stat fingerprint, so only
changed documents are re-tokenized; top-k snippets read text fresh.
"""

# Within a run, `retrieval_cache._load_cache` memoizes the parsed index
# per process (#511/m-74): `deep-research` subagents call `search()` many
# times, and re-parsing 14 MB per call was the largest fixed cost.

import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from typing import Any

from chitragupta.ledger_citable import PARSED
from chitragupta import (
    _reference_cut,
    _tokens,
    collection_filter,
    ledger,
    ledger_paths,
    retrieval_cache,
    retrieval_added,
    retrieval_scoring,
    retrieval_tables,
)

# Dropped from queries, never from the index: `_tokens.INTERROGATIVES`.
_INTERROGATIVES = _tokens.INTERROGATIVES


@dataclass
class SearchResult:
    citekey: str
    title: str
    score: float
    snippet: str


# The `INDEX` setting: `chitragupta/_tokens.py` has the floor's measurement
# (#790) and why editing it needs no version bump (issue 845).
def _tokenize(text: str) -> list[str]:
    return _tokens.words(text, _tokens.INDEX)


def short_query_terms(query: str) -> list[str]:
    """Single-character words in `query` dropped *only* by the length floor.

    Stopwords are excluded, as naming them explains nothing; what is left
    lets the CLI explain an empty result. One character since #790 ("AI"
    now ranks); both read `_tokens.INDEX`, so they cannot drift (issue 845).
    """
    rule = _tokens.INDEX
    return [
        w
        for w in _tokens.WORD.findall(query.lower())
        if len(w) < rule.floor and w not in rule.stopwords
    ]


def _query_terms(query: str) -> list[str]:
    """`_tokenize(query)` with interrogatives also dropped -- query-side
    only, so a document's own term frequencies and every IDF stay put."""
    return [w for w in _tokenize(query) if w not in _INTERROGATIVES]


# What a query is ranked on: the typed terms, then what acronym expansion
# (#789) and spelling correction (#1232) added, with the `Added` entries
# (retrieval_added.py). Everything that ranks, windows or notes a query
# goes through here, since #953 found separate pipelines disagreeing.
# `context` (`--y-prev`'s prose) is expanded but never spelling-corrected:
# draft prose is full of LaTeX and words a corpus lacks (bench/RESULTS.md).
# Added terms are never expanded or corrected in turn, and score at full
# weight (#789's sweep).
def query_terms(query: str, context: str = "") -> tuple[list[str], list[retrieval_added.Added]]:
    typed, extra = _query_terms(query), _query_terms(context)
    added = retrieval_added.added_terms(typed, extra, _tokenize, _tokenize_item, _INTERROGATIVES)
    return typed + extra + [entry.term for entry in added], added


# Per-term anchor ceiling for `_windows`: bounds work on a pathological
# document; quality comes from scoring, not from more candidates.
_MAX_ANCHORS_PER_TERM = 500

# Numeric markers only ([12], [3, 7], [12-14]), so [Figure 2] survives.
# 22.8% of snippets carry one. The idea is OpenScholar's remove_citations,
# not its regex, which deletes every ']'.
_CITATION_MARKER = re.compile(r"\[\d+(?:\s*[,-]\s*\d+)*\]")


def _clean_window(text: str) -> str:
    """Whitespace-normalized `text` with a numeric citation marker
    stripped."""
    return " ".join(_CITATION_MARKER.sub("", text).split())


def _windows(text: str, terms: set[str], width: int, count: int) -> list[str]:
    """The `count` best-matching windows of `text`, in document order.

    Scored by distinct query terms inside, not raw hits, and anchored on
    every occurrence so late passages are reachable. Deterministic despite
    per-process string hashing: anchors are sorted and ties break on
    position.
    """
    lower = text.lower()
    # Matched as a word, not a substring (#790 made "ai" match inside
    # "said": 37 of 134 two-character hits were substring-only). Lookarounds
    # over `[a-z0-9]`, deliberately not `\b`, which disagrees with
    # `_tokenize` on underscores and accents and gave ranked documents no
    # window. So "co" matches "co-simulation" but not "control", exactly
    # as the index counted it.
    patterns = {term: re.compile(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])") for term in terms}
    anchors: list[int] = []
    for pattern in patterns.values():
        # Bounded per term, so one frequent term cannot crowd out another's
        # anchors; a shared budget would pick its victim by set order.
        for found, match in enumerate(pattern.finditer(lower)):
            if found == _MAX_ANCHORS_PER_TERM:
                break
            anchors.append(match.start())
    if not anchors:
        return []

    scored: list[tuple[int, int, int]] = []
    half = width // 2
    for anchor in sorted(set(anchors)):
        begin = max(0, anchor - half)
        end = min(len(text), begin + width)
        window = lower[begin:end]
        hits = sum(1 for pattern in patterns.values() if pattern.search(window))
        scored.append((hits, begin, end))

    chosen: list[tuple[int, int]] = []
    for _, begin, end in sorted(scored, key=lambda item: (-item[0], item[1])):
        if any(begin < other_end and end > other_begin for other_begin, other_end in chosen):
            continue
        chosen.append((begin, end))
        if len(chosen) == count:
            break
    return retrieval_tables.render_windows(text, chosen, _clean_window)


def _snippet(text: str, terms: set[str], window: int = 500) -> str:
    """The single best `window` characters of `text` for `terms`, via
    `_windows` as `evidence` uses, so the same query gives the same snippet
    every run (docs/REJECTION.md says why that matters).
    """
    best = _windows(text, terms, width=window, count=1)
    if best:
        return best[0]
    return _clean_window(text[:window])


def _full_text(item: sqlite3.Row) -> str:
    text_parts = [item["title"] or ""]
    # A non-'parsed' status means parsed_path may name a superseded
    # version's text (#490). `parsed_file` is the other half (issue 821):
    # a ledger row is data, and one repointed at `~/.ssh/id_rsa` had its
    # bytes indexed. Relative to `config.PARSED_DIR` (#966).
    if item["status"] == "parsed" and (parsed := ledger_paths.parsed_file(item["parsed_path"])):
        try:
            raw = parsed.read_text(encoding="utf-8", errors="replace")
        except OSError:
            # Counted, not reported here: `retrieval_cli` prints it as a
            # note (issue 844).
            pass
        else:
            # `errors="replace"`, as `sync` and `passages` decode (issue
            # 844), so a stray byte cannot fuse words. The bibliography is
            # cut here (#768, `_reference_cut.py`) so snippets, evidence
            # windows and ranked tokens all come from the same text.
            text_parts.append(_reference_cut.strip_references(raw, str(parsed)))
    return "\n".join(text_parts)


def _tokenize_item(item: sqlite3.Row) -> dict:
    # `field_freqs` feeds #762's weights; older entries still score, but
    # `_INDEX_SCHEMA_VERSION` was bumped so none lacks the counts.
    tokens = _tokenize(_full_text(item))
    fields = retrieval_scoring.field_freqs(item, _tokenize)
    return {"length": len(tokens), "term_freqs": dict(Counter(tokens)), "field_freqs": fields}


def _bm25_scores(index: dict, terms: list[str]) -> dict[str, float]:
    """Delegates to `retrieval_scoring.bm25_scores` (#762) rather than
    aliasing it: `dossier/_drift.py` and `discover/_resolve.py` use this
    name, and an alias would not see a test patching the new module."""
    return retrieval_scoring.bm25_scores(index, terms)


def search(
    query: str,
    k: int = 5,
    snippet_chars: int = 500,
    collection: str | None = None,
    context: str = "",
) -> list[SearchResult]:
    """Rank ledger items by BM25 relevance to `query`. Returns top-k.

    `context` is ranked beside `query` without being typed (see
    `query_terms`). `collection` (a slug or display path, resolved by
    `collection_filter.py`, #195) filters the ranking, not the index,
    since narrowing the index would change every IDF and split the cache.
    `snippet_chars` gives a caller enough context to judge relevance
    itself. One result per citekey by construction (`scores` is keyed by
    citekey, #305; tests/test_retrieval.py); sub-document rankers need a cap.
    """
    terms, _added = query_terms(query, context)
    if not terms:
        return []

    # Only parsed rows are ranked: an unparsed row is not citable (#1118)
    # and takes no part in any IDF. `search` is the cache's one writer.
    with ledger.reading() as con:
        items = [item for item in ledger.all_items(con) if item["status"] == PARSED]
        members = collection_filter.members(con, items, collection)

    index = retrieval_cache._load_index(items, _tokenize_item)
    scores = _bm25_scores(index, terms)
    by_citekey = {item["citekey"]: item for item in items}
    if members is not None:
        scores = {citekey: score for citekey, score in scores.items() if citekey in members}
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:k]

    term_set = set(terms)
    results = []
    for citekey, score in ranked:
        item = by_citekey[citekey]
        results.append(
            SearchResult(
                citekey=citekey,
                title=item["title"],
                score=score,
                snippet=_snippet(_full_text(item), term_set, window=snippet_chars),
            )
        )
    return results


# `evidence` and the CLI live in retrieval_cli.py (#441), which imports
# `_windows`, `_full_text` and `search` from here. `main` is re-exported
# via PEP 562 `__getattr__`, not a bottom-of-file import: under
# `python -m chitragupta.retrieval` this file runs as `__main__`, and a
# plain import would re-import it mid-load and fail with "cannot import
# name 'main' from partially initialized module". Deferred, a bare `-m`
# run stays a silent no-op. (A package `__init__.py` never hits this.)
def __getattr__(name: str) -> Any:
    if name == "main":
        from chitragupta.retrieval_cli import main

        return main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
