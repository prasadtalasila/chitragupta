"""Verbatim digest report: how much of a digest is not the sources' own
words, and what every such sentence is (#991).

    python -m chitragupta.review digest <draft>
        split the digest into citation-terminated runs, find each in
        the source it cites, and list every sentence that is not
        verified source text. Leads with the unsupported fraction.

    python -m chitragupta.review digest <draft> --baseline <stem>.digest.json
        the same, then compare with an earlier run: resolved,
        persisting and new items, the counts and fractions before and
        after, and whether the unsupported text fell.

A digest is private study text in the papers' own words
(docs/VERBATIM-DIGEST.md), never a drafting source. Advisory: every
finding is `[surfaced]`, exit 0 whatever it finds. Runs match only
reading-ordered Docling passages: a `pdftotext` run can splice two
columns, so it is reported not checkable rather than compared. The
report is filed unconditionally because its `.json` is the next pass's
`--baseline`. Reads the ledger read-only (#843).
"""

import argparse
import shlex
import sys
from pathlib import Path

from chitragupta import config, ledger, passages, review
from chitragupta.review import (
    _digest_match,
    _digest_recheck,
    _digest_render,
    _digest_repeat,
    _digest_runs,
    _emit,
)
from chitragupta.help_format import ClickParser

AID = "digest"


def build_report(draft: Path) -> tuple[_digest_match.Checked, list[dict]]:
    """Every run of `draft` checked, and the worklist rows for what failed,
    over one ledger connection and one passage lookup per citekey."""
    text = draft.read_text(encoding="utf-8")
    checked = _digest_match.Checked()
    cache: dict[str, tuple[list, str | None]] = {}
    with ledger.reading() as con:

        def lookup(citekey: str) -> tuple[list, str | None]:
            if citekey not in cache:
                cache[citekey] = passages.source_passages(con, citekey)
            return cache[citekey]

        shown = _digest_runs.shown_figures(text)
        for run in _digest_runs.runs(text):
            _digest_match.check_run(run, lookup, checked, shown)
    checked.findings += _digest_repeat.repeats(checked.spans)
    return checked, _digest_render.items(checked, text)


def _command(draft: Path, args: argparse.Namespace) -> str:
    """The bare invocation, even under `--baseline`: the filed `.json` is
    the next run's baseline, so it must name a regenerating command."""
    parts = ["python", "-m", "chitragupta.review", "digest", str(draft)]
    if args.formats != "md,tex,pdf":
        parts += ["--formats", args.formats]
    return shlex.join(parts)


def build_parser(parser=None) -> argparse.ArgumentParser:
    if parser is None:
        parser = ClickParser(
            description="How much of a verbatim digest is not the sources' own words.",
        )
    parser.add_argument("draft", help="The digest to check, under content/drafts/")
    _emit.add_formats(parser)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the payload (or, with --baseline, the comparison) as JSON "
        "instead of the summary. The .json sibling is filed either way.",
    )
    parser.add_argument(
        "--baseline",
        help="Compare this run against a previously filed <stem>.digest.json: "
        "resolved, persisting and new items, counts and fractions before and "
        "after, and whether unsupported text fell.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


def _file(draft: Path, args: argparse.Namespace) -> tuple[dict, dict]:
    checked, rows = build_report(draft)
    command = _command(draft, args)
    body = _digest_render.render_markdown(draft, command, checked, rows)
    written = review.write(draft, AID, body, _emit.formats(args))
    payload = _digest_render.payload(draft, command, checked, rows)
    written["json"] = review.write_json(draft, AID, payload)
    return payload, written


def run(args: argparse.Namespace) -> int:
    """The draft is checked first (exit 1), then the baseline (exit 2)
    before anything is computed, the order `agenda` keeps."""
    try:
        draft = review.require_reviewable(Path(args.draft))
    except (FileNotFoundError, config.OutsideContentDir) as exc:
        print(exc, file=sys.stderr)
        return 1
    baseline = None
    if args.baseline:
        try:
            baseline = _digest_recheck.load_baseline(args.baseline)
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 2
    payload, written = _file(draft, args)
    if baseline is None:
        _emit.announce(payload, written, as_json=args.json)
        return 0
    comparison = _digest_recheck.compare(payload, baseline)
    if args.json:
        recheck = _digest_recheck.recheck_payload(draft, args.baseline, comparison)
        _emit.announce(recheck, written, as_json=True)
    else:
        print(_digest_recheck.format_recheck(args.baseline, comparison))
        review.print_written(written)
    return 0
