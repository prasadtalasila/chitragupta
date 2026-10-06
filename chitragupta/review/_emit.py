"""How a review aid prints and files its report (#849).

`review/__init__.py` fixes the output *contract* -- report paths, the
banner, `write`/`write_json`/`print_written` -- and names fragility as the
reason there is one. The *procedure* around it was the part every aid
copied: decide from `--json`/`--write` what to print, build the command
line and payload only when something needs them, file the Markdown and
its `.json` sibling, and move the written-files summary to stderr when
stdout has become a payload. Ten aids carried that sequence, three of
them at or one under docs/CODE-STANDARDS.md's 25-statement limit, so a
change to it had ten places to land.

A submodule rather than more of `review/__init__.py`, which sits at the
250-code-line limit.
"""

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path

from chitragupta import install, review

# Every aid's --formats help (#1022): written once, because ten copies
# went on naming pdflatex after #996 moved a pdf render to LuaLaTeX.
# The wording matches docs/CLI.md's per-aid rows.
FORMATS_HELP = (
    "Additional formats to render beside the Markdown report (default: "
    "md,tex,pdf). The .md is always written -- it is the report; tex and "
    "pdf are renders of it: tex needs pandoc, and pdf needs pandoc and "
    f"LuaLaTeX with the fonts {install.remedy('os-deps')} installs."
)


def add_formats(parser: argparse.ArgumentParser) -> None:
    """The `--formats` option every aid takes, with its one help text."""
    parser.add_argument("--formats", default="md,tex,pdf", help=FORMATS_HELP)


def formats(args: argparse.Namespace) -> list[str]:
    """`--formats md,pdf` as `["md", "pdf"]`: split on commas, stripped,
    empties dropped, so `"md, pdf,"` means what its author meant."""
    return [fmt.strip() for fmt in args.formats.split(",") if fmt.strip()]


def emit(
    draft: Path,
    aid: str,
    args: argparse.Namespace,
    *,
    text: Callable[[], str],
    command: Callable[[], str],
    payload: Callable[[str], dict],
    markdown: Callable[[str], str],
) -> int:
    """Print, and under `--write` file, one aid's report. Returns 0: an
    aid is advisory whatever it found.

    Every piece is a callable, built only for the combination that needs
    it -- the human text is never rendered under `--json`, and the command
    line, payload and Markdown are never built for a bare run. That is the
    evaluation order each aid had inline, kept. `command()` is called at
    most once and handed to both `payload` and `markdown`, so the report
    and its `.json` name the same invocation.
    """
    if not (args.json or args.write):
        print(text())
        return 0
    invocation = command()
    data = payload(invocation)
    print(json.dumps(data, indent=2) if args.json else text())
    if args.write:
        written = review.write(draft, aid, markdown(invocation), formats(args))
        written["json"] = review.write_json(draft, aid, data)
        review.print_written(written, stream=sys.stderr if args.json else sys.stdout)
    return 0


def announce(data: dict, written: dict[str, Path], *, as_json: bool) -> None:
    """What an aid that files its report unconditionally prints once it
    has: the payload under `--json`, with the written-files summary moved
    to stderr so stdout stays a valid JSON file, and otherwise the
    summary alone."""
    if as_json:
        print(json.dumps(data, indent=2))
        review.print_written(written, stream=sys.stderr)
    else:
        review.print_written(written)
