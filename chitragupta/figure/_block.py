r"""The house figure-style block as a region inside a figure file (#1013).

A figure must compile alone (in a thesis, in the probe document), so it
carries a copy of the block between marker lines instead of `\input`ing an
install path; this keeps the copy current (docs/TIKZ-STYLE.md).

States: `CURRENT` (installed bytes), `STALE` (a released block in
`assets/tikz/cg-figstyle.versions.toml`, replaceable), `MODIFIED` (paired
markers, unknown bytes), `MISSING`, `MALFORMED` (markers not pairing once).
A modified region is never overwritten: it is someone's work, reported with
a diff for a person to decide.

Pure except `load_house`, so the writer and the renderer share the classifier.
"""

import hashlib
import re
import tomllib
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from chitragupta import config
from chitragupta._tex_comments import strip_comments

# Leading whitespace is tolerated when finding a marker, so a re-indented region
# reads as modified, not missing (which would stamp a second copy).
_START_RE = re.compile(r"^[ \t]*% >>> chitragupta figure style v(\d+)\b[^\n]*$", re.M)
_END_RE = re.compile(r"^[ \t]*% >>> end chitragupta figure style <<<[ \t]*\r?$", re.M)
# Where a missing block goes: above the first line that loads a library
# or opens a picture, so the styles exist before anything uses them.
_ANCHOR_RE = re.compile(r"\\usetikzlibrary\b|\\begin\s*\{tikzpicture\}")
_COMMAND = "python -m chitragupta figure sync"


class State(Enum):
    CURRENT = "current"
    STALE = "stale"
    MODIFIED = "modified"
    MISSING = "missing"
    MALFORMED = "malformed"


@dataclass(frozen=True)
class House:
    """The installed block (LF line endings), its version, and every
    released block's digest mapped to its version."""

    text: str
    version: int
    released: dict[str, int]


@dataclass(frozen=True)
class Region:
    """One file's region: state, the version its start marker names, and
    character offsets (`end` past the end marker's line break; `None`
    without a single region)."""

    state: State
    marker_version: int | None = None
    start: int | None = None
    end: int | None = None


def digest(text: str) -> str:
    """sha256 of a region, CRLF folded and one final newline ensured."""
    lf = text.replace("\r\n", "\n")
    if not lf.endswith("\n"):
        lf += "\n"
    return hashlib.sha256(lf.encode("utf-8")).hexdigest()


def load_house(block: Path | None = None, register: Path | None = None) -> House:
    """The installed block and register. Raises `OSError` or `ValueError`
    (`tomllib.TOMLDecodeError` is one) on a broken install."""
    block = block or config.shipped("assets", "tikz", "cg-figstyle.tex")
    register = register or config.shipped("assets", "tikz", "cg-figstyle.versions.toml")
    text = block.read_text(encoding="utf-8").replace("\r\n", "\n")
    marker = _START_RE.match(text)
    if marker is None:
        raise ValueError(f"{block}: no figure-style start marker on its first line")
    with register.open("rb") as handle:
        recorded = tomllib.load(handle)
    released = {value: int(key[1:]) for key, value in recorded.items()}
    return House(text=text, version=int(marker.group(1)), released=released)


def _line_end(text: str, offset: int) -> int:
    """`offset` moved past its line's break; `_END_RE` already took a CRLF's `\r`."""
    return offset + 1 if text.startswith("\n", offset) else offset


def classify(text: str, house: House) -> Region:
    starts = list(_START_RE.finditer(text))
    ends = list(_END_RE.finditer(text))
    if not starts and not ends:
        return Region(State.MISSING)
    if len(starts) != 1 or len(ends) != 1 or ends[0].start() < starts[0].start():
        return Region(State.MALFORMED)
    start, end = starts[0].start(), _line_end(text, ends[0].end())
    marker_version = int(starts[0].group(1))
    known = house.released.get(digest(text[start:end]))
    if known is None:
        state = State.MODIFIED
    else:
        state = State.CURRENT if known == house.version else State.STALE
    return Region(state, marker_version, start, end)


def _anchor(text: str) -> int | None:
    offset = 0
    for line in text.splitlines(keepends=True):
        if _ANCHOR_RE.search(strip_comments(line)):
            return offset
        offset += len(line)
    return None


def stamp(text: str, house: House) -> str | None:
    """`text` with the current block in place: unchanged when current,
    `None` when the region must not be touched or there is nowhere to
    put one. The file's own line endings are kept."""
    region = classify(text, house)
    if region.state is State.CURRENT:
        return text
    newline = "\r\n" if "\r\n" in text else "\n"
    block = house.text.replace("\n", newline)
    if region.state is State.STALE:
        return text[: region.start] + block + text[region.end :]
    if region.state is State.MISSING:
        at = _anchor(text)
        return None if at is None else text[:at] + block + text[at:]
    return None


def finding(text: str, house: House) -> str | None:
    """One advisory sentence about `text`'s region, `None` when current."""
    region = classify(text, house)
    if region.state is State.CURRENT:
        return None
    if region.state is State.MISSING:
        return f"carries no house figure-style block -- `{_COMMAND}` stamps one"
    if region.state is State.STALE:
        old = house.released[digest(text[region.start : region.end])]
        return (
            f"house figure-style block is v{old}, current is v{house.version} "
            f"-- `{_COMMAND}` refreshes it"
        )
    if region.state is State.MALFORMED:
        return (
            f"house figure-style markers are unpaired or repeated; `{_COMMAND}` will not touch it"
        )
    if (region.marker_version or 0) > house.version:
        return newer_than_install(region, house)
    return (
        f"house figure-style block was edited inside its markers; `{_COMMAND}` will not "
        "touch it -- move a local style below the block (docs/TIKZ-STYLE.md)"
    )


def newer_than_install(region: Region, house: House) -> str:
    return (
        f"house figure-style block is v{region.marker_version}, newer than this "
        f"install's v{house.version}; upgrade chitragupta rather than edit it"
    )
