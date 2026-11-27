"""Per-host boilerplate (acronyms, fixed phrasing, defined terms, whole
paragraphs) this draft's owner has decided `scan` should never flag.
config.VERBATIM_ALLOWLIST_PATH is gitignored, per-host data -- see
docs/PLAGIARISM.md.
"""

import tomllib

from chitragupta import config, overlap_skipgram
from chitragupta.review.verbatim_check._corpus import norm

_ALLOWLIST_KEYS = ("acronyms", "phrases", "definitions", "paragraphs")


def _load_allowlist_phrases() -> list[tuple[str, ...]]:
    """Every phrase across the allowlist file's four categories, as word
    tuples via `norm()`, the tokenization `scan` uses on the draft.

    No file means no suppressions. A present file that is malformed,
    unreadable, mistyped or has an unknown key (a typo like `pharses`)
    raises ValueError: a policy file that silently stopped suppressing
    surfaces months later. OSError is wrapped too, since `run()` turns
    only ValueError into a clean exit 2.
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
    """Per-word mask of `span_word_strs`, True where any allowlisted phrase
    covers it; ORing handles repeated and overlapping phrases."""
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
    """Tier-2 analogue of `_mask_allowlisted`: phrases match after
    `overlap_skipgram`'s stem-and-drop-stopwords reduction, since a
    literal check would almost never fire on a stemmed tier-2 finding.
    The mask stays indexed by original positions, covering the whole
    matched stretch, stopwords and all.
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
