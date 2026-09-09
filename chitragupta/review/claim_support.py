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
from chitragupta.passages import Passage, distinctive, source_passages
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


# Passage labels that cannot be a premise. A section heading is a few
# words naming what follows; it asserts nothing, so it cannot support a
# claim -- and `_score_claim` takes `max()` over whatever it is given, so
# a heading that happens to score well is *reported* as the claim's best
# supporting passage. That is a wrong answer rather than a weak one,
# which is why this is a filter and not a ranking penalty (issue #719).
#
# Deliberately only `section_header`, though it is 6.9% of the corpus's
# passage units and `list_item` is another 15.9%: a bulleted line
# routinely carries a real assertion, and dropping those would lose
# genuine support with no measurement saying it does not. `table` and
# `formula` (0.7% each) stay for the same reason -- #632 added them on
# purpose, and a table cell can support a numeric claim.
#
# A passage whose `label` is None is *kept*. `passages._from_sidecar`
# leaves it None whenever the record has no `label` key, which is every
# passage from a sidecar written before labelling; dropping those would
# empty the premise set for those sources and silently move their
# citations from `scored` to `unscoreable`.
_NOT_A_PREMISE = frozenset({"section_header"})


def _quotable(passages: list[Passage]) -> list[Passage]:
    """Only passages that can serve as an entailment premise: real text,
    and not one of the labels `_NOT_A_PREMISE` names.

    Unlike provenance's lexical scorer, which can still compare against a
    page-level bag of words, an entailment model needs an actual premise.

    Both of this module's call sites go through here -- `build_report`'s
    "is there anything to score" gate and `_score_claim`'s own selection
    -- so the two cannot disagree about what the premise set is. That is
    what keeps `_score_claim`'s documented no-empty-result invariant true
    after the label filter was added.
    """
    return [p for p in passages if p.quotable and p.label not in _NOT_A_PREMISE]


# The cheap lexical scorer decides which premises the expensive model
# sees. That is the whole cost lever behind issue #693: `_score_claim`
# sends one pair per quotable passage, and docs/PERFORMANCE.md measures
# that at 725-887 pairs per citation -- a figure set by how finely the
# parse segmented the corpus, not by anything the draft controls.
#
# Ranked by the *same* overlap count `citation_provenance.score_claim`
# bands, deliberately: that scorer is already trusted to pick a claim's
# best passage for the neighbouring aid, and a second notion of lexical
# similarity here would be one more thing to disagree with it.
#
# `top_k` is None everywhere by default, so nothing below runs unless a
# caller asks for it. That is not timidity: a cap trades recall for
# speed, and the recall loss cannot be quantified until B9's rating
# instrument has labels (#757). The mechanism ships measured; the
# default stays the owner's call.
#
# Two properties the tests pin, because a cap lacking either is worse
# than no cap:
#
#   - It ranks what `_quotable` already kept, never the raw list, so a
#     filtered heading cannot occupy a slot a real premise needed.
#   - Ties resolve on document order (`sorted` is stable over an
#     already-ordered list), so a capped re-run over an unchanged draft
#     and corpus reports the same best passage. An arbitrary tie-break
#     would break R2's stable-identity rule for a whole class of
#     findings, because an all-stopword claim ties *every* premise at
#     zero overlap.
def _ranked(claim: str, passages: list[Passage], top_k: int | None) -> list[Passage]:
    """`passages`, cut to the `top_k` sharing most distinctive words with
    `claim` -- or unchanged when `top_k` is None."""
    if top_k is None or len(passages) <= top_k:
        return passages
    wanted = distinctive(claim)
    return sorted(passages, key=lambda p: -len(wanted & p.words))[:top_k]


# Callers pass every passage, not just the quotable ones, so the filter
# below is not redundant with the caller's own check -- it is what
# selects which passages the entailer actually sees. Only `build_report`
# calls this, and only after confirming `_quotable` is non-empty for the
# same `passages`, so unlike `citation_provenance.score_claim` (a public
# function with no such guarantee from its callers) this one does not
# re-guard against an empty result -- and its return type has no
# `| None` for the same reason: that would be defensive handling for a
# state this module's own call graph makes impossible.
#
# `_ranked` preserves that invariant, because it only ever shortens a
# non-empty list, and never to zero: `top_k` is at least 1 wherever it
# is not None, which `config._get_optional_positive_int` enforces at
# load rather than here.
def _score_claim(
    entailer, claim: str, passages: list[Passage], top_k: int | None = None
) -> tuple[float, Passage]:
    """Best-scoring quotable passage for `claim`, over at most `top_k`
    of them."""
    quotable = _ranked(claim, _quotable(passages), top_k)
    scores = entailer.score([(p.text, claim) for p in quotable])
    best_index = max(range(len(scores)), key=scores.__getitem__)
    return scores[best_index], quotable[best_index]


def build_report(draft_path: Path, entailer, top_k: int | None = None) -> Report:
    text = Path(draft_path).read_text(encoding="utf-8")
    report = Report(draft=Path(draft_path))
    with ledger.connection() as con:
        cache: dict[str, tuple[list[Passage], str | None]] = {}
        for line_no, citekey, claim in citation_provenance.claims(text):
            if citekey not in cache:
                cache[citekey] = source_passages(con, citekey)
            passages, reason = cache[citekey]
            if not _quotable(passages):
                # Two different absences, and saying "page-level only"
                # for the second would be false: a source can have real
                # readable text and still offer no premise, if every
                # readable passage it has is a heading.
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


def finding_id(citekey: str, claim: str) -> str:
    """A finding's identity, stable across runs (R2) -- keyed on the
    same (citekey, claim) pair _citation_provenance_render.finding_id uses,
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

    # Resolved here rather than defaulted inside `build_report`, so that
    # the config is what the *CLI* obeys while a caller -- notably
    # bench/bench_support_topk.py, which sweeps k -- pins it per arm at
    # the call site instead of mutating a module constant mid-run.
    report = build_report(draft_path, entailer, config.SUPPORT_PREMISE_TOPK)
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
