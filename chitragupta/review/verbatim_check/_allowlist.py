"""Per-host boilerplate (acronyms, fixed phrasing, defined terms, whole
paragraphs) this draft's owner has decided `scan` should never flag.
config.VERBATIM_ALLOWLIST_PATH is gitignored, per-host data -- see
docs/PLAGIARISM.md and config.py's own comment on it.

Split out of chitragupta/review/verbatim_check.py (#361) -- see
chitragupta/review/verbatim_check/_corpus.py's docstring for the split.
"""

import tomllib

from chitragupta import config, overlap_skipgram
from chitragupta.review.verbatim_check._corpus import norm

_ALLOWLIST_KEYS = ("acronyms", "phrases", "definitions", "paragraphs")


def _load_allowlist_phrases() -> list[tuple[str, ...]]:
    """Every phrase across the allowlist file's four categories,
    normalized into word tuples via `norm()` -- the same tokenization
    `scan` itself uses on the draft, so a phrase matches regardless of
    how it's capitalized or spaced in the file.

    No file -> no suppressions: the normal state for a fresh clone, since
    nothing ever commits this file (see config.VERBATIM_ALLOWLIST_PATH).
    A *present* file that isn't valid TOML, that this process cannot read
    (permissions, or the path is a directory), whose category isn't a
    list of strings, or that carries a key outside the four documented
    ones (a typo like `pharses`), raises ValueError rather than
    degrading to "no suppressions" -- a policy file that silently
    stopped suppressing is exactly the failure that surfaces months
    later as "why did this stop working," not as "no findings today."
    An unknown key is exactly that failure mode: without the check, a
    misspelled category loads as an empty list, no phrases suppress, and
    nothing says why. `run()` only catches `ValueError` as a usage error
    (`OSError` would otherwise escape as an unhandled traceback instead
    of the same clean exit 2), so both open() and parsing are wrapped.
    """
    path = config.VERBATIM_ALLOWLIST_PATH
    if not path.exists():
        return []
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"{path}: malformed TOML -- {exc}") from None
    except OSError as exc:
        raise ValueError(f"{path}: cannot read allowlist -- {exc}") from None

    unknown = sorted(set(data) - set(_ALLOWLIST_KEYS))
    if unknown:
        raise ValueError(
            f"{path}: unknown key(s) {unknown} -- expected only {list(_ALLOWLIST_KEYS)}"
        )

    phrases = []
    for key in _ALLOWLIST_KEYS:
        values = data.get(key, [])
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            raise ValueError(f"{path}: {key!r} must be a list of strings")
        phrases.extend(values)

    normalized = (tuple(norm(p)) for p in phrases)
    return [words for words in normalized if words]


def _mask_allowlisted(
    span_word_strs: list[str], allowlist_tuples: list[tuple[str, ...]]
) -> list[bool]:
    """Boolean mask, one entry per word in `span_word_strs`, True where
    that position is covered by a contiguous occurrence of any
    allowlisted phrase.

    A phrase can occur more than once in one span, and two allowlisted
    phrases can overlap (a whole paragraph allowlisted alongside a
    phrase that also appears inside it) -- ORing into one mask handles
    both without double-counting a word twice.
    """
    n = len(span_word_strs)
    masked = [False] * n
    for phrase in allowlist_tuples:
        length = len(phrase)
        if length == 0 or length > n:
            continue
        for i in range(n - length + 1):
            if tuple(span_word_strs[i : i + length]) == phrase:
                for j in range(i, i + length):
                    masked[j] = True
    return masked


def _mask_allowlisted_stemmed(
    span_word_strs: list[str], allowlist_tuples: list[tuple[str, ...]]
) -> list[bool]:
    """Tier-2 analogue of `_mask_allowlisted`: an allowlisted phrase is
    matched after the same stem-and-drop-stopwords reduction
    `overlap_skipgram` applies before hashing, not against
    `span_word_strs`' literal wording -- a tier-2 finding is itself only
    a stemmed, skip-gram-level match, so a literal-text allowlist check
    would almost never fire on it, defeating the point of allowlisting
    against a tier built to tolerate a synonym swap in the first place.

    The mask is still indexed by `span_word_strs`' own (original,
    unstemmed) positions: a stemmed-phrase match spanning reduced
    positions p..q masks every *original* position from the first
    matched reduced token's index to the last's, inclusive -- the same
    "the whole matched stretch counts, stopwords and all" convention
    `_mask_allowlisted` uses for tier 1.
    """
    span_stems, span_positions = overlap_skipgram.stem_filter(span_word_strs)
    masked = [False] * len(span_word_strs)
    m = len(span_stems)
    for phrase in allowlist_tuples:
        stems, _ = overlap_skipgram.stem_filter(list(phrase))
        length = len(stems)
        if length == 0 or length > m:
            continue
        for i in range(m - length + 1):
            if tuple(span_stems[i : i + length]) == tuple(stems):
                first, last = span_positions[i], span_positions[i + length - 1]
                for j in range(first, last + 1):
                    masked[j] = True
    return masked
