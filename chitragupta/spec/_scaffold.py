"""The two files a new book starts with that its author, not the
outline, owns: a preface and a copyright page (#1137).

`spec init` copies each from `assets/book/` once and never overwrites
it, so re-running anything here cannot cost an author their words.
`spec sign` writes the year into the copyright page the first time the
outline is approved, and never again: a copyright year is the year of
first publication, and one that followed the build date would quietly
become next year's on every rebuild.

Split from `chitragupta/spec/_cli.py` so the commands stay commands; the
file names live here because nothing else writes these files.
"""

import datetime
from pathlib import Path

from chitragupta import config

PREFACE_MD = "preface.md"
COPYRIGHT_TEX = "copyright.tex"
_YEAR = "<year>"


def _this_year() -> int:
    return datetime.date.today().year


def _copy_once(source: Path, target: Path) -> bool:
    if target.exists():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return True


def scaffold(book: Path, specs: Path) -> list[str]:
    """Copy the preface into `book` and the copyright page into `specs`,
    skipping either that already exists; one line per file written."""
    written = []
    preface = Path(book) / PREFACE_MD
    if _copy_once(config.shipped("assets", "book", PREFACE_MD), preface):
        written.append(f"Wrote {preface}: the preface is yours to write.")
    copyright_page = specs / COPYRIGHT_TEX
    if _copy_once(config.shipped("assets", "book", COPYRIGHT_TEX), copyright_page):
        written.append(f"Wrote {copyright_page}: the copyright page is yours to edit.")
    return written


def stamp_year(specs: Path) -> str | None:
    """Write this year over the copyright page's placeholder, if the page
    exists and still has one; the line to print, or None."""
    copyright_page = specs / COPYRIGHT_TEX
    if not copyright_page.is_file():
        return None
    text = copyright_page.read_text(encoding="utf-8")
    if _YEAR not in text:
        return None
    year = _this_year()
    copyright_page.write_text(text.replace(_YEAR, str(year)), encoding="utf-8")
    return f"Wrote the year {year} into {copyright_page}; change it there by hand from now on."
