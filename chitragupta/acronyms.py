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

from chitragupta import config


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


# Where a numbered reference list starts, in every genre this pipeline's
# skills produce (`## 6.15 References`, `## References`, ...). Excluding
# everything from here on is load-bearing, not defensive: measured
# against the real 15-chapter book, a citation line shaped like
# `[12] Author, "Title," in *Venue (ACRONYM)*, pp. 1-9, year.` matches
# _BODY_ACRONYM for every conference name in it -- 11 of 15 raw
# candidates on that book were venue abbreviations (ICCCN, ICSA, ETFA,
# ...) from exactly this, and zero were real domain acronyms.
_REFERENCES_HEADING = re.compile(
    r"^#{1,6}\s*(?:[\d.]+\s*)?References\s*$", re.MULTILINE | re.IGNORECASE
)

# The same shape _PARENTHETICAL_ACRONYM matches in a glossary bullet,
# applied to running prose instead of an isolated bolded term -- and the
# same pattern assets/vale/styles/chitragupta/Acronyms.yml's `second`
# field already matches for its own, unrelated check (expanded-at-first-
# use), so this is an established convention, not a new heuristic.
# `(?:-[a-z]+)*` carries a hyphenated word: chapter 6 of the real book
# defines "**Functional Mock-up Interface (FMI)**", and without it the
# name capture restarts at the hyphen and yields "Interface" -- a wrong
# expansion `acronyms-suggest --apply` would then write into the author's
# own vocabulary as if they had typed it. Lowercase after the hyphen
# only, so "Digital Twin-Based" keeps its existing reading as two words.
_BODY_ACRONYM = re.compile(
    r"(?P<name>(?:\b[A-Z][a-z]+(?:-[a-z]+)*[\s-]){1,5})\((?P<acronym>[A-Z]{2,6})\)"
)


def body_candidates(text: str) -> dict[str, str]:
    """Acronyms first defined in a draft's own raw prose via the
    "Name (ACRONYM)" shape -- returned in the same `{bolded-term-shape:
    definition}` shape `dossier.glossary_terms()` uses, so a caller can
    merge this with the real glossary before handing the combined dict
    to `suggest()`, which never needs to know there were two sources.

    Two things measured against the real 15-chapter book before this was
    written, both load-bearing:

    - **Everything from a `## References` heading onward is excluded**
      -- see `_REFERENCES_HEADING`'s own comment for the measurement.
    - **A single newline is a hard line-wrap, not a paragraph break, and
      is collapsed to a space before matching.** Markdown wraps prose at
      a fixed column, so `"**Digital Twin\\nAggregate (DTA)**"` is one
      phrase split across two physical lines on disk; matching the raw
      text truncated it to `"Aggregate"`. A blank line (a real paragraph
      break) is left alone, so two adjacent paragraphs are never fused
      into one candidate.

    First occurrence per acronym wins, approximating "first use" without
    attempting exact first-use detection (section order, the quoted-span
    exemption `docs/WRITING-STANDARDS.md` §9 gives every rule here) -- a
    false or truncated candidate costs nothing, since `suggest()` is
    advisory-only and never applied without a human running `--apply`.
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
