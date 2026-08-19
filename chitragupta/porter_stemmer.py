"""The classic Porter stemming algorithm (Porter, 1980), vendored.

`chitragupta/overlap_skipgram.py` (tier 2, #133) needs a stemmer to fold
inflection/synonym-adjacent word forms together before skip-gram hashing --
the same reduction PAN 2013's winning CoReMo design (Torrejon & Ramos)
built on, cited in discussion #115 and docs/PLAGIARISM-DESIGN.md. No dependency
on the corpus already carries this (nltk and its Snowball stemmer are not
project dependencies), and this algorithm is a fixed, public specification
rather than a moving target, so it is reimplemented from the published
rules here rather than pulled in as a new dependency for one function.

Deliberately a fresh implementation of the published algorithm, not a
transcription of any single existing open-source port: the whole feature
this module supports exists to catch verbatim reuse, and copying a
particular implementation almost word-for-word would be exactly that.

`stem(word)` is the only entry point a caller needs; everything else is
the five suffix-stripping steps the original paper defines, applied in
order. Input is assumed already lowercased `[a-z]+` (see
`chitragupta/overlap_skipgram.py`'s tokenizer) -- this module does no case
folding or character-class filtering of its own.

Coupled to `overlap_skipgram._TOKENIZER_VERSION` by contract, not by
import: any change to a suffix rule here changes stemmed output for
already-cached documents, and that constant is what forces a rebuild.
There is no automated check that a change here bumped it -- but
`tests/test_porter_stemmer.py` pins `stem()`'s output for enough words
across all five steps that an unintended rule change breaks a test
before it can reach a stale cache silently.
"""

from __future__ import annotations

_VOWELS = "aeiou"


def _is_consonant(word: str, i: int) -> bool:
    """Whether `word[i]` is a consonant, Porter's definition: a letter
    other than a, e, i, o, u, and 'y' counts as a consonant unless the
    letter immediately before it is itself a consonant (so "toy" has a
    consonant y, "syzygy" has consonant y's after the first)."""
    ch = word[i]
    if ch in _VOWELS:
        return False
    if ch != "y":
        return True
    return i == 0 or not _is_consonant(word, i - 1)


def _cv_string(word: str) -> str:
    """`word` collapsed to its consonant/vowel pattern, e.g. "trouble" ->
    "cvccvcv" folded to the CV-sequence "cvcv" is not what this returns --
    this is the raw per-letter C/V string, folded into m() below."""
    return "".join("c" if _is_consonant(word, i) else "v" for i in range(len(word)))


def _measure(stem: str) -> int:
    """Porter's `m`: the number of consonant-sequence -> vowel-sequence
    transitions in `stem`, i.e. `[C](VC){m}[V]` -- "tree" -> m=0, "trees"
    -> m=1, "trouble" -> m=1, "troubles" -> m=2. A leading consonant run
    and a trailing vowel run are both optional and don't themselves count;
    only a completed VC pair does."""
    cv = _cv_string(stem)
    cv = cv.lstrip("c")
    return cv.count("vc")


def _ends_with_vowel(stem: str) -> bool:
    """Porter's `*v*`: stem contains a vowel somewhere (a leading
    consonant-only stem like "ps" has none)."""
    return any(not _is_consonant(stem, i) for i in range(len(stem)))


def _ends_double_consonant(stem: str) -> bool:
    """Porter's `*d`: stem ends in two identical consonants ("hopp",
    "topp") -- caught by 1b's second branch before it strips one."""
    return (
        len(stem) >= 2
        and stem[-1] == stem[-2]
        and _is_consonant(stem, len(stem) - 1)
    )


def _cvc(stem: str) -> bool:
    """Porter's `*o`: stem ends consonant-vowel-consonant, where the final
    consonant is not w, x or y ("wil", "hop" qualify; "wow", "sky" -- the
    literal exceptions the paper carves out -- do not)."""
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
    """The three-way patch-up 1b applies after stripping "ed"/"ing",
    once the stem has been shown to contain a vowel: restore a silent
    "e" where dropping the suffix left an ambiguous ending, undouble a
    doubled final consonant that isn't l/s/z, and otherwise leave the
    bare stem alone unless it's a single short cvc word, which also gets
    an "e" back ("hop" -> "hope", not left as a monosyllable that reads
    as a different word)."""
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


# (suffix, replacement) pairs for step 2, applied only when the resulting
# stem has measure > 0 -- Porter's Table for turning derivational endings
# into their root form ("relational" -> "relate", not just "relat").
_STEP2_RULES = (
    ("ational", "ate"), ("tional", "tion"), ("enci", "ence"), ("anci", "ance"),
    ("izer", "ize"), ("abli", "able"), ("alli", "al"), ("entli", "ent"),
    ("eli", "e"), ("ousli", "ous"), ("ization", "ize"), ("ation", "ate"),
    ("ator", "ate"), ("alism", "al"), ("iveness", "ive"), ("fulness", "ful"),
    ("ousness", "ous"), ("aliti", "al"), ("iviti", "ive"), ("biliti", "ble"),
)

_STEP3_RULES = (
    ("icate", "ic"), ("ative", ""), ("alize", "al"), ("iciti", "ic"),
    ("ical", "ic"), ("ful", ""), ("ness", ""),
)

# Step 4 endings are dropped outright (measure > 1), no replacement --
# except "ion", which additionally requires the stem to end in s or t,
# so "motion" doesn't lose its whole identity to a rule meant for
# "adoption" -> "adopt".
_STEP4_SUFFIXES = (
    "al", "ance", "ence", "er", "ic", "able", "ible", "ant", "ement",
    "ment", "ent", "ou", "ism", "ate", "iti", "ous", "ive", "ize",
)


def _step2(word: str) -> str:
    for suffix, replacement in _STEP2_RULES:
        stem = _split_suffix(word, suffix)
        if stem is not None and _measure(stem) > 0:
            return stem + replacement
    return word


def _step3(word: str) -> str:
    for suffix, replacement in _STEP3_RULES:
        stem = _split_suffix(word, suffix)
        if stem is not None and _measure(stem) > 0:
            return stem + replacement
    return word


def _step4(word: str) -> str:
    stem = _split_suffix(word, "ion")
    if stem is not None and _measure(stem) > 1 and stem.endswith(("s", "t")):
        return stem
    for suffix in _STEP4_SUFFIXES:
        stem = _split_suffix(word, suffix)
        if stem is not None and _measure(stem) > 1:
            return stem
    return word


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
    unchanged -- the algorithm's measure-based rules need at least a
    short consonant/vowel run to mean anything, and stemming "as" or "is"
    would only erase words the stopword list (see `overlap_skipgram.py`)
    is meant to remove entirely, not shorten."""
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
