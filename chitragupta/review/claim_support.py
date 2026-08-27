"""Claim-support report: does the cited source actually entail the
claim citing it -- scored by a real NLI entailment model, never
lexical overlap.

`chitragupta/review/citation_provenance.py` asks a related question
with a lexical scorer and answers it cheaply; this aid exists because
the roadmap's own argument for why that is not enough: a paraphrase
that subtly misstates a paper passes the gate (real citekey), passes
the verbatim scan (wording now differs), and passes provenance (the
source remains topically related). Only reading whether the source's
own words actually entail the claim catches that.

Reuses citation_provenance.claims() for extraction (line, citekey,
claim) rather than re-parsing -- the same function
bench/bench_paraphrase_hunt.py already reuses for the same reason --
and passages.source_passages() for the source text. Only the scorer
differs: chitragupta/entailment.py's Entailer, injected rather than
imported here, so this module's own logic is testable with no model
anywhere (chitragupta/entailment.py's own tests cover the model seam).

Ranked, never banded. Unlike provenance's "no support found / weak /
supported" bands, this aid publishes a bare score. Retrieval already
selected these passages by similarity, so the discriminator here is
weak in the same way docs/PLAGIARISM-DESIGN.md records for tier 3 --
and a band would claim a precision this corpus does not support. See
docs/REVIEW.md's limits section.

**Surfaced, never repaired unattended, and permanently.**
docs/AUTO-IMPROVEMENT-RATIONALE.md settles this by mechanism, not
policy: every check this loop owns returns clean on its worst output,
which is exactly the paraphrase case above. An unattended reviser
chasing a higher score would make a claim look supported without
making it supported.

Needs the `enrich` extra (chitragupta/entailment.py). Advisory like
the other eight -- exit 0 whatever it finds, no lock, no draft blocked.

Usage:
    python -m chitragupta.review support content/drafts/<slug>.md
    python -m chitragupta.review support <draft.md> --json --write
"""

import argparse
import hashlib
import json
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path

from chitragupta import config, entailment, ledger, review
from chitragupta.passages import Passage, source_passages
from chitragupta.review import _claim_support_render as _render
from chitragupta.review import citation_provenance


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
    unscoreable: dict[str, str] = field(default_factory=dict)


def _quotable(passages: list[Passage]) -> list[Passage]:
    """Only passages with real text -- an entailment model needs an
    actual premise, unlike provenance's lexical scorer, which can
    still compare against a page-level bag of words."""
    return [p for p in passages if p.quotable]


def _score_claim(entailer, claim: str, passages: list[Passage]) -> tuple[float, Passage]:
    """Best-scoring quotable passage for `claim`.

    Callers pass every passage, not just the quotable ones, so the
    filter below is not redundant with the caller's own check -- it is
    what selects which passages the entailer actually sees. Only
    `build_report` calls this, and only after confirming `_quotable`
    is non-empty for the same `passages`, so unlike
    `citation_provenance.score_claim` (a public function with no such
    guarantee from its callers) this one does not re-guard against an
    empty result -- and its return type has no `| None` for the same
    reason: that would be defensive handling for a state this module's
    own call graph makes impossible."""
    quotable = _quotable(passages)
    scores = entailer.score([(p.text, claim) for p in quotable])
    best_index = max(range(len(scores)), key=scores.__getitem__)
    return scores[best_index], quotable[best_index]


def build_report(draft_path: Path, entailer) -> Report:
    text = Path(draft_path).read_text(encoding="utf-8")
    report = Report(draft=Path(draft_path))
    with ledger.connection() as con:
        cache: dict[str, tuple[list[Passage], str | None]] = {}
        for line_no, citekey, claim in citation_provenance.claims(text):
            if citekey not in cache:
                cache[citekey] = source_passages(con, citekey)
            passages, reason = cache[citekey]
            if not _quotable(passages):
                report.unscoreable[citekey] = reason or (
                    "the source's passages carry no readable text to score "
                    "against (page-level only)"
                )
                score, passage, note = 0.0, None, report.unscoreable[citekey]
            else:
                score, passage = _score_claim(entailer, claim, passages)
                note = None
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
    report.findings.sort(key=lambda f: (f.score, f.line))
    return report


def finding_id(citekey: str, claim: str) -> str:
    """A finding's identity, stable across runs (R2) -- keyed on the
    same (citekey, claim) pair citation_provenance.finding_id uses,
    because this is the same underlying question asked by a different
    scorer. Defined locally rather than imported: every aid in this
    layer owns its own finding_id, even when the formula matches."""
    digest = hashlib.sha256(f"{citekey}\x00{claim}".encode())
    return digest.hexdigest()[:12]


def findings(report: Report) -> list[dict]:
    """One object per citation, worst-scoring first -- already the
    Report's own sort order, so this only shapes the dicts."""
    return [
        {
            "id": finding_id(f.citekey, f.claim),
            "line": f.line,
            "citekey": f.citekey,
            "claim": f.claim,
            "score": f.score,
            "note": f.note,
        }
        for f in report.findings
    ]


def _command(draft: Path, as_json: bool, write: bool) -> str:
    """The invocation recorded in both the Markdown header and the JSON
    envelope -- `--json`/`--write` in full when given, the same rule
    `uncited_prose._command` states for its own `--genre`."""
    parts = ["python", "-m", "chitragupta.review", "support", str(draft)]
    if as_json:
        parts += ["--json"]
    if write:
        parts += ["--write"]
    return shlex.join(parts)


def support_payload(report: Report, command: str) -> dict:
    """The same findings the report prints, as data -- an additional
    serialisation, never a second computation.

    `"scored"` counts findings the entailer actually scored (`note is
    None`), not `len(report.findings) - len(report.unscoreable)`. The
    two differ when a single unscoreable citekey is cited more than
    once: `report.unscoreable` is keyed by citekey, so it gains one
    entry no matter how many findings that citekey produces, while
    `build_report` still gives every one of those findings its own
    `note`. Counting the naive way would let "scored" overcount by the
    number of repeat citations of an already-unscoreable citekey --
    inconsistent with `_claim_support_render._scored`, which every
    rendered report already uses for the same number. Matching that
    keeps the JSON and the text report agreeing on what "scored"
    means.

    Deliberately different units, not a second inconsistency:
    `"scored"` counts findings (one per citation), `"unscoreable"`
    counts citekeys (one per source), the same split
    `_claim_support_render._summary` already prints -- a repeated
    citation of one bad citekey is one line under "Not scored" but two
    lines under Findings, in the JSON exactly as in the rendered
    report."""
    payload = review.envelope(report.draft, "support", command)
    payload.update(
        {
            "scored": len([f for f in report.findings if f.note is None]),
            "unscoreable": dict(sorted(report.unscoreable.items())),
            "findings": findings(report),
        }
    )
    return payload


def build_parser(parser=None) -> argparse.ArgumentParser:
    if parser is None:
        # A one-line description rather than this module's docstring, for
        # the reason chitragupta/corpus.py's DESCRIPTION gives (#152).
        parser = argparse.ArgumentParser(
            description="Does the cited source actually entail the claim citing it?",
        )
    parser.add_argument("draft", help="Path to the draft to check")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the findings as JSON instead of as text. "
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
        help="Additional formats to render beside the Markdown report "
        "(default: md,tex,pdf). The .md is always written -- it is the "
        "report; tex/pdf are renders of it, and need pandoc/pdflatex "
        "on PATH.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


def run(args: argparse.Namespace) -> int:
    """Dispatch already-parsed arguments, split from main() so
    chitragupta/review/__main__.py can hand over args parsed with this
    module's own build_parser().

    Advisory: exits 0 whatever it finds, including when the enrichment
    layer is not installed at all -- an unbuilt optional check is not a
    failure, matching how tier 3 of the verbatim scan degrades."""
    try:
        draft_path = review.require_reviewable(Path(args.draft))
    except (FileNotFoundError, config.OutsideContentDir) as exc:
        print(exc, file=sys.stderr)
        return 1

    entailer, reason = entailment.open_entailer()
    if entailer is None:
        print(f"support: not run -- {reason}", file=sys.stderr)
        return 0

    report = build_report(draft_path, entailer)
    found = findings(report)

    if not (args.json or args.write):
        print(_render.format_report(report, found))
        return 0

    command = _command(draft_path, args.json, args.write)
    payload = support_payload(report, command)
    print(json.dumps(payload, indent=2) if args.json else _render.format_report(report, found))

    if args.write:
        formats = [f.strip() for f in args.formats.split(",") if f.strip()]
        written = review.write(
            draft_path, "support", _render.render_markdown(report, command, found), formats
        )
        written["json"] = review.write_json(draft_path, "support", payload)
        review.print_written(written, stream=sys.stderr if args.json else sys.stdout)
    return 0
