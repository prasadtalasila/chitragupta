"""A fragment's derived heading labels, prefixed with its unit id (#1122).

pandoc labels a heading the author gave no `{#id}` from its text alone.
A standalone document is never `\\input` beside another, so that is
harmless there; in a book it is not. Units repeat their section names
-- Summary, Exercises, Further reading -- so the assembled `book.tex`
defined `summary` once per chapter: 84 `multiply defined` warnings in a
real seven-chapter book, and a `\\ref` to any of them resolving to
whichever chapter LaTeX read last.

`assets/pandoc/unit_labels.lua` puts `<stem>-` in front of every such
derived label and of every in-unit link to one, so `u1.md`'s Summary is
`u1-summary`. The stem is the draft's own, not the temporary copy's,
because a book unit's file name is its outline id (book-assembler step
4). A label the author wrote is left alone: that one is what the
outline and the registry resolve against, and renaming it would orphan
every reference to it. pandoc's own `--id-prefix` would have been the
obvious tool, but its LaTeX writer ignores it (pandoc 3.7.0.2).
"""

from pathlib import Path

from chitragupta import config

FILTER = config.shipped("assets", "pandoc", "unit_labels.lua")


def pandoc_args(input_path: Path, fragment: bool) -> list[str]:
    """The argv that prefixes `input_path`'s derived labels, or none for a
    standalone render, whose labels cannot collide."""
    if not fragment:
        return []
    return [
        "--lua-filter",
        str(FILTER),
        "--metadata",
        f"chitragupta-label-prefix={input_path.stem}-",
    ]
