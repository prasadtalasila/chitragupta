"""Read a book's outline, and refuse one that does not parse.

Split out of `_cli.py` so the feature modules that carry their own
commands -- `_align.py`, `_seed.py` -- can reach it without importing the
module that imports *them*. The alternative was a function-level import
in each command to break the cycle; a six-line module both of them can
depend on says the dependency plainly instead.

The same shape `chitragupta/dossier/` already has, where `_outline.py`
and `_sections.py` hold their own `_cmd_*` and share what they need
through the package rather than through `_cli.py`.
"""

import sys
from pathlib import Path

from chitragupta.spec import SpecError, parse, spec_path


def read_spec(book: Path) -> tuple[str, dict]:
    """A book's spec text and its parse, refusing a book that has none."""
    path = spec_path(book)
    if not path.is_file():
        raise SpecError(
            f"No spec at {path}. Write one with `python -m chitragupta.draft spec init {book}`."
        )
    text = path.read_text(encoding="utf-8")
    return text, parse(text)


def report_problems(parsed: dict, book: Path) -> int:
    """Print every parse problem and refuse.

    Always returns 1, so a caller reads as `return report_problems(...)`.
    Every problem rather than the first: someone fixing an outline wants
    the whole list, not one round trip per missing id.
    """
    for problem in parsed["problems"]:
        print(f"[spec] {problem}", file=sys.stderr)
    print(f"{len(parsed['problems'])} problem(s) in {spec_path(book)}.", file=sys.stderr)
    return 1
