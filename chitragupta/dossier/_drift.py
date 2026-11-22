"""Whether a dossier's kept evidence and rejections still match what's
currently in the corpus -- the data model and the computation, not its
CLI report.

Split out of chitragupta/dossier.py (#219), and split again from
`_drift_report` (the print/render formatting that used to sit beside
this in one CLI handler) once it was clear the combined module would
not fit under this project's 250-code-line cap on its own. `Corpus`,
`Candidate` and `Reconsider` exist as their own dataclasses rather than
plain tuples because `drift()` builds up several of each per dossier
and a caller reading `candidate.reason` is clearer than an index into a
tuple it has to remember the shape of.

`status <draft>` answers "did the corpus move under this one draft?".
`drift`/`drift_all` answer the other half: which drafts on this machine
have gone stale, and what specifically about each. Read-only, lock-free,
and never fatal -- a missing ledger, a missing dossier file and an
unparsable row are all things to report, not to fail on.
"""

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
    SECTIONS_MD,
    _corpus_rows,
    all_dossiers,
    digest,
    dossier_name,
    draft_relpath,
    find_draft,
    recorded_corpus,
)
from chitragupta.dossier._renames import renamed_in
from chitragupta.dossier._retrieval import recorded_queries_with_collection

# Re-exported: callers and tests reach the shared snapshot through `_drift`.
from chitragupta.dossier._drift_corpus import CANDIDATE_K, Corpus  # noqa: F401


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
        # `reconsider` is deliberately not part of this. A rejection that
        # still matches its query was true before the corpus moved and
        # will be true on every sweep after it -- counting it as drift
        # would mark every dossier that ever declined a paper permanently
        # stale, which is exactly the signal this command exists to give.
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

    Two findings, and they are not the same kind of thing. A **missing**
    citekey is a defect: the draft cites a paper the corpus no longer
    has, and something has to be swapped or dropped. A **candidate** is
    an opportunity: a paper the corpus has gained that this draft's own
    recorded queries would have put in front of the writer. The first is
    work; the second is a decision, and drift is still not itself a
    reason to redraft.

    Pass `corpus` to share one ledger read and one index across a sweep;
    omit it and this reads the ledger for itself.
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

    # The ledger *plus* what this dossier declares by giving a citekey its
    # own `evidence.md` heading. The ledger alone cannot answer "which
    # cited papers left the corpus?" for a separator-free key, because a
    # key that left it is not in it -- see `declared_citekeys` (#506/M-28).
    known = corpus.citekeys | declared_citekeys(dossier) | set(corpus.renames)

    sections_citing = section_citekeys(dossier, known)
    cited = _citekeys_in(dossier, CITED_FILES, known)
    # Only what the dossier *declares* can go missing (#1117): an
    # `evidence.md` heading or a `sections.md` cell. `cited` also matches
    # backticked prose, and the skill's own name in the evidence preamble
    # (`tutorial-writer`) was reported as a citation that left the ledger.
    declared = declared_citekeys(dossier) | set(sections_citing)
    # A renamed key is not missing: sync recorded its replacement, and
    # `dossier apply-renames` swaps it without a search (plans/1211).
    texts = [p.read_text(encoding="utf-8") for p in _texts_of(report.draft, dossier)]
    report.renamed = renamed_in(texts, corpus.renames, corpus.citekeys, sections_citing)
    report.missing = {
        citekey: sections_citing.get(citekey, [])
        for citekey in sorted(declared - corpus.citekeys - set(report.renamed))
    }

    # Everything the dossier ever weighed -- rejections included, which is
    # the point. Re-offering a paper the draft already turned down as if
    # it were new would cost exactly the re-judging that `rejected.md`
    # exists to prevent.
    mentioned = cited_citekeys(dossier, known)
    report.unconsidered = len(corpus.citekeys - mentioned)

    declined = rejected_reasons(dossier)
    queries, report.unresolved_collections = corpus.resolve(
        recorded_queries_with_collection(dossier)
    )
    matched = sorted(corpus.matches(queries).items())
    report.candidates = [
        Candidate(citekey, corpus.titles.get(citekey, ""), queries)
        for citekey, queries in matched
        if citekey not in mentioned
    ]
    # A declined paper its queries still reach, reported separately and
    # with the reason. `cited` wins the tie: a citekey that is both cited
    # and listed as rejected is a stale `rejected.md` row, not an open
    # question, and offering it back would send a reviser to re-decide
    # something the draft already acts on.
    report.reconsider = [
        Reconsider(citekey, corpus.titles.get(citekey, ""), queries, declined[citekey])
        for citekey, queries in matched
        if citekey in declined and citekey not in cited
    ]
    return report


def _texts_of(draft: Path | None, dossier: Path) -> list[Path]:
    """The draft and the dossier files a renamed key can be cited in."""
    paths = [dossier / name for name in (EVIDENCE_MD, SECTIONS_MD)]
    return [p for p in ([draft] if draft else []) + paths if p.is_file()]


def drift_all() -> list[Drift]:
    """One drift report per dossier on this machine, nearest-first."""
    rows = _corpus_rows()
    corpus = Corpus(rows) if rows is not None else None
    return [drift(path, corpus) for path in all_dossiers()]
