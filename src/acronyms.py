"""The acronym vocabulary a genre skill reads at step 0.

A vendored default (`assets/style/acronyms.toml`) merged with an optional
user file (`[style].acronyms` in config.toml), the user's expansion
winning on a shared key. Additive, not a full-replacement override like
CSL_STYLE_PATH/VALE_CONFIG_PATH: a user's own domain vocabulary and this
project's PDF/CPU/URL floor are meant to sit together, not replace one
another. See assets/style/README.md and GitHub issue #190.
"""

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
