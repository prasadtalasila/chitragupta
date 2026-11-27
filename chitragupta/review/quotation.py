"""Quotation-integrity report: does each quoted span actually appear in
the source it is attributed to?

A quote attributed to a source that lacks it is the fabricated-citekey
failure with a real citekey, which `citation_gate.py` cannot see. It
checks exactly what the evidence sidecar publishes, via
`evidence_appendix.quoted_spans` (cited keys only, `quote:` only, each
quote numbered in its block, #1174), so the two never disagree.

The page is derived, not a contract field (plans/c3-quotation-integrity.md).
**Three outcomes**: `found`, `absent`, and `unverifiable` where only
`pdftotext -layout` text exists, whose spliced columns would make a
correct quote look absent. That third outcome is why this can never be a
gate (docs/ARCHITECTURE.md's Layer 4). The report also says which
`UNIVERSES` it checked (#838), so checking nothing never reads as clean.
A review aid, never a gate, no write lock.

Usage:
    python -m chitragupta.review quotation <draft.md>
    python -m chitragupta.review quotation <draft.md> --json --write
"""

import argparse
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path

from chitragupta import citation_gate, config, evidence_appendix, ledger, passages, review
from chitragupta.review import _emit
from chitragupta.dossier import DossierError, dossier_dir
from chitragupta.review import _quotation_render
from chitragupta.review._quotation_match import Checked, check_one
from chitragupta.help_format import ClickParser


# What `build_report` could see (#838); only "checked" is a clean bill.
# agenda/_render.py's `_QUOTATION_UNIVERSE_NOTES` is pinned against it.
UNIVERSES = ("no-dossier", "no-quotes", "checked")


@dataclass
class Report:
    draft: Path
    checked: list[Checked]
    universe: str

    def of(self, verdict: str) -> list[Checked]:
        return [c for c in self.checked if c.verdict == verdict]


def build_report(draft: Path) -> Report:
    """Every published quote in `draft`'s dossier, checked, over one
    ledger connection."""
    draft = Path(draft)
    try:
        directory = dossier_dir(draft)
    except DossierError:
        # Under content/ but not content/drafts/ (#496): like every sibling
        # aid, an empty report rather than a raise.
        return Report(draft, [], "no-dossier")
    if not directory.is_dir():
        # `dossier_dir` does not check existence; agenda agrees (#838).
        return Report(draft, [], "no-dossier")
    text = draft.read_text(encoding="utf-8")
    spans = evidence_appendix.quoted_spans(text, directory, latex=citation_gate.is_latex(draft))
    if not spans:
        return Report(draft, [], "no-quotes")
    checked = []
    with ledger.reading() as con:
        for citekey, quotes in spans.items():
            # Once per source, not per quote: a digest may carry many.
            found, reason = passages.source_passages(con, citekey)
            for index, quote in enumerate(quotes, start=1):
                one = check_one(citekey, quote, found, reason)
                one.index, one.of = index, len(quotes)
                checked.append(one)
    return Report(draft, checked, "checked")


def findings(report: Report) -> list[dict]:
    """One object per `absent` quote -- never per `unverifiable` one --
    worst near-miss first."""
    found = [
        {
            "id": _quotation_render.finding_id(c.citekey, c.quote),
            "citekey": c.citekey,
            "quote": c.quote,
            "near_miss_page": c.near_miss_page,
            "near_miss_score": c.near_miss_score,
            "index": c.index,
            "of": c.of,
        }
        for c in report.of("absent")
    ]
    return sorted(found, key=lambda f: (f["near_miss_score"], f["citekey"]))


def _command(draft: Path, as_json: bool, write: bool) -> str:
    """The invocation recorded in the Markdown header and JSON envelope."""
    parts = ["python", "-m", "chitragupta.review", "quotation", str(draft)]
    if as_json:
        parts += ["--json"]
    if write:
        parts += ["--write"]
    return shlex.join(parts)


def run_text(draft: Path) -> str:
    """What a bare invocation prints, without capturing stdout (a test
    pins two runs byte-identical)."""
    report = build_report(draft)
    return _quotation_render.format_report(report, findings(report))


def build_parser(parser=None) -> argparse.ArgumentParser:
    """This aid's flags, declared once for chitragupta/review/__main__.py."""
    if parser is None:
        # Not this module's docstring (#152; see chitragupta/corpus.py).
        parser = ClickParser(
            description="Check each quoted span against the source it is attributed to.",
        )
    parser.add_argument("draft", help="Path to the draft to check")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the verdicts as JSON instead of as text. "
        "--write files it beside the report either way.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Also write the report to content/review/, mirroring the "
        "draft's path. Off by default: printing is the usual use.",
    )
    _emit.add_formats(parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


def run(args: argparse.Namespace) -> int:
    """Dispatch already-parsed arguments (for __main__). Exits 0 whatever
    it finds: a non-zero exit is how a gate speaks.
    """
    try:
        draft_path = review.require_reviewable(Path(args.draft))
    except (FileNotFoundError, config.OutsideContentDir) as exc:
        print(exc, file=sys.stderr)
        return 1

    report = build_report(draft_path)
    found = findings(report)

    return _emit.emit(
        draft_path,
        "quotation",
        args,
        text=lambda: _quotation_render.format_report(report, found),
        command=lambda: _command(draft_path, args.json, args.write),
        payload=lambda command: _quotation_render.quotation_payload(report, command, found),
        markdown=lambda command: _quotation_render.render_markdown(report, command, found),
    )
