"""The one rule for reading words off text, and its two named settings.

Issue 845: BM25 and claim matching each had their own regex, floor and
stopwords, and cache versions relied on a comment asking for hand bumps;
a missed bump silently ranked cached and fresh entries on different
vocabularies. `vocabulary_digest` now versions both caches. Stdlib-only.

The verbatim tier keeps every word and versions its own caches, so it
deliberately does not borrow `WORD`; `tests/test_tokens.py` pins that it
splits where these do.
"""

import hashlib
import re
from typing import NamedTuple

# Lowercase alphanumeric runs, applied to already-lowercased text: on raw
# text it splits "Configuration" into "onfiguration".
WORD = re.compile(r"[a-z0-9]+")


class Rule(NamedTuple):
    """Which of `WORD`'s matches count as words: the shortest length kept,
    and the words dropped whatever their length."""

    floor: int
    stopwords: frozenset[str]


CORE_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "of",
        "on",
        "in",
        "for",
        "and",
        "to",
        "with",
        "is",
        "are",
        "be",
        "this",
        "that",
        "as",
        "by",
        "from",
        "at",
    }
)

# What BM25 indexes and ranks on, documents and queries alike; edits need
# no version bump (`vocabulary_digest(INDEX)`). Floor 2, not 3 (#790):
# "AI", "DT", "5G" are content words; recall@5 0.84 -> 0.91 on the
# affected queries, and floor 1 adds nothing for 13.5% more tokens
# (bench/RESULTS.md 2026-09-16).
INDEX = Rule(floor=2, stopwords=CORE_STOPWORDS)

# High-IDF question words that out-compete the subject terms. Dropped from
# queries only, so not in INDEX's digest (docs/CORPUS-SEARCH.md).
INTERROGATIVES = frozenset(
    {
        "what",
        "why",
        "how",
        "who",
        "whom",
        "whose",
        "which",
        "when",
        "where",
        "can",
        "could",
        "would",
        "should",
        "will",
        "shall",
        "does",
        "did",
    }
)

# Claim-matching words: stricter than INDEX and never looser, or a match
# could rest on a word retrieval could not rank by. Floor 3 means "AI" can
# rank a document but not match a passage alone; closing that gap needs
# its own measurement.
DISTINCTIVE = Rule(
    floor=3,
    stopwords=CORE_STOPWORDS
    | {
        "it",
        "its",
        "can",
        "has",
        "have",
        "was",
        "were",
        "which",
        "such",
        "these",
        "those",
        "their",
        "than",
        "then",
        "but",
        "not",
        "also",
    },
)


def words(text: str, rule: Rule) -> list[str]:
    # Unpacked once: this runs over every document on a rebuild.
    floor, stopwords = rule
    return [w for w in WORD.findall(text.lower()) if len(w) >= floor and w not in stopwords]


def vocabulary_digest(rule: Rule) -> str:
    """Eight hex digits that move whenever `rule` would split text
    differently. Stopwords are sorted: frozenset order follows
    PYTHONHASHSEED and would invalidate the caches every run."""
    spelled = repr((WORD.pattern, rule.floor, sorted(rule.stopwords)))
    return hashlib.sha256(spelled.encode("utf-8")).hexdigest()[:8]


def index_version(schema: int) -> str:
    """A BM25 cache's version: its hand-bumped `schema` for non-vocabulary
    changes (#762, issue 844), joined to the vocabulary digest."""
    return f"{schema}-{vocabulary_digest(INDEX)}"
