"""Plagiarism / page-locator helper for reviewing a draft.

One of the six aids in the **review layer**, beside
citation_provenance.py, citation_coverage.py, synthesis.py, figure_layout/
and uncited_prose.py -- read over a finished draft, by a person or by a driver, never a gate, and
never holding the write lock. chitragupta/review/__init__.py owns where a written
report goes (`content/review/<topic>/<stem>.verbatim.md`, mirroring the
draft's path) and what its header looks like.

Reached through the layer's single entry point, chitragupta/review/__main__.py,
never as `python -m chitragupta.review.verbatim_check`: this module has no
__main__ block of its own, so that invocation would import it and exit 0
without doing anything. See docs/ARCHITECTURE.md on why every layer's
command surface stays one level deep.

Four modes:
    python -m chitragupta.review verbatim overlap <draft.md> <citekey> [--n 8]
        report the longest verbatim word-n-gram runs shared between the
        draft's sentences citing <citekey> and that source's parsed text.

    python -m chitragupta.review verbatim scan <draft.md> [--min-run 8] [--gap 1]
                                       [--limit N] [--json]
                                       [--write] [--formats md,tex,pdf]
        slide the WHOLE draft across the WHOLE corpus index (chitragupta/overlap_index.py),
        not just the sources a paragraph happens to cite -- catches verbatim
        reuse from an uncited source, and reuse in connective prose that
        cites nothing at all. Prints by default; --write also files the
        report under content/review/, beside the same draft's provenance
        and coverage reports. --json prints the same findings as data
        instead of as text, and --write files that too, as the report's
        `.json` sibling -- see `scan_payload`.

    python -m chitragupta.review verbatim recheck <draft.md> --baseline <scan.json>
                                          [--json]
        re-scan the draft at the baseline's own floor and report which of
        its findings are gone, which remain, and which the edits
        introduced. The deterministic half of #129's remediation loop:
        "did this rewrite fix the finding without breaking anything else"
        is an acceptance test, and one a model should not be deciding by
        reading two reports side by side. Still not a gate -- it exits 0
        whatever it finds, and `python -m chitragupta.draft gate` remains the only
        thing in this pipeline that blocks.

    python -m chitragupta.review verbatim locate <citekey> "<phrase>" [more phrases...]
        report which PDF page each phrase (or its distinctive words)
        appears on, for fact-checking page numbers.

Exits 0 on every successful invocation, findings or not -- a review aid,
not a gate. A draft this layer will not read (missing, or outside
content/) exits 1; a malformed invocation exits 2, the usual CLI-usage
error, not a verdict.

**A package since #361**, split out of what was one 2357-line module: the
corpus lookup (`bib_entry`/`pdf_path`/`pages`/`norm`/`sentences_citing`)
moved to `_corpus.py`, masking/tokenizing to `_masking.py`, the
gap-tolerant run merger to `_merge.py`, the per-host allowlist to
`_allowlist.py`, the helpers every tier shares (line lookup, finding
identity, cites/quotes) to `_shared.py`, the three detection tiers to
`_exact.py`/`_skipgram.py`/`_embed.py`, the scan orchestrator and published
finding shape to `_scan.py`, the Markdown report to `_scan_render.py`, the
`scan` CLI mode's stdout/JSON forms to `_scan_cmd.py`, `recheck`'s baseline
and comparison machinery to `_baseline.py`/`_recheck.py`, and the `overlap`
and `locate` CLI modes to `_overlap.py` -- the tiers issue #361 itself
named, each with their own state and thresholds, plus the seams around
them. Only the CLI wiring itself stays here, because it has nowhere else
with fewer than one caller. Every name below is re-exported so `from
chitragupta.review import verbatim_check as vc; vc.<name>` keeps reaching
it exactly as it did when this was one file.
"""

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from chitragupta import config, review
from chitragupta.review.verbatim_check._allowlist import (
    _load_allowlist_phrases,
    _mask_allowlisted,
    _mask_allowlisted_stemmed,
)
from chitragupta.review.verbatim_check._baseline import _BASELINE_FIELDS, load_baseline
from chitragupta.review.verbatim_check._corpus import (
    BIB,
    PARSED_DIR,
    bib_entry,
    norm,
    pages,
    pdf_path,
    sentences_citing,
)
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
    _flags,
    _tier_note,
    published,
    scan_findings,
)
from chitragupta.review.verbatim_check._scan_cmd import (
    cmd_scan,
    format_scan,
    scan_command,
    scan_payload,
)
from chitragupta.review.verbatim_check._scan_render import render_scan_markdown
from chitragupta.review.verbatim_check._shared import _line_at, _newline_offsets, finding_id


def _bounded_int(minimum: int, name: str) -> Callable[[str], int]:
    """An argparse `type` that rejects an out-of-range value as a usage
    error rather than letting it through to be silently absorbed.

    A value that parses fine can still be nonsensical: `--limit 0`
    silently hides every finding behind the same "no verbatim run found"
    message a genuinely clean draft prints, and a negative `--gap` breaks
    even a pure-verbatim run's merge (Python's `list[:0]`/negative-gap
    arithmetic degrade silently rather than raising) -- both look like
    "nothing to report" instead of the usage error they actually are.
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
    """The `verbatim` aid's four modes.

    `parser` is passed by chitragupta/review/__main__.py, which has already
    created this aid's subparser and needs the modes hung off *that*
    rather than off a fresh top-level parser -- so the flags are declared
    once, here, and the entry point never restates them.
    """
    if parser is None:
        # A one-line description rather than this module's docstring, for
        # the reason chitragupta/corpus.py's DESCRIPTION gives (#152).
        parser = argparse.ArgumentParser(
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
    p_scan.add_argument(
        "--formats",
        default="md,tex,pdf",
        help="Additional formats to render beside the Markdown "
        "report (default: md,tex,pdf). The .md is always "
        "written -- it is the report; tex/pdf are renders "
        "of it, and need pandoc/pdflatex on PATH.",
    )

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

    # So run() can print this aid's own help when no mode was given,
    # whether it was reached directly or through the entry point's
    # `verbatim` subparser -- which is a different parser object.
    parser.set_defaults(_parser=parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Exit codes: `0` on every successful invocation, findings or not --
    a review aid, not a gate. `1` for a draft this layer will not read
    (missing, or outside `content/`). `2` for a malformed invocation,
    the usual CLI-usage error, which argparse already uses.

    No mode at all prints the usage and exits 0: that is the same "tell
    me how to use this" request as `--help`, not an error.
    """
    parser = build_parser()
    return run(parser.parse_args(sys.argv[1:] if argv is None else argv))


def run(args: argparse.Namespace) -> int:
    """Dispatch already-parsed arguments.

    Split from main() so chitragupta/review/__main__.py can hand over the args it
    parsed with this module's own build_parser(), rather than re-slicing
    argv and parsing it twice.
    """
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
                formats=[f.strip() for f in args.formats.split(",") if f.strip()],
                as_json=args.json,
            )
    except ValueError as exc:
        # "this input can't be scanned as asked" (e.g. --min-run below the
        # corpus index's own n-gram size, or a baseline that cannot serve
        # as one) is a usage error, not a finding.
        print(exc, file=sys.stderr)
        return 2
    return 0
