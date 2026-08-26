"""Quotation-integrity report: does each quoted span actually appear in
the source it is attributed to?

A `quote:` is verbatim by contract, and it reaches a rendered sidecar in
quotation marks under an attribution. Nothing before this checked that
the span is in the paper it names. A quotation attributed to a source
that does not contain it is the same failure class as a fabricated
citekey -- a plausible artefact with nothing real behind it -- and it is
the one part of that class `chitragupta/citation_gate.py` cannot see,
because the citekey *is* real.

**It checks exactly what the evidence sidecar publishes**, by calling
`evidence_appendix.quoted_spans` rather than reimplementing it. Three
decisions come along inherited rather than restated, and that is the
point: only citekeys the draft actually cites; `quote:` and only
`quote:`, so a legacy `support:` window nobody chose as a quotation is
not checked as though someone had; and one quote per block, which
docs/DOSSIER.md's "three possible fields" makes the contract rather than
`_evidence_check.fields`'s accident. Reading the dossier directly here
instead would put the support-is-not-a-quote rule in a second place, and
two modules deciding separately what counts as a published quote is how
this aid comes to check a set the sidecar does not print.

**The roadmap asks for a page the contract does not carry.** C3 reads
"verify each quoted span appears verbatim in the cited source at the
cited page", and a block has `relevance:`/`claim:`/`quote:` and no page.
So the page is *derived* -- located, then reported -- rather than added
as a field to a contract that shipped. plans/c3-quotation-integrity.md
records the rejected alternative.

**Three outcomes, not two.** `found` and `absent` are what the issue
asks for; `unverifiable` is the third, and it is why this aid can never
become a gate. At `passages.py`'s page-level rungs the only text
available is `pdftotext -layout` output, which preserves a page's visual
arrangement rather than its reading order -- on a two-column paper each
line splices two columns, and a perfectly correct quotation is simply
not contiguous. Calling that `absent` would assert a fabrication that is
not there, in a report whose entire worth is being trusted about exactly
that. So `absent` is a finding, `unverifiable` is a count, and a check
that needs a third outcome is not a two-valued gate however binary it
looks. docs/ARCHITECTURE.md's Layer 4 has the argument: which side a
check falls on is decided by what it is measured against -- here, the
parse, a derived artefact -- not by how decidable its answer is.

**Today it checks nothing on any real draft**, and that is correct
rather than a gap. No dossier in this repository carries a `quote:` yet;
`quote:` is optional and absent by default, because a captured quote is
a quote in the drafter's context and A2's contract exists to remove
those. This aid is what makes the first one safe to publish.

One of the seven commands in the **review layer**, beside
citation_provenance.py, citation_coverage.py, verbatim_check/,
synthesis.py, figure_layout/ and uncited_prose.py -- read over a
finished draft, by a person or by a driver, never a gate, and never
holding the write lock.

Usage:
    python -m chitragupta.review quotation <draft.md>
    python -m chitragupta.review quotation <draft.md> --json --write
"""

import argparse
import hashlib
import json
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path

from chitragupta import config, evidence_appendix, ledger, passages, review
from chitragupta.dossier import dossier_dir
from chitragupta.review import _quotation_render
from chitragupta.review._quotation_match import Checked, check_one


@dataclass
class Report:
    draft: Path
    checked: list[Checked]

    def of(self, verdict: str) -> list[Checked]:
        return [c for c in self.checked if c.verdict == verdict]


def build_report(draft: Path) -> Report:
    """Every published quote in `draft`'s dossier, checked.

    The ledger connection is opened once for the whole run rather than
    per citekey: `passages.source_passages` needs one only to reach its
    page-level rungs, and a report over twenty quotes should not open
    twenty connections to answer that.
    """
    draft = Path(draft)
    spans = evidence_appendix.quoted_spans(draft.read_text(encoding="utf-8"), dossier_dir(draft))
    if not spans:
        return Report(draft, [])
    with ledger.connection() as con:
        return Report(
            draft,
            [
                check_one(citekey, quote, *passages.source_passages(con, citekey))
                for citekey, quote in spans.items()
            ],
        )


def finding_id(citekey: str, quote: str) -> str:
    """A finding's name, stable across runs and position-free -- the same
    convention the other six aids' `finding_id` use.

    Keyed on the pair whose truth is in question, so both halves hold and
    both are wanted. Editing an unrelated block renames nothing, and
    re-attributing the quote or correcting it to the real span makes the
    finding disappear, which is what "this finding is gone" should mean
    (R2). And *any* edit to the quote text is a new finding by
    construction, a typo fix included: a changed span is a different
    assertion about the source and has not been checked. Keying on the
    citekey alone would let a repaired quote inherit its predecessor's
    identity and read, in a later comparison, as one that was resolved.
    """
    return hashlib.sha256(f"{citekey}\n{quote}".encode()).hexdigest()[:12]


def findings(report: Report) -> list[dict]:
    """One object per `absent` quote -- never per `unverifiable` one.

    Worst near-miss first, then by citekey: a span whose words are not in
    the source at all is a different claim from one that is nearly there,
    and a reviewer should meet the first kind before the second.
    """
    found = [
        {
            "id": finding_id(c.citekey, c.quote),
            "citekey": c.citekey,
            "quote": c.quote,
            "near_miss_page": c.near_miss_page,
            "near_miss_score": c.near_miss_score,
        }
        for c in report.of("absent")
    ]
    return sorted(found, key=lambda f: (f["near_miss_score"], f["citekey"]))


def _command(draft: Path, as_json: bool, write: bool) -> str:
    """The invocation recorded in both the Markdown header and the JSON
    envelope."""
    parts = ["python", "-m", "chitragupta.review", "quotation", str(draft)]
    if as_json:
        parts += ["--json"]
    if write:
        parts += ["--write"]
    return shlex.join(parts)


def quotation_payload(report: Report, command: str) -> dict:
    """The same verdicts the report prints, as data -- an additional
    serialisation, never a second computation.

    Every checked quote appears, not only the findings: the tier that
    confirmed a span is what tells a reader the check was contiguous
    rather than an ordered alignment around an ellipsis, and a count of
    what was skipped is what separates "seven checked, all clean" from
    "seven not checked at all".
    """
    payload = review.envelope(report.draft, "quotation", command)
    payload.update(
        {
            "quotes_total": len(report.checked),
            "found": len(report.of("found")),
            "absent": len(report.of("absent")),
            "unverifiable": len(report.of("unverifiable")),
            "quotes": [
                {
                    "id": finding_id(c.citekey, c.quote),
                    "citekey": c.citekey,
                    "verdict": c.verdict,
                    "tier": c.tier,
                    "pages": c.pages,
                    "reason": c.reason,
                }
                for c in report.checked
            ],
            "findings": findings(report),
        }
    )
    return payload


def run_text(draft: Path) -> str:
    """What a bare invocation prints. Split out so a caller -- and the
    test that pins two runs byte-identical -- can have it without
    capturing stdout."""
    report = build_report(draft)
    return _quotation_render.format_report(report, findings(report))


def build_parser(parser=None) -> argparse.ArgumentParser:
    """This aid's flags.

    `parser` is passed by chitragupta/review/__main__.py, which has
    already created the `quotation` subparser and needs the flags hung
    off *that* -- so they are declared once, here.
    """
    if parser is None:
        # A one-line description rather than this module's docstring, for
        # the reason chitragupta/corpus.py's DESCRIPTION gives (#152).
        parser = argparse.ArgumentParser(
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
    parser.add_argument(
        "--formats",
        default="md,tex,pdf",
        help="Additional formats to render beside the Markdown "
        "report (default: md,tex,pdf). The .md is always "
        "written -- it is the report; tex/pdf are renders "
        "of it, and need pandoc/pdflatex on PATH.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


def run(args: argparse.Namespace) -> int:
    """Dispatch already-parsed arguments, split from main() so
    chitragupta/review/__main__.py can hand over args parsed with this
    module's own build_parser().

    Exits 0 whatever it finds -- including on a draft where every quoted
    span is absent from its source. This aid is advisory, and a non-zero
    exit is how a gate speaks.
    """
    try:
        draft_path = review.require_reviewable(Path(args.draft))
    except (FileNotFoundError, config.OutsideContentDir) as exc:
        print(exc, file=sys.stderr)
        return 1

    report = build_report(draft_path)
    found = findings(report)

    if not (args.json or args.write):
        print(_quotation_render.format_report(report, found))
        return 0

    command = _command(draft_path, args.json, args.write)
    payload = quotation_payload(report, command)
    print(
        json.dumps(payload, indent=2)
        if args.json
        else _quotation_render.format_report(report, found)
    )

    if args.write:
        formats = [f.strip() for f in args.formats.split(",") if f.strip()]
        written = review.write(
            draft_path,
            "quotation",
            _quotation_render.render_markdown(report, command, found),
            formats,
        )
        written["json"] = review.write_json(draft_path, "quotation", payload)
        review.print_written(written, stream=sys.stderr if args.json else sys.stdout)
    return 0
