"""Read a book's outline, and refuse one that does not parse.

Its own module so `_align.py` and `_seed.py` can reach it without
importing `_cli.py`, which imports them; a plain dependency instead of
function-level imports to break the cycle.
"""

import sys
from pathlib import Path

from chitragupta.spec import SpecError, parse, spec_path


def read_spec(book: Path) -> tuple[str, dict]:
    path = spec_path(book)
    if not path.is_file():
        raise SpecError(
            f"No spec at {path}. Write one with `python -m chitragupta.draft spec init {book}`."
        )
    text = path.read_text(encoding="utf-8")
    return text, parse(text)


def report_problems(parsed: dict, book: Path) -> int:
    """Print every parse problem and refuse.

    Always returns 1, so callers `return report_problems(...)`.
    """
    for problem in parsed["problems"]:
        print(f"[spec] {problem}", file=sys.stderr)
    print(f"{len(parsed['problems'])} problem(s) in {spec_path(book)}.", file=sys.stderr)
    return 1
