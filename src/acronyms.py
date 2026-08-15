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


def suggest(glossary: dict[str, str]) -> dict[str, str]:
    """`glossary` entries that look like an acronym and aren't in the
    vocabulary yet -- candidates for the user's own acronyms file.

    Takes a draft's already-parsed glossary (`dossier.glossary_terms()`)
    rather than a draft path, so this module never needs to import
    `src.dossier` -- that module already imports this one for
    `load_vocabulary()`, and a two-way import would be a cycle.
    """
    vocabulary = load_vocabulary()
    return {
        term: definition
        for term, definition in glossary.items()
        if _LOOKS_LIKE_AN_ACRONYM.match(term) and term not in vocabulary
    }
