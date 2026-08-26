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
the other six -- exit 0 whatever it finds, no lock, no draft blocked.

Usage:
    python -m chitragupta.review support content/drafts/<slug>.md
    python -m chitragupta.review support <draft.md> --json --write
"""

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from chitragupta import ledger
from chitragupta.passages import Passage, source_passages
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


def _score_claim(
    entailer, claim: str, passages: list[Passage]
) -> tuple[float, Passage]:
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
                Finding(line=line_no, citekey=citekey, claim=claim, score=score,
                        passage=passage, note=note)
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
