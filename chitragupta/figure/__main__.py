"""`python -m chitragupta figure sync [PATH ...] [--check]` (#1013).

Exit codes: 0 whatever sync found, including a modified region it
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
import sys
from collections import Counter
from pathlib import Path

from chitragupta.figure._block import load_house
from chitragupta.figure._sync import Outcome, run
from chitragupta.progname import prog_for


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog_for("figure"),
        description="Keep the house figure-style block current in every figure file.",
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
    return parser


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
