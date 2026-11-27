"""Whether a dossier's kept evidence and rejections still match what's
currently in the corpus -- the data model and the computation, not its
CLI report.

`status <draft>` answers "did the corpus move under this draft?";
`drift`/`drift_all` answer which drafts have gone stale and how.
Read-only, lock-free and never fatal: missing or unparsable inputs are
reported, not failed on.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from chitragupta.dossier._citekeys import (
    CITED_FILES,
    _citekeys_in,
    cited_citekeys,
    declared_citekeys,
    rejected_reasons,
    section_citekeys,
)
from chitragupta.dossier import (
    EVIDENCE_MD,
    SCOPE_MD,
    SECTIONS_MD,
    _corpus_rows,
    all_dossiers,
    digest,
    dossier_name,
    draft_relpath,
    find_draft,
    recorded_corpus,
)
from chitragupta.dossier._renames import cited as mentioned_in
from chitragupta.dossier._renames import renamed_in
from chitragupta.dossier._retrieval import recorded_queries_with_collection

from chitragupta.dossier._drift_corpus import Corpus


@dataclass
class Candidate:
    """A paper in the ledger that this dossier has never weighed, which
    one of the dossier's own recorded queries would have surfaced."""

    citekey: str
    title: str
    queries: list[str]


@dataclass
class Reconsider:
    """A paper this draft read and declined, which its queries still
    reach -- carried with the reason it was declined."""

    citekey: str
    title: str
    queries: list[str]
    reason: str


@dataclass
class Drift:
    dossier: Path
    name: str
    draft: Path | None
    corpus_available: bool = False
    recorded: tuple[int, str] | None = None
    current: tuple[int, str] | None = None
    missing: dict[str, list[str]] = field(default_factory=dict)
    candidates: list[Candidate] = field(default_factory=list)
    reconsider: list[Reconsider] = field(default_factory=list)
    unconsidered: int = 0
    unresolved_collections: list[str] = field(default_factory=list)
    renamed: dict[str, dict] = field(default_factory=dict)

    @property
    def drifted(self) -> bool:
        return bool(self.recorded and self.current and self.recorded[1] != self.current[1])

    @property
    def clean(self) -> bool:
        # `reconsider` is deliberately excluded: a still-matching
        # rejection would mark every dossier that ever declined a paper
        # permanently stale.
        return not (self.missing or self.candidates or self.unresolved_collections or self.renamed)

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "dossier": draft_relpath(self.dossier),
            "draft": draft_relpath(self.draft) if self.draft else None,
            "corpus_available": self.corpus_available,
            "recorded": list(self.recorded) if self.recorded else None,
            "current": list(self.current) if self.current else None,
            "drifted": self.drifted,
            "missing": self.missing,
            "unresolved_collections": self.unresolved_collections,
            "renamed": self.renamed,
            "candidates": [
                {"citekey": c.citekey, "title": c.title, "queries": c.queries}
                for c in self.candidates
            ],
            "reconsider": [
                {"citekey": r.citekey, "title": r.title, "queries": r.queries, "reason": r.reason}
                for r in self.reconsider
            ],
            "unconsidered": self.unconsidered,
        }


def drift(dossier: Path, corpus: "Corpus | None" = None) -> Drift:
    """What has gone stale about one dossier since its draft was written.

    A **missing** citekey is a defect to fix; a **candidate** is an
    opportunity to decide on, and not itself a reason to redraft. Pass
    `corpus` to share one ledger read across a sweep.
    """
    dossier = Path(dossier)
    if corpus is None:
        rows = _corpus_rows()
        corpus = Corpus(rows) if rows is not None else None

    report = Drift(
        dossier=dossier,
        name=dossier_name(dossier),
        draft=find_draft(dossier),
        recorded=recorded_corpus(dossier),
    )
    if corpus is None:
        return report

    report.corpus_available = True
    report.current = (len(corpus.citekeys), digest(corpus.citekeys))

    # Plus declared `evidence.md` headings, or a departed separator-free
    # key would be invisible (#506/M-28).
    known = corpus.citekeys | declared_citekeys(dossier) | set(corpus.renames)

    sections_citing = section_citekeys(dossier, known)
    cited = _citekeys_in(dossier, CITED_FILES, known)
    # Only what the dossier *declares* can go missing (#1117): `cited`
    # also matches backticked prose such as a skill's own name.
    declared = declared_citekeys(dossier) | set(sections_citing)
    _missing_and_renamed(report, corpus, declared, sections_citing)

    # Rejections included, so a declined paper is not re-offered as new.
    mentioned = cited_citekeys(dossier, known)
    report.unconsidered = len(corpus.citekeys - mentioned)

    declined = rejected_reasons(dossier)
    queries, report.unresolved_collections = corpus.resolve(
        recorded_queries_with_collection(dossier), _scope_collection(dossier)
    )
    matched = sorted(corpus.matches(queries).items())
    report.candidates = [
        Candidate(citekey, corpus.titles.get(citekey, ""), queries)
        for citekey, queries in matched
        if citekey not in mentioned
    ]
    # A declined paper its queries still reach, with the reason. `cited`
    # wins a tie: cited-and-rejected is a stale `rejected.md` row.
    report.reconsider = [
        Reconsider(citekey, corpus.titles.get(citekey, ""), queries, declined[citekey])
        for citekey, queries in matched
        if citekey in declined and citekey not in cited
    ]
    return report


def _missing_and_renamed(report: Drift, corpus: Corpus, declared, sections_citing) -> None:
    """Fill `report.renamed` and `report.missing`.

    A key sync found stale, or one only the draft's text cites, is
    missing. A renamed key is not: `dossier apply-renames` swaps it
    without a search (plans/1211).
    """
    live = corpus.citekeys - corpus.stale
    texts = [p.read_text(encoding="utf-8") for p in _texts_of(report.draft, report.dossier)]
    report.renamed = renamed_in(texts, corpus.renames, live, sections_citing)
    gone = (declared - live) | set(mentioned_in(texts, corpus.stale))
    report.missing = {
        citekey: sections_citing.get(citekey, []) for citekey in sorted(gone - set(report.renamed))
    }


def _scope_collection(dossier: Path) -> str:
    """The collection `scope.md` records, or "" for none or the whole corpus."""
    scope = dossier / SCOPE_MD
    text = scope.read_text(encoding="utf-8") if scope.is_file() else ""
    match = re.search(r"^- collection:\s*(.*)$", text, re.MULTILINE)
    value = match.group(1).strip() if match else ""
    return "" if value.startswith("(") else value


def _texts_of(draft: Path | None, dossier: Path) -> list[Path]:
    paths = [dossier / name for name in (EVIDENCE_MD, SECTIONS_MD)]
    return [p for p in ([draft] if draft else []) + paths if p.is_file()]


def drift_all() -> list[Drift]:
    """One drift report per dossier on this machine, nearest-first."""
    rows = _corpus_rows()
    corpus = Corpus(rows) if rows is not None else None
    return [drift(path, corpus) for path in all_dossiers()]
