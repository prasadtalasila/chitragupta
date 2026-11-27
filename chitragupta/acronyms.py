"""The acronym vocabulary a genre skill reads at step 0.

A vendored default (`assets/style/acronyms.toml`) merged with an optional
user file (`[style].acronyms`), the user winning on a shared key. Additive,
unlike the CSL/Vale overrides: the user's vocabulary and the project's
floor sit together (#190, assets/style/README.md).
"""

import re
import sys
import tomllib
from pathlib import Path

from chitragupta import config

# Unreadable files already reported, so a sweep says so once.
_NOTED: set[Path] = set()


def _load(path: Path) -> dict[str, str]:
    """`path`'s acronyms, or `{}` when it is absent or unreadable.

    An unreadable file is skipped with one stderr note (#1023): the
    vocabulary is an aid, and a typo used to crash every command reading
    it. stderr, because several of those commands' stdout is parsed.
    """
    if not path.is_file():
        return {}
    try:
        with path.open("rb") as handle:
            parsed = tomllib.load(handle)
    except (tomllib.TOMLDecodeError, OSError) as exc:
        if path not in _NOTED:
            _NOTED.add(path)
            print(
                f"  [note] acronym file skipped, it could not be parsed as TOML: {path}: {exc}",
                file=sys.stderr,
            )
        return {}
    # A non-string value is dropped, not raised, so one bad entry does not
    # cost the vocabulary; consumers only add or compare (#504).
    return {k: v for k, v in parsed.items() if isinstance(v, str)}


def load_vocabulary() -> dict[str, str]:
    """The merged acronym -> expansion table a genre skill drafts from."""
    vendored = _load(config.ACRONYMS_DEFAULT_PATH)
    if config.ACRONYMS_PATH == config.ACRONYMS_DEFAULT_PATH:
        return vendored
    user = _load(config.ACRONYMS_PATH)
    return {**vendored, **user}


# A short run of capitals, as Acronyms.yml: "DTaaS" matches, "Connector"
# does not.
_LOOKS_LIKE_AN_ACRONYM = re.compile(r"^[A-Z]{2,}[A-Za-z]*$")

# The commoner glossary shape, "Digital twin (DT)" -- measured, a real book's
# glossary had no bare acronyms at all. Acronyms.yml's `second` pattern
# assumes it too. The name captured is the terse phrase, as a vocabulary
# value must be.
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
    `chitragupta.dossier` -- that module already imports this one for
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

    Compared case-insensitively with trailing punctuation stripped: both
    sides are terse, so exact equality is the honest test. The
    bare-acronym branch is unmeasured on real drafts; advisory either way.
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


# Everything from the reference list on is excluded: on a real book 11 of
# 15 raw candidates were venue abbreviations from citation lines.
_REFERENCES_HEADING = re.compile(
    r"^#{1,6}\s*(?:[\d.]+\s*)?References\s*$", re.MULTILINE | re.IGNORECASE
)

# The glossary's parenthetical shape applied to prose, as Acronyms.yml's
# `second` field. `(?:-[a-z]+)*` keeps "Mock-up" whole, or `--apply` would
# write "Interface" as an FMI expansion; lowercase only after the hyphen.
_BODY_ACRONYM = re.compile(
    r"(?P<name>(?:\b[A-Z][a-z]+(?:-[a-z]+)*[\s-]){1,5})\((?P<acronym>[A-Z]{2,6})\)"
)


def body_candidates(text: str) -> dict[str, str]:
    """Acronyms first defined in a draft's own prose as "Name (ACRONYM)",
    in `dossier.glossary_terms()`'s shape so a caller can merge them
    before `suggest()`.

    Text from a `## References` heading on is excluded, and a single
    newline (a hard wrap) is collapsed so a wrapped name is not truncated;
    a blank line still separates paragraphs. First occurrence wins;
    advisory only, applied only by a human's `--apply`.
    """
    heading = _REFERENCES_HEADING.search(text)
    if heading:
        text = text[: heading.start()]
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
    found: dict[str, str] = {}
    seen: set[str] = set()
    for match in _BODY_ACRONYM.finditer(text):
        acronym = match.group("acronym")
        if acronym in seen:
            continue
        seen.add(acronym)
        name = match.group("name").strip()
        found[f"{name} ({acronym})"] = name
    return found
