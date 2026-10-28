"""`python -m chitragupta figure sync [PATH ...] [--check]` (#1013) and
`python -m chitragupta figure check <figure.tex> [--width PT] [--json]`
(#1053).

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

from chitragupta.figure._block import load_house
from chitragupta.figure._check import DEFAULT_WIDTH_PT, check
from chitragupta.figure._check_report import format_text, payload
from chitragupta.figure._sync import Outcome, run
from chitragupta.progname import prog_for
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
    figure_check = verbs.add_parser("check", help="report every rule one figure file breaks")
    figure_check.add_argument("figure", type=Path, help="the figure's .tex file")
    figure_check.add_argument(
        "--width",
        type=_points,
        default=DEFAULT_WIDTH_PT,
        help=f"target text width in pt (default: {DEFAULT_WIDTH_PT:g}, the render's A4 at 1in)",
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
    result = check(args.figure, args.width)  # pragma: no cover-windows
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


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.verb == "check":
        return _check(args)
    try:
        house = load_house()
    except (OSError, ValueError) as exc:
        print(
            f"figure sync: cannot read the house block: {exc}. "
            "`chitragupta doctor` checks the install.",
            file=sys.stderr,
        )
        return 2
    outcomes = run(args.paths, house, check=args.check)
    if not outcomes:
        print("figure sync: no figure files found")
        return 0
    _print(outcomes)
    return 1 if args.check and any(o.action != "current" for o in outcomes) else 0


if __name__ == "__main__":
    sys.exit(main())
