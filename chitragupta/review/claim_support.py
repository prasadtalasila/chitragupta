"""Claim-support report: does the cited source actually entail the
claim citing it -- scored by a real NLI entailment model, never
lexical overlap.

A subtly misstated paraphrase passes the gate, the verbatim scan and
lexical provenance; only entailment catches it. Reuses
citation_provenance.claims() and passages.source_passages(); the
Entailer (chitragupta/entailment.py) is injected so this logic tests with
no model.

Ranked, never banded: retrieval already chose these passages by
similarity, so a band would claim precision the corpus does not support
(docs/REVIEW.md). Surfaced, never repaired unattended: a reviser chasing
the score would make a claim look supported without making it so
(docs/AUTO-IMPROVEMENT-RATIONALE.md). Needs the `enrich` extra; exit 0
whatever it finds.

Usage:
    python -m chitragupta.review support content/drafts/<slug>.md
    python -m chitragupta.review support <draft.md> --json --write
"""

import argparse
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path

from chitragupta import citation_gate, config, entailment, ledger, review
from chitragupta.review import _emit
from chitragupta.passages import Passage, distinctive, source_passages
from chitragupta.review import _claim_support_render as _render
from chitragupta.review import citation_provenance
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
    unscoreable: dict[str, str] = field(default_factory=dict)


# A heading asserts nothing, yet `_score_claim`'s max() would report one
# that scores well as the best support: a filter, not a penalty (#719).
# `list_item`, `table` and `formula` stay because they can carry real
# assertions. A None label (pre-labelling sidecar) is kept, or those
# sources would silently move to `unscoreable`.
_NOT_A_PREMISE = frozenset({"section_header"})


def _quotable(passages: list[Passage]) -> list[Passage]:
    """Passages usable as an entailment premise: real text, not a label
    `_NOT_A_PREMISE` names. Both call sites use this, so the "anything to
    score" gate and `_score_claim` agree on the premise set.
    """
    return [p for p in passages if p.quotable and p.label not in _NOT_A_PREMISE]


# A lexical pre-rank of the premises the model sees (#693: 725-887 pairs
# per citation, docs/PERFORMANCE.md). Off by default and should stay off:
# swept k = 8..128 it damaged the report at every k (bench/RESULTS.md,
# 2026-09-09). Lexical pre-ranking is ruled out, not a cap; a semantic
# pre-rank is untested. Kept to make that experiment cheap. Pinned: it
# ranks only what `_quotable` kept, and ties keep document order so a
# re-run reports the same best passage (R2).
def _ranked(claim: str, passages: list[Passage], top_k: int | None) -> list[Passage]:
    """`passages`, cut to the `top_k` sharing most distinctive words with
    `claim` -- or unchanged when `top_k` is None."""
    if top_k is None or len(passages) <= top_k:
        return passages
    wanted = distinctive(claim)
    return sorted(passages, key=lambda p: -len(wanted & p.words))[:top_k]


# Only called after `build_report` confirmed `_quotable` is non-empty, and
# `_ranked` never shortens to zero (top_k >= 1 is enforced at config load),
# so no empty-result guard and no `| None`.
def _score_claim(
    entailer, claim: str, passages: list[Passage], top_k: int | None = None
) -> tuple[float, Passage]:
    """Best-scoring quotable passage for `claim`, over at most `top_k`."""
    quotable = _ranked(claim, _quotable(passages), top_k)
    scores = entailer.score([(p.text, claim) for p in quotable])
    best_index = max(range(len(scores)), key=scores.__getitem__)
    return scores[best_index], quotable[best_index]


def build_report(draft_path: Path, entailer, top_k: int | None = None) -> Report:
    text = Path(draft_path).read_text(encoding="utf-8")
    report = Report(draft=Path(draft_path))
    with ledger.reading() as con:
        cache: dict[str, tuple[list[Passage], str | None]] = {}
        latex = citation_gate.is_latex(draft_path)
        for line_no, citekey, claim in citation_provenance.claims(text, latex=latex):
            if citekey not in cache:
                cache[citekey] = source_passages(con, citekey)
            passages, reason = cache[citekey]
            if not _quotable(passages):
                # A source with readable text can still offer no premise
                # if every readable passage is a heading.
                report.unscoreable[citekey] = reason or (
                    "the source's only readable passages are section headings, "
                    "which assert nothing to score a claim against"
                    if any(p.quotable for p in passages)
                    else "the source's passages carry no readable text to score "
                    "against (page-level only)"
                )
                score, passage, note = 0.0, None, report.unscoreable[citekey]
            else:
                score, passage = _score_claim(entailer, claim, passages, top_k)
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


def _command(draft: Path, as_json: bool, write: bool) -> str:
    """The invocation recorded in the Markdown header and JSON envelope."""
    parts = ["python", "-m", "chitragupta.review", "support", str(draft)]
    if as_json:
        parts += ["--json"]
    if write:
        parts += ["--write"]
    return shlex.join(parts)


def build_parser(parser=None) -> argparse.ArgumentParser:
    if parser is None:
        # Not this module's docstring (#152; see chitragupta/corpus.py).
        parser = ClickParser(
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
    _emit.add_formats(parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


def _scored(draft_path: Path) -> Report | None:
    """The scored report, or None once "not run" is on stderr (entailer
    not installed or its model will not load)."""
    entailer, reason = entailment.open_entailer()
    if entailer is None:
        print(f"support: not run -- {reason}", file=sys.stderr)
        return None
    # Resolved here so the CLI obeys config while bench/bench_support_topk.py
    # pins k per arm at the call site.
    try:
        return build_report(draft_path, entailer, config.SUPPORT_PREMISE_TOPK)
    except entailment.EntailmentUnavailable as unavailable:
        # The model loads at the first claim scored (#977).
        print(f"support: not run -- {unavailable}", file=sys.stderr)
        return None


def run(args: argparse.Namespace) -> int:
    """Dispatch already-parsed arguments (for __main__).

    Exits 0 even when the enrichment layer is not installed: an unbuilt
    optional check is not a failure."""
    try:
        draft_path = review.require_reviewable(Path(args.draft))
    except (FileNotFoundError, config.OutsideContentDir) as exc:
        print(exc, file=sys.stderr)
        return 1

    report = _scored(draft_path)
    if report is None:
        return 0
    found = _render.findings(report)

    return _emit.emit(
        draft_path,
        "support",
        args,
        text=lambda: _render.format_report(report, found),
        command=lambda: _command(draft_path, args.json, args.write),
        payload=lambda command: _render.support_payload(report, command),
        markdown=lambda command: _render.render_markdown(report, command, found),
    )
