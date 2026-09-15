r"""Strip hand-rolled TikZ library loading from figure files (#781).

Two generations of workaround exist in figure files written before the
renderer hoisted `\usetikzlibrary` into the preamble, and both are worse
than the bug they were written for:

1. Clear `\tikz@library@<name>@loaded` and reload per figure. But
   `tikzlibrarypositioning.code.tex` appends to `\tikz@node@reset@hook`
   *globally* on every load, so after N loads every node's placement
   shift is applied N times.
2. Save the hook once and restore it before each reload. Correct in a
   document containing only second-generation figures -- every
   single-chapter render -- and wrong in a book where the two
   generations meet, because the second saves an already-polluted hook
   as "pristine".

With the library loaded once in the preamble, a figure file's own plain
`\usetikzlibrary` line is a no-op that appends nothing, and both
workarounds are dead weight that will silently break the next assembled
book. This removes them and keeps that line.

**Nothing in this repository needs it.** A grep for either internal over
the tree, over `content/` and over its backup snapshots finds no file;
the 20 files the issue names live in the author's own gitignored
`content/drafts/`. So it is run by whoever has the affected tree:

    python scripts/strip_tikz_load_workarounds.py content/drafts/mybook
    python scripts/strip_tikz_load_workarounds.py content/drafts/mybook --write

Dry-run by default, and that is not politeness: its target is by
definition a gitignored directory where a wrong edit has no undo.

**Line-oriented, deliberately.** Both generations were written as their
own lines above the `tikzpicture`, and a pattern that reached inside a
line could cut a `\draw` in half. A figure that stops compiling is a
worse outcome than a workaround left behind for a human to see, so a
line doing anything else keeps its whole self -- including a `\draw`
whose *comment* mentions the internal.
"""

import argparse
import re
import sys
from pathlib import Path

# The two internals a figure file has no business naming. Kept in step
# with `chitragupta/review/figure_layout/_source.py`'s `_BY_HAND_RE`,
# which reports the same thing rather than repairing it -- this script
# is standalone (`scripts/` ships without the package on some paths), so
# the pattern is restated rather than imported.
_INTERNAL_RE = re.compile(r"\\?(?:tikz@library@[A-Za-z.]+@loaded|tikz@node@reset@hook)")

# A figure file, as this pipeline names them.
_FIGURE_GLOB = "*.tex"


def _is_workaround(line: str) -> bool:
    """Whether this whole line exists only to manage a library load."""
    return bool(_INTERNAL_RE.search(line.split("%")[0]))


def strip_workarounds(source: str) -> str:
    """`source` with every hand-rolled load line removed.

    An `\\makeatletter`/`\\makeatother` pair left holding nothing goes
    too: both generations were written inside one, and a wrapper with an
    empty body reads as a workaround still being there.
    """
    kept = [line for line in source.splitlines(keepends=True) if not _is_workaround(line)]
    return "".join(_without_empty_makeat_pairs(kept))


def _without_empty_makeat_pairs(lines: list[str]) -> list[str]:
    """`lines` with any `\\makeatletter` immediately followed by
    `\\makeatother` dropped, both of them."""
    out: list[str] = []
    for line in lines:
        if out and out[-1].strip() == "\\makeatletter" and line.strip() == "\\makeatother":
            out.pop()
            continue
        out.append(line)
    return out


def _targets(paths: list[str]) -> tuple[list[Path], list[str]]:
    """Every figure file under the given paths, and the ones that do not
    exist."""
    found: list[Path] = []
    missing: list[str] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            found += sorted(path.rglob(_FIGURE_GLOB))
        elif path.is_file():
            found.append(path)
        else:
            missing.append(raw)
    return found, missing


def _process(path: Path, write: bool) -> bool:
    """Report one figure file, rewriting it when asked. True when it
    carried a workaround."""
    source = path.read_text(encoding="utf-8", errors="replace")
    stripped = strip_workarounds(source)
    if stripped == source:
        return False
    print(f"{path}:")
    for line in source.splitlines():
        if _is_workaround(line):
            print(f"  - {line.strip()}")
    if write:
        path.write_text(stripped, encoding="utf-8")
    return True


def main(argv: list[str] | None = None) -> int:
    """Report, and with `--write` repair, every figure file carrying a
    hand-rolled load."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="+", help="figure files, or directories to walk")
    parser.add_argument(
        "--write",
        action="store_true",
        help="rewrite the files (default: report what would change and write nothing)",
    )
    args = parser.parse_args(argv)

    targets, missing = _targets(args.paths)
    for raw in missing:
        print(f"[error] {raw}: not a file or directory", file=sys.stderr)

    changed = sum(_process(path, args.write) for path in targets)
    if not changed:
        print("No figure file carries a hand-rolled TikZ library load.")
    elif not args.write:
        print(f"\n{changed} file(s) would change. Re-run with --write to apply.")
    return 1 if missing else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
