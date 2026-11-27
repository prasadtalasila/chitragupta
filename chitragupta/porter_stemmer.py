"""The classic Porter stemming algorithm (Porter, 1980), vendored.

Tier 2 (`overlap_skipgram.py`, #133) stems before skip-gram hashing, as
PAN 2013's CoReMo did (docs/PLAGIARISM-DESIGN.md). Reimplemented from
the published rules rather than added as a dependency, and freshly
written, not transcribed from a port: this feature exists to catch
verbatim reuse. Input is assumed lowercased `[a-z]+`.

Coupled to `overlap_skipgram._TOKENIZER_VERSION` by contract: a rule
change alters cached stems and must bump it. tests/test_porter_stemmer.py
pins enough output to catch an unintended change, which also guards
`bench/RESULTS.md`'s 2026-09-15 comparison. Retrieval declined stemming
(#787), so nothing on that path imports this.
"""

from __future__ import annotations

_VOWELS = "aeiou"


def _is_consonant(word: str, i: int) -> bool:
    """Porter's consonant: not a, e, i, o, u, and 'y' only when the letter
    before it is not itself a consonant."""
    ch = word[i]
    if ch in _VOWELS:
        return False
    if ch != "y":
        return True
    return i == 0 or not _is_consonant(word, i - 1)


def _cv_string(word: str) -> str:
    """`word` as its raw per-letter C/V string, folded in `_measure`."""
    return "".join("c" if _is_consonant(word, i) else "v" for i in range(len(word)))


def _measure(stem: str) -> int:
    """Porter's `m` in `[C](VC){m}[V]`: "tree" -> 0, "trouble" -> 1,
    "troubles" -> 2."""
    cv = _cv_string(stem)
    cv = cv.lstrip("c")
    return cv.count("vc")


def _ends_with_vowel(stem: str) -> bool:
    """Porter's `*v*`: stem contains a vowel somewhere."""
    return any(not _is_consonant(stem, i) for i in range(len(stem)))


def _ends_double_consonant(stem: str) -> bool:
    """Porter's `*d`: stem ends in two identical consonants."""
    return len(stem) >= 2 and stem[-1] == stem[-2] and _is_consonant(stem, len(stem) - 1)


def _cvc(stem: str) -> bool:
    """Porter's `*o`: stem ends consonant-vowel-consonant, the final one
    not w, x or y."""
    if len(stem) < 3:
        return False
    return (
        _is_consonant(stem, len(stem) - 3)
        and not _is_consonant(stem, len(stem) - 2)
        and _is_consonant(stem, len(stem) - 1)
        and stem[-1] not in "wxy"
    )


def _split_suffix(word: str, suffix: str) -> "str | None":
    """`word` with `suffix` removed, or `None` if it doesn't end that way."""
    if suffix and word.endswith(suffix):
        return word[: -len(suffix)]
    return None


def _step1a(word: str) -> str:
    for suffix, replacement in (("sses", "ss"), ("ies", "i"), ("ss", "ss"), ("s", "")):
        stem = _split_suffix(word, suffix)
        if stem is not None:
            return stem + replacement
    return word


def _step1b(word: str) -> str:
    stem = _split_suffix(word, "eed")
    if stem is not None:
        return stem + "ee" if _measure(stem) > 0 else word

    for suffix in ("ed", "ing"):
        stem = _split_suffix(word, suffix)
        if stem is None or not _ends_with_vowel(stem):
            continue
        return _step1b_restore(stem)
    return word


def _step1b_restore(stem: str) -> str:
    """1b's patch-up after stripping "ed"/"ing": restore a silent "e",
    undouble a final consonant other than l/s/z, or give a short cvc stem
    its "e" back ("hop" -> "hope")."""
    if stem.endswith(("at", "bl", "iz")):
        return stem + "e"
    if _ends_double_consonant(stem) and stem[-1] not in "lsz":
        return stem[:-1]
    if _measure(stem) == 1 and _cvc(stem):
        return stem + "e"
    return stem


def _step1c(word: str) -> str:
    stem = _split_suffix(word, "y")
    if stem is not None and _ends_with_vowel(stem):
        return stem + "i"
    return word


# Step 2 (suffix, replacement) pairs, applied when the stem has m > 0.
_STEP2_RULES = (
    ("ational", "ate"),
    ("tional", "tion"),
    ("enci", "ence"),
    ("anci", "ance"),
    ("izer", "ize"),
    ("abli", "able"),
    ("alli", "al"),
    ("entli", "ent"),
    ("eli", "e"),
    ("ousli", "ous"),
    ("ization", "ize"),
    ("ation", "ate"),
    ("ator", "ate"),
    ("alism", "al"),
    ("iveness", "ive"),
    ("fulness", "ful"),
    ("ousness", "ous"),
    ("aliti", "al"),
    ("iviti", "ive"),
    ("biliti", "ble"),
)

_STEP3_RULES = (
    ("icate", "ic"),
    ("ative", ""),
    ("alize", "al"),
    ("iciti", "ic"),
    ("ical", "ic"),
    ("ful", ""),
    ("ness", ""),
)

# Step 4 endings drop outright (m > 1); "ion" also needs a stem ending in
# s or t, so "motion" survives a rule meant for "adoption".
_STEP4_SUFFIXES = (
    "al",
    "ance",
    "ence",
    "er",
    "ic",
    "able",
    "ible",
    "ant",
    "ement",
    "ment",
    "ent",
    "ou",
    "ism",
    "ate",
    "iti",
    "ous",
    "ive",
    "ize",
)


def _longest_matching_suffix(word: str, suffixes) -> "str | None":
    """The longest entry of `suffixes` that `word` ends with, or `None`.
    Steps 2-4 test one suffix's condition once, never falling through to
    a shorter one when it fails."""
    longest = None
    for suffix in suffixes:
        if word.endswith(suffix) and (longest is None or len(suffix) > len(longest)):
            longest = suffix
    return longest


def _step2(word: str) -> str:
    suffix = _longest_matching_suffix(word, (rule[0] for rule in _STEP2_RULES))
    if suffix is None:
        return word
    replacement = dict(_STEP2_RULES)[suffix]
    stem = word[: -len(suffix)]
    return stem + replacement if _measure(stem) > 0 else word


def _step3(word: str) -> str:
    suffix = _longest_matching_suffix(word, (rule[0] for rule in _STEP3_RULES))
    if suffix is None:
        return word
    replacement = dict(_STEP3_RULES)[suffix]
    stem = word[: -len(suffix)]
    return stem + replacement if _measure(stem) > 0 else word


def _step4(word: str) -> str:
    stem = _split_suffix(word, "ion")
    if stem is not None and _measure(stem) > 1 and stem.endswith(("s", "t")):
        return stem
    suffix = _longest_matching_suffix(word, _STEP4_SUFFIXES)
    if suffix is None:
        return word
    stem = word[: -len(suffix)]
    return stem if _measure(stem) > 1 else word


def _step5a(word: str) -> str:
    stem = _split_suffix(word, "e")
    if stem is None:
        return word
    if _measure(stem) > 1:
        return stem
    if _measure(stem) == 1 and not _cvc(stem):
        return stem
    return word


def _step5b(word: str) -> str:
    if word.endswith("ll") and _measure(word[:-1]) > 1:
        return word[:-1]
    return word


def stem(word: str) -> str:
    """`word`'s Porter stem. Words of two letters or fewer are returned
    unchanged; stemming them would only erase stopwords."""
    if len(word) <= 2:
        return word
    word = _step1a(word)
    word = _step1b(word)
    word = _step1c(word)
    word = _step2(word)
    word = _step3(word)
    word = _step4(word)
    word = _step5a(word)
    word = _step5b(word)
    return word
