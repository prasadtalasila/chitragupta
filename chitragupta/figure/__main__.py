"""`python -m chitragupta figure sync [PATH ...] [--check]` (#1013),
`python -m chitragupta figure check <figure.tex> [--width PT] [--layout NAME]
[--json]` (#1053, #1057) and `python -m chitragupta figure new
<figures-dir> <name> --layout ID` and `python -m chitragupta figure look
<figure.tex> [--draft DRAFT]` (#1052).

`figure new` exits 0 once it has written the figure, and 2 for anything
it refused (a name with a path in it, a file already there, an unknown
layout) or could not read from the install; it never writes half.
`figure look` exits 0 whatever the figure does, a failed compile
included, and 2 only for an unreadable figure, a missing `lualatex`,
`tikz.sty` or `pdftoppm` (and `pandoc`, with `--draft`), or a rendered
directory outside the content directory: the cases where it looked at
nothing. A draft that does not render is reported and is not one of
them: the figure's own look is still written.

`figure check` exits 0 whatever it finds: an objective finding is the
skill's to resolve or allow, never an exit code's to enforce. 2 is a
usage error, or a host with no `lualatex` or `tikz.sty`, where it checks
nothing at all rather than report a half that would read as clean.

`figure sync` exit codes: 0 whatever sync found, including a modified region it
refused to touch -- this is an aid, and an aid reports. `--check` is the
one mode that fails: it writes nothing and exits 1 if any file is not
current, which is what `git-hooks/pre-commit` asks it. 2 is a usage
error, or a broken install whose shipped block or register cannot be
read; that is not a finding about any figure, and `chitragupta doctor`
is where to look.

What to do about a modified region is in docs/TIKZ-STYLE.md, "The house
figure style".
"""

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

from chitragupta.figure._block import House, load_house
from chitragupta.figure._check import DEFAULT_WIDTH_PT, check
from chitragupta.figure._check_report import format_text, payload
from chitragupta.figure._layout import layout_names
from chitragupta.figure._look import lines, look
from chitragupta.figure._look_draft import notes, page_line, refresh
from chitragupta.figure._new import Refused, layouts, new_figure
from chitragupta.figure._sync import Outcome, run
from chitragupta.config_path import OutsideContentDir
from chitragupta.progname import prog_for
from chitragupta.render_output._cli import _build_parser as _render_parser
from chitragupta.render_output._cli import _rendered
from chitragupta.render_output._errors import MissingBinary, _require
from chitragupta.render_output._figures import _require_tikz


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog_for("figure"),
        description="Keep the house figure-style block current, and check one figure.",
    )
    verbs = parser.add_subparsers(dest="verb", required=True)
    sync = verbs.add_parser("sync", help="stamp, refresh and report the block in figure files")
    sync.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="files or directories (default: content/drafts/**/figures/*.tex)",
    )
    sync.add_argument(
        "--check", action="store_true", help="write nothing; exit 1 if any file is not current"
    )
    new = verbs.add_parser("new", help="start a figure from a layout's scaffold")
    new.add_argument("figures_dir", type=Path, help="the draft's figures/ directory")
    new.add_argument("name", help="the figure's file stem, e.g. flow for flow.tex")
    new.add_argument("--layout", required=True, choices=list(layouts()), help="the scaffold")
    figure_look = verbs.add_parser("look", help="see one figure as it will print")
    figure_look.add_argument("figure", type=Path, help="the figure's .tex file")
    figure_look.add_argument(
        "--draft",
        type=Path,
        help="also render this draft to pdf and picture the page that holds the figure",
    )
    figure_check = verbs.add_parser("check", help="report every rule one figure file breaks")
    figure_check.add_argument("figure", type=Path, help="the figure's .tex file")
    figure_check.add_argument(
        "--width",
        type=_points,
        default=DEFAULT_WIDTH_PT,
        help=f"target text width in pt (default: {DEFAULT_WIDTH_PT:g}, the render's A4 at 1in)",
    )
    figure_check.add_argument(
        "--layout",
        choices=layout_names(),
        default="",
        help="read the size reports against this layout's reference ranges "
        "(default: the figure's own `%% cg-layout:` line)",
    )
    figure_check.add_argument("--json", action="store_true", help="print the report as JSON")
    return parser


def _points(text: str) -> float:
    """A width in pt: a positive number, or argparse's usage error."""
    try:
        value = float(text)
    except ValueError:
        value = 0.0
    # `nan` and `inf` parse as floats, and every comparison with `nan` is
    # false, so `--width nan` would switch size-width off without a word.
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError(f"not a positive width in pt: {text!r}")
    return value


def _check(args: argparse.Namespace) -> int:
    try:
        args.figure.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"figure check: {args.figure} is not a readable UTF-8 file: {exc}", file=sys.stderr)
        return 2
    try:
        _require("lualatex")
        _require_tikz()  # pragma: no cover-windows
    except MissingBinary as exc:
        print(
            f"figure check: {exc} Nothing was checked. `chitragupta doctor` checks the install.",
            file=sys.stderr,
        )
        return 2
    result = check(args.figure, args.width, args.layout)  # pragma: no cover-windows
    print(
        json.dumps(payload(result), indent=2) if args.json else format_text(result)
    )  # pragma: no cover-windows
    return 0  # pragma: no cover-windows


def _print(outcomes: list[Outcome]) -> None:
    """One line per file that is not current, its detail indented under
    it, then a count of each action."""
    for outcome in outcomes:
        if outcome.action != "current":
            print(f"{outcome.action:<10} {outcome.path}")
            for line in outcome.detail.splitlines():
                print(f"    {line}")
    counts = Counter(o.action for o in outcomes)
    print("figure sync: " + ", ".join(f"{n} {a}" for a, n in sorted(counts.items())))


def _look(args: argparse.Namespace) -> int:
    try:
        args.figure.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"figure look: {args.figure} is not a readable UTF-8 file: {exc}", file=sys.stderr)
        return 2
    try:
        _require("lualatex")
        _require_tikz()  # pragma: no cover-windows
        _require("pdftoppm")  # pragma: no cover-windows
        if args.draft:  # pragma: no cover-windows
            _require("pandoc")
    except MissingBinary as exc:
        print(
            f"figure look: {exc} Nothing was written. `chitragupta doctor` checks the install.",
            file=sys.stderr,
        )
        return 2
    try:  # pragma: no cover-windows
        if args.draft:
            return _look_in_draft(args.figure, args.draft)
        print("\n".join(lines(look(args.figure), args.figure)))
    except OutsideContentDir as exc:  # pragma: no cover-windows
        print(f"figure look: {exc}", file=sys.stderr)
        return 2
    return 0  # pragma: no cover-windows


def _look_in_draft(figure: Path, draft: Path) -> int:
    """Render `draft` to pdf as `draft render` does, then report
    `figure`'s look and the page it printed on."""
    pdf = _rendered(_render_parser().parse_args([str(draft), "--format", "pdf"]))
    if pdf is None:
        # The render printed why; the figure's own look still stands.
        print("\n".join(lines(look(figure), figure)))
        return 0
    refreshed = refresh(draft, pdf)
    for line in notes(refreshed):
        print(line, file=sys.stderr)
    print(f"wrote    {pdf}")
    mine = [item for item in refreshed.figures if item.figure.resolve() == figure.resolve()]
    if not mine:
        print("\n".join(lines(look(figure), figure)))
        print(f"note     {figure}: no figure marker in {draft} names it, so no page PNG")
        return 0
    item = mine[0]
    if item.look:
        print("\n".join(lines(item.look, figure)))
    if item.page:
        print(page_line(item.page, pdf))
    if item.note or not item.page:
        print(f"note     {figure}: {item.note or refreshed.skipped}")
    return 0


def _new(args: argparse.Namespace, house: House) -> int:
    try:
        created = new_figure(args.figures_dir, args.name, args.layout, house)
    except Refused as exc:
        print(f"figure new: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"figure new: {exc}. `chitragupta doctor` checks the install.", file=sys.stderr)
        return 2
    print(f"created  {created.figure}   (from {args.layout})")
    if created.twin:
        print(f"created  {created.twin}   (from {args.layout})")
    else:
        twin = created.figure.with_suffix(".txt")
        print(f"no twin  {args.layout} ships no .txt twin; write {twin}")
    _print([created.sync])
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.verb == "check":
        return _check(args)
    if args.verb == "look":
        return _look(args)
    try:
        house = load_house()
    except (OSError, ValueError) as exc:
        print(
            f"figure {args.verb}: cannot read the house block: {exc}. "
            "`chitragupta doctor` checks the install.",
            file=sys.stderr,
        )
        return 2
    if args.verb == "new":
        return _new(args, house)
    outcomes = run(args.paths, house, check=args.check)
    if not outcomes:
        print("figure sync: no figure files found")
        return 0
    _print(outcomes)
    return 1 if args.check and any(o.action != "current" for o in outcomes) else 0


if __name__ == "__main__":
    sys.exit(main())
