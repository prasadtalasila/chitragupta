"""Plagiarism / page-locator helper for reviewing a draft.

A review aid, never a gate, no write lock; chitragupta/review/__init__.py
owns where a written report goes. Reached only through
chitragupta/review/__main__.py: this package has no __main__ block, so
`python -m chitragupta.review.verbatim_check` would exit 0 doing nothing
(docs/ARCHITECTURE.md: command surfaces stay one level deep).

Four modes:
    python -m chitragupta.review verbatim overlap <draft.md> <citekey> [--n 8]
        longest verbatim word-n-gram runs shared with one cited source.

    python -m chitragupta.review verbatim scan <draft.md> [--min-run 8] [--gap 1]
                                       [--limit N] [--json]
                                       [--write] [--formats md,tex,pdf]
        the whole draft against the whole corpus index
        (chitragupta/overlap_index.py), catching reuse from uncited
        sources and in uncited prose. --write files the report (and its
        `.json` sibling, see `scan_payload`) under content/review/.

    python -m chitragupta.review verbatim recheck <draft.md> --baseline <scan.json>
                                          [--json]
        re-scan at the baseline's floor and report findings gone, kept and
        introduced: #129's acceptance test, decided deterministically
        rather than by a model comparing reports. Still exits 0.

    python -m chitragupta.review verbatim locate <citekey> "<phrase>" [more phrases...]
        which PDF page each phrase (or its distinctive words) is on.

Exits 0 findings or not; 1 for a draft the layer will not read; 2 for a
malformed invocation. A package since #361; every name is re-exported
so `vc.<name>` still reaches it.
"""

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from chitragupta import config, review
from chitragupta.review import _emit
from chitragupta.review.verbatim_check._allowlist import (
    _load_allowlist_phrases,
    _mask_allowlisted,
    _mask_allowlisted_stemmed,
)
from chitragupta.review.verbatim_check._baseline import _BASELINE_FIELDS, load_baseline
from chitragupta.review.verbatim_check._corpus import norm, pages, pdf_path, sentences_citing
from chitragupta.review.verbatim_check._masking import (
    _lower_offsets,
    _mask_for_scan,
    _paragraphs,
    _quote_char_spans,
    _tokenize_draft,
)
from chitragupta.review.verbatim_check._merge import _merge_runs, _merge_spans
from chitragupta.review.verbatim_check._overlap import cmd_locate, cmd_overlap
from chitragupta.review.verbatim_check._recheck import (
    cmd_recheck,
    format_recheck,
    recheck_command,
    recheck_findings,
    recheck_payload,
)
from chitragupta.review.verbatim_check._scan import (
    LONG_RUN_WORDS,
    _PAYLOAD_FIELDS,
    _bucket,
    _bucket_title,
    published,
    scan_findings,
)
from chitragupta.review.verbatim_check._scan_notes import _flags, _tier_note
from chitragupta.review.verbatim_check._scan_cmd import (
    cmd_scan,
    format_scan,
    scan_command,
    scan_payload,
)
from chitragupta.review.verbatim_check._scan_render import render_scan_markdown
from chitragupta.review.verbatim_check._shared import _line_at, _newline_offsets, finding_id
from chitragupta.help_format import ClickParser


def _bounded_int(minimum: int, name: str) -> Callable[[str], int]:
    """An argparse `type` that rejects an out-of-range value as a usage
    error: `--limit 0` and a negative `--gap` otherwise degrade silently
    into "nothing to report".
    """

    def parse(raw: str) -> int:
        try:
            value = int(raw)
        except ValueError:
            raise argparse.ArgumentTypeError(f"{raw!r} is not a valid value") from None
        if value < minimum:
            raise argparse.ArgumentTypeError(f"{name} must be >= {minimum}")
        return value

    return parse


def build_parser(parser: argparse.ArgumentParser | None = None) -> argparse.ArgumentParser:
    """The `verbatim` aid's four modes, declared once for __main__."""
    if parser is None:
        # Not this module's docstring (#152; see chitragupta/corpus.py).
        parser = ClickParser(
            description="Report how much wording a draft shares with the sources it cites.",
        )
    sub = parser.add_subparsers(dest="mode")

    p_overlap = sub.add_parser("overlap", help="per-citekey verbatim runs")
    p_overlap.add_argument("draft", help="Markdown draft to check")
    p_overlap.add_argument("citekey", help="The cited source to compare against")
    p_overlap.add_argument(
        "--n",
        type=_bounded_int(1, "--n"),
        default=8,
        help="Minimum run length in words (default: 8)",
    )

    p_scan = sub.add_parser("scan", help="whole-draft x whole-corpus scan")
    p_scan.add_argument("draft", help="Markdown draft to scan")
    p_scan.add_argument(
        "--min-run",
        type=_bounded_int(1, "--min-run"),
        default=None,
        help="Reporting length floor in words (default: the corpus index's own n-gram size)",
    )
    p_scan.add_argument(
        "--gap",
        type=_bounded_int(0, "--gap"),
        default=1,
        help="Non-matching words tolerated inside a run (default: 1)",
    )
    p_scan.add_argument(
        "--limit",
        type=_bounded_int(1, "--limit"),
        default=None,
        help="Cap how many findings print (default: all of them)",
    )
    p_scan.add_argument(
        "--json",
        action="store_true",
        help="Print the findings as JSON instead of as text, for a "
        "caller that would otherwise parse the printed form. "
        "--write files it beside the report either way.",
    )
    p_scan.add_argument(
        "--write",
        action="store_true",
        help="Also write the report to content/review/, mirroring the "
        "draft's path. Off by default: printing is the usual use.",
    )
    _emit.add_formats(p_scan)

    p_recheck = sub.add_parser("recheck", help="this scan against a recorded one")
    p_recheck.add_argument("draft", help="Markdown draft to re-scan")
    p_recheck.add_argument(
        "--baseline",
        required=True,
        help="A scan payload to compare against, as written by "
        "`scan --write`. Its --min-run and --gap are reused, "
        "so the two scans are comparable.",
    )
    p_recheck.add_argument(
        "--json", action="store_true", help="Print the comparison as JSON instead of as text."
    )

    p_locate = sub.add_parser("locate", help="which page a phrase is on")
    p_locate.add_argument("citekey", help="The source to search")
    p_locate.add_argument("phrases", nargs="+", help="Phrases to locate")

    # The entry point's `verbatim` subparser is a different parser object,
    # so run() needs this one to print help when no mode was given.
    parser.set_defaults(_parser=parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Exit codes as the module docstring says. No mode prints the usage
    and exits 0: the same request as `--help`, not an error.
    """
    parser = build_parser()
    return run(parser.parse_args(sys.argv[1:] if argv is None else argv))


def run(args: argparse.Namespace) -> int:
    """Dispatch already-parsed arguments (for __main__, so argv is parsed
    once)."""
    if args.mode is None:
        args._parser.print_help()
        return 0

    if args.mode == "locate":
        cmd_locate(args.citekey, *args.phrases)
        return 0

    try:
        draft = review.require_reviewable(Path(args.draft))
    except (FileNotFoundError, config.OutsideContentDir) as exc:
        print(exc, file=sys.stderr)
        return 1

    if args.mode == "overlap":
        cmd_overlap(str(draft), args.citekey, args.n)
        return 0

    try:
        if args.mode == "recheck":
            cmd_recheck(str(draft), args.baseline, as_json=args.json)
        else:
            cmd_scan(
                str(draft),
                args.min_run,
                args.gap,
                args.limit,
                write=args.write,
                formats=_emit.formats(args),
                as_json=args.json,
            )
    except ValueError as exc:
        # Unscannable as asked (e.g. --min-run below the index's n-gram
        # size, or an unusable baseline): a usage error, not a finding.
        print(exc, file=sys.stderr)
        return 2
    return 0
