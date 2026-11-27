"""Citation provenance report: for each citation in a draft, what in the
cited source supports it, and where.

`citation_gate` answers "is this citekey real?" exactly; this answers
"does the cited paper say this?", which a drifted claim with a real
citekey passes. Not a gate: lexical matching cannot tell "the source
doesn't say this" from "it says it in other words", and a check blocking
on that would train people to work around it. Passages come from
`chitragupta/passages.py`'s ladder, which also decides when a source
reports a page rather than a quotation. Stdlib only.

Usage:
    python -m chitragupta.review provenance content/drafts/<slug>.md
    python -m chitragupta.review provenance <draft.md> --formats md,tex,pdf
"""

import argparse
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path

from chitragupta import citation_gate, config, ledger, review
from chitragupta.review import _emit
from chitragupta.passages import Passage, distinctive, source_passages
from chitragupta.review import _blocks, _citation_provenance_render, _claim_sentence
from chitragupta.help_format import ClickParser


@dataclass
class Finding:
    line: int
    citekey: str
    claim: str
    score: float
    passage: Passage | None = None
    note: str | None = None


@dataclass
class Report:
    draft: Path
    findings: list[Finding] = field(default_factory=list)
    unreadable: dict[str, str] = field(default_factory=dict)


def claims(draft_text: str, *, latex: bool = False) -> list[tuple[int, str, str]]:
    """(line number, citekey, the text carrying it) for every citation.

    The text is the citing sentence, table row, list item or heading: the
    block (`_blocks.spans`), then the sentence in it
    (`_claim_sentence.sentence_around`). The raw line was tried and yields
    fragments, since drafts are hard-wrapped; the whole paragraph was
    tried and scores all its citations identically.
    """
    lines = draft_text.splitlines()
    spans = _blocks.spans(lines)
    out = []
    for line_no, citekey in citation_gate.extract_citekeys(draft_text, latex=latex):
        block = next(
            (text for start, end, text in spans if start <= line_no <= end),
            lines[line_no - 1] if 0 < line_no <= len(lines) else "",
        )
        out.append((line_no, citekey, _claim_sentence.sentence_around(block, citekey)))
    return out


def score_claim(claim: str, passages: list[Passage]) -> tuple[float, Passage | None]:
    """Best lexical-overlap score over `passages`, and the passage that
    achieved it. Overlap rather than verbatim n-grams: a correct paraphrase
    keeps its content words but scores zero on `verbatim_check`'s exact
    runs, and paraphrase is the normal case.
    """
    wanted = distinctive(claim)
    if not wanted or not passages:
        return 0.0, None
    best_score, best = 0.0, None
    for passage in passages:
        hits = len(wanted & passage.words)
        score = hits / len(wanted)
        if score > best_score:
            best_score, best = score, passage
    return best_score, best


def build_report(draft_path: Path) -> Report:
    text = draft_path.read_text(encoding="utf-8")
    # The path, not `.name`: two topics' `survey.md` would otherwise share
    # a header, and the recorded command would not re-run.
    report = Report(draft=Path(draft_path))
    with ledger.reading() as con:
        cache: dict[str, list[Passage]] = {}
        for line_no, citekey, claim in claims(text, latex=citation_gate.is_latex(draft_path)):
            if citekey not in cache:
                passages, reason = source_passages(con, citekey)
                cache[citekey] = passages
                if reason:
                    report.unreadable[citekey] = reason
            score, passage = score_claim(claim, cache[citekey])
            note = report.unreadable.get(citekey)
            report.findings.append(
                Finding(
                    line=line_no,
                    citekey=citekey,
                    claim=claim,
                    score=score,
                    passage=passage,
                    note=note,
                )
            )
    # Worst first, so the report opens on what deserves attention.
    report.findings.sort(key=lambda f: (f.score, f.line))
    return report


def _command(draft_path: Path, as_json: bool) -> str:
    """The invocation recorded in the JSON envelope; `--formats` is left
    out, as it changes nothing in the payload.
    """
    parts = ["python", "-m", "chitragupta.review", "provenance", str(draft_path)]
    if as_json:
        parts += ["--json"]
    return shlex.join(parts)


# Shared with `run()` (#515/m-90), which passes its already-built `report`
# to avoid walking every source twice. It must be `build_report(draft_path)`
# for this same draft, built now: a foreign one would file a report on the
# wrong draft, the very shape this aid exists to catch.
def write_report(
    draft_path: Path, formats: list[str], report: "dict | None" = None
) -> dict[str, Path]:
    """Writes the report and returns {format: path} for what succeeded."""
    return review.write(
        draft_path,
        "provenance",
        _citation_provenance_render.render_markdown(
            build_report(draft_path) if report is None else report
        ),
        formats,
    )


def build_parser(parser=None) -> argparse.ArgumentParser:
    """This aid's flags, hung off the subparser `__main__` created."""
    if parser is None:
        parser = ClickParser(
            description="Report what in each cited source supports the claim citing it.",
        )
    parser.add_argument("draft", help="Markdown draft to check")
    _emit.add_formats(parser)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the findings as JSON instead of just the "
        "written-files summary. The .json sibling is filed "
        "beside the Markdown report either way.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


def run(args: argparse.Namespace) -> int:
    """Dispatch already-parsed arguments.

    The `.md` and `.json` are filed unconditionally; `--json` only decides
    stdout, moving the written-files summary to stderr so
    `provenance --json > findings.json` stays valid JSON.
    """
    try:
        draft_path = review.require_reviewable(Path(args.draft))
    except (FileNotFoundError, config.OutsideContentDir) as exc:
        print(exc, file=sys.stderr)
        return 1

    report = build_report(draft_path)
    written = write_report(draft_path, _emit.formats(args), report)
    payload = _citation_provenance_render.provenance_payload(
        report, _command(draft_path, args.json)
    )
    written["json"] = review.write_json(draft_path, "provenance", payload)

    _emit.announce(payload, written, as_json=args.json)
    return 0
