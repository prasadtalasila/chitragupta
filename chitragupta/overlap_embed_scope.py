"""Whether tier 3 can run for a draft, and what it needs when it can.

Split from `chitragupta/overlap_embed.py` (#516). That module is the tier
itself -- the alignment, the per-section cap, the report -- and this is
the question asked *before* any of it: is the enrichment stack installed,
is there an embedded corpus, does this draft have a dossier that scopes
it, and is there a ledger to read source passages from. Four different
"no"s wanting four different fixes, and none of them about alignment.

The split was owed: `overlap_embed.py` sat at 249 of
docs/CODE-STANDARDS.md's 250-line C2 ceiling, so #516's read-only ledger
guard could not land without it.

The dependency runs one way, `overlap_embed` -> here. `Scope`,
`open_scope` and `unavailable_reason` are re-exported there so no caller
changes.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from chitragupta import config, dossier, overlap_chroma
from chitragupta.overlap_index_ledger import _ledger_connect_ro


@dataclass
class Scope:
    """Everything the tier needs to run, once it is established that it
    can: the dossier's section -> citekeys mapping, the chroma collection
    to shortlist against, and the ledger connection source passages come
    from."""

    citekeys_by_section: dict[str, list[str]]
    collection: object
    connection: Any
    embedder: overlap_chroma.Embedder = field(default_factory=overlap_chroma.Embedder)

    # Every caller of `open_scope` owns what it opened (#516/m-79).
    # `unavailable_reason` opens a scope purely to read its *reason* and
    # used to drop the rest on the floor, leaking a connection per call --
    # and it is called once per draft per report.
    def close(self) -> None:
        """Release the ledger connection this scope holds."""
        self.connection.close()


def unavailable_reason(draft: Path) -> str | None:
    """Why tier 3 cannot run for `draft`, or `None` when it can.

    A sentence, not a code -- it is printed to a person mid-review, and
    the five ways this tier is unavailable want five different fixes
    (install the enrich group, embed the corpus, parse with Docling,
    write the draft's dossier, or sync the corpus -- the last one added
    by #516/m-79, which stopped this tier *creating* the ledger it is
    supposed to be reading). Reported rather than swallowed: an
    unbuilt tier that says nothing and a built tier that found nothing
    look identical in a report, and only one of them means the draft was
    checked.
    """
    scope, reason = open_scope(draft)
    if scope is not None:
        scope.close()
    return reason


def open_scope(draft: Path) -> tuple[Scope | None, str | None]:
    """`(scope, None)` when tier 3 can run for `draft`, `(None, reason)`
    when it cannot.

    Ordered cheapest-first, and the order is also most-likely-first: a
    host that has never run the drafting pipeline has no dossier, which
    is decided by two file reads before anything imports torch.
    """
    scoped, reason = _dossier_scope(draft)
    if scoped is None:
        return None, reason

    stack = overlap_chroma.optional_stack()
    if stack is None:
        return None, (
            "the enrichment layer is not installed -- `poetry install --with enrich` "
            "adds the chromadb/sentence-transformers stack this tier embeds with"
        )

    collection = overlap_chroma.built_collection(stack[0])
    if collection is None:
        return None, (
            f"{config.CHROMA_DIR} holds no embedded corpus for "
            f"{config.EMBEDDING_MODEL} -- run `python -m chitragupta.enrich` to build it"
        )
    # Read-only, and this tier's whole layer says so: `ledger.connect()`
    # runs the schema, the migrations and a commit -- a *writer*, opened
    # inside a review aid whose contract is that it never takes the write
    # lock (#516/m-79). A scan racing a `corpus sync` could contend for
    # it, and on a fresh checkout this tier would create the ledger it is
    # supposed to be merely reading.
    connection = _ledger_connect_ro()
    if connection is None:
        return (
            None,
            f"{config.LEDGER_PATH} does not exist -- run `python -m chitragupta.corpus sync`",
        )
    return Scope(scoped, collection, connection), None


def _dossier_scope(draft: Path) -> tuple[dict[str, list[str]] | None, str | None]:
    """The draft's `sections.md` mapping, or why there isn't one.

    A draft outside `content/drafts/` has no dossier path at all
    (`dossier_dir` raises rather than guessing), and one whose dossier
    records no citekeys has nothing to scope to. Both are the same
    outcome for this tier and neither is an error: most drafts on most
    hosts are in exactly that state.
    """
    try:
        directory = dossier.dossier_dir(Path(draft))
    except dossier.DossierError:
        return None, (
            "the draft is not under content/drafts/, so it has no dossier -- "
            "this tier compares each section against the citekeys its dossier records"
        )
    mapping = {
        title: keys for title, keys in dossier.citekeys_by_section(directory).items() if keys
    }
    if not mapping:
        return None, (
            f"{directory}/sections.md records no citekeys for any section -- "
            "this tier compares each section against the sources it was written from, "
            "and never against the whole corpus (docs/PLAGIARISM-DESIGN.md)"
        )
    return mapping, None
