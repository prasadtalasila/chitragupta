"""A fragment's derived heading labels, prefixed with its unit id (#1122).

Units repeat section names (Summary, Exercises), so pandoc's text-derived
labels collided across a book's chapters and `\\ref`s resolved to the last
one read. `assets/pandoc/unit_labels.lua` prefixes derived labels and their
in-unit links with the draft's stem; author-written labels are left alone,
as the outline and registry resolve against them. pandoc's `--id-prefix` is
ignored by its LaTeX writer (pandoc 3.7.0.2).
"""

from pathlib import Path

from chitragupta import config

FILTER = config.shipped("assets", "pandoc", "unit_labels.lua")


def pandoc_args(input_path: Path, fragment: bool) -> list[str]:
    """The argv that prefixes derived labels; none for a standalone render."""
    if not fragment:
        return []
    return [
        "--lua-filter",
        str(FILTER),
        "--metadata",
        f"chitragupta-label-prefix={input_path.stem}-",
    ]
