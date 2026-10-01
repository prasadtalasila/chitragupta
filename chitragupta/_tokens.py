"""The one rule for reading words off text, and its two named settings.

Issue 845. BM25's index (`retrieval._tokenize`) and the claim-matching
word set (`passages.distinctive`) each carried their own copy of
`[a-z0-9]+`, their own length floor and their own stopword list, and the
two BM25 caches were versioned by integers that a comment in a third
file asked to be bumped whenever its stopwords moved. Four bumps landed
that way (`retrieval_cache._INDEX_SCHEMA_VERSION`'s own history), and a
missed one fails silently: cached and fresh entries ranked on different
vocabularies, with no error.

So the rule lives here once, each consumer names the setting it reads,
and `vocabulary_digest` turns the index setting into the part of both
caches' versions nobody has to remember. Stdlib-only, like both caches,
so it runs under bare `python`.

The verbatim tier (`overlap_index._norm`, `review/verbatim_check`) keeps
every word and has its own on-disk caches with their own
`_TOKENIZER_VERSION`, so it is deliberately not a setting here:
borrowing `WORD` from this module would make it the next thing whose
version a comment has to keep in step. `tests/test_tokens.py` pins
instead that it splits exactly where these two do.
"""

import hashlib
import re
from typing import NamedTuple

# Lowercase alphanumeric runs. Applied to already-lowercased text, which
# matters: against raw text it splits "Configuration" into "onfiguration"
# (see `overlap_source_text`'s docstring).
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

# What BM25 indexes and ranks on -- documents, passages, titles and the
# query alike. Editing this needs no version bump anywhere: both caches'
# versions carry `vocabulary_digest(INDEX)`.
#
# Floor 2, not 3, since #790: a two-character token is a content word in
# a technical bibliography ("AI", "DT", "5G", "ML") and the old floor put
# every one of them outside both the index and the query, so a search for
# "5G" returned nothing with no ranking it could have contributed to.
# Measured before it moved, on this project's own corpus
# (bench/RESULTS.md, 2026-09-16): on the 32 of 258 self-retrieval queries
# whose terms the floor actually changes, recall@5 goes 0.8438 -> 0.9062
# and nDCG@5 0.7335 -> 0.8130, six queries better against one worse.
# Stopping at 2 rather than 1 is measured too, not assumed: floor 1 wins
# nothing floor 2 had not already won and costs 13.5% more tokens per
# document. The stopword list is consulted independently of the length,
# so "of" and "in" stay out at either floor.
INDEX = Rule(floor=2, stopwords=CORE_STOPWORDS)

# The words that distinguish one claim from another, which is what the
# review aids match a claim against a passage on. Stricter than INDEX in
# both directions and never looser -- a word kept here that BM25 dropped
# would be a match on something retrieval could not have ranked by. The
# extras feed no index, so they are free to change on their own.
#
# Floor 3 here while INDEX is at 2 means a two-character term ("AI")
# can rank a document but never match a passage on its own. That gap is
# now a difference between two named settings rather than between two
# copies of a regex; closing it is a change to what the aids report and
# wants its own measurement, not a side effect of this one.
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
    # Unpacked once rather than read as attributes per word: this runs
    # over every parsed document on an index rebuild.
    floor, stopwords = rule
    return [w for w in WORD.findall(text.lower()) if len(w) >= floor and w not in stopwords]


def vocabulary_digest(rule: Rule) -> str:
    """Eight hex digits that move whenever `rule` would split text
    differently. The stopwords are sorted first: a frozenset's iteration
    order follows PYTHONHASHSEED, so hashing it as-is would invalidate
    the caches on every run."""
    spelled = repr((WORD.pattern, rule.floor, sorted(rule.stopwords)))
    return hashlib.sha256(spelled.encode("utf-8")).hexdigest()[:8]


def index_version(schema: int) -> str:
    """A BM25 cache's version: its own hand-bumped `schema`, for rule
    changes that are not vocabulary (#762's `field_freqs`, issue 844's
    decode), joined to the digest of what it was tokenized by."""
    return f"{schema}-{vocabulary_digest(INDEX)}"
