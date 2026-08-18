"""The acronym vocabulary a genre skill reads at step 0.

A vendored default (`assets/style/acronyms.toml`) merged with an optional
user file (`[style].acronyms` in config.toml), the user's expansion
winning on a shared key. Additive, not a full-replacement override like
CSL_STYLE_PATH/VALE_CONFIG_PATH: a user's own domain vocabulary and this
project's PDF/CPU/URL floor are meant to sit together, not replace one
another. See assets/style/README.md and GitHub issue #190.
"""

import re
import tomllib
from pathlib import Path

from src import config


def _load(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    with path.open("rb") as handle:
        return tomllib.load(handle)


def load_vocabulary() -> dict[str, str]:
    """The merged acronym -> expansion table a genre skill drafts from."""
    vendored = _load(config.ACRONYMS_DEFAULT_PATH)
    if config.ACRONYMS_PATH == config.ACRONYMS_DEFAULT_PATH:
        return vendored
    user = _load(config.ACRONYMS_PATH)
    return {**vendored, **user}


# A shape close enough to Acronyms.yml's own heuristic (a short run of
# capital letters) to flag as "probably an acronym" without a false
# positive on an ordinary capitalised glossary term: "DTaaS" and "FMU"
# both match; "Twin state" and "Connector" don't, because neither starts
# with two or more capitals in a row.
_LOOKS_LIKE_AN_ACRONYM = re.compile(r"^[A-Z]{2,}[A-Za-z]*$")

# The other shape a glossary bullet's bolded term takes -- "Digital twin
# (DT)" rather than "DT" on its own. Measured, not assumed: of the 155
# distinct glossary terms across the real 15-chapter book at
# content/dossiers/books/digital-twins-for-software-engineers, none are a
# bare acronym and 7 (DT, DM, DS, DES, RTF, ROM, UQ) are this parenthetical
# shape -- so the bare-acronym branch above was firing on none of this
# project's own real content. It is also the convention Acronyms.yml
# already assumes: its `second` pattern,
# `(?:\b[A-Z][a-z]+[\s-]){1,5}\(([A-Z]{2,6})\)`, expects an expansion
# followed by "(ACRONYM)". The captured name is the terse phrase before
# the parenthesis, not the bullet's full prose -- a vocabulary file's
# values are terse ("PDF = Portable Document Format"), and a paragraph is
# not a usable one.
_PARENTHETICAL_ACRONYM = re.compile(r"^(?P<name>.+?)\s*\((?P<acronym>[A-Z]{2,6})\)$")


def _candidate(term: str, definition: str) -> tuple[str, str] | None:
    """The `(acronym, terse expansion)` this glossary bullet defines, or
    None if `term` matches neither acronym shape `suggest()` and
    `stale_expansions()` both recognise."""
    if _LOOKS_LIKE_AN_ACRONYM.match(term):
        return term, definition
    match = _PARENTHETICAL_ACRONYM.match(term)
    if match:
        return match.group("acronym"), match.group("name").strip()
    return None


def suggest(glossary: dict[str, str]) -> dict[str, str]:
    """`glossary` entries that look like an acronym and aren't in the
    vocabulary yet -- candidates for the user's own acronyms file.

    Takes a draft's already-parsed glossary (`dossier.glossary_terms()`)
    rather than a draft path, so this module never needs to import
    `src.dossier` -- that module already imports this one for
    `load_vocabulary()`, and a two-way import would be a cycle.
    """
    vocabulary = load_vocabulary()
    candidates = {}
    for term, definition in glossary.items():
        found = _candidate(term, definition)
        if found is None:
            continue
        acronym, expansion = found
        if acronym not in vocabulary:
            candidates[acronym] = expansion
    return candidates


def stale_expansions(glossary: dict[str, str]) -> dict[str, tuple[str, str]]:
    """Acronyms this glossary defines whose recorded expansion disagrees
    with the current vocabulary -- `{acronym: (glossary's expansion,
    vocabulary's expansion)}`.

    Compared case-insensitively with trailing punctuation stripped, not by
    substring: a vocabulary value is terse and so is the name `_candidate`
    extracts from a parenthetical term, so the two sides are the same
    shape and an exact match is the honest comparison. Measured against
    the real book named above: a vocabulary built from `suggest()`'s own
    output produces zero of these, and hand-changing one recorded
    expansion produces exactly one, naming the chapter that defines it.

    The bare-acronym branch (`"DTaaS" -- Digital Twin as a Service.`) gets
    the same equality check, but unlike the parenthetical branch above, no
    real draft in this project's corpus uses that shape yet, so this half
    is unmeasured. Low-cost either way -- this feeds an advisory finding,
    never a gate.
    """
    vocabulary = load_vocabulary()
    stale = {}
    for term, definition in glossary.items():
        found = _candidate(term, definition)
        if found is None:
            continue
        acronym, expansion = found
        if acronym not in vocabulary:
            continue
        recorded = vocabulary[acronym].strip().rstrip(".").lower()
        seen = expansion.strip().rstrip(".").lower()
        if recorded != seen:
            stale[acronym] = (expansion.strip(), vocabulary[acronym])
    return stale
