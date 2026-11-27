"""Whether tier 3 can run for a draft, and what it needs when it can.

The question asked before `overlap_embed.py` aligns anything: enrich
stack, embedded corpus, dossier, ledger (#516). `Scope`, `open_scope`
and `unavailable_reason` are re-exported there.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from chitragupta import config, dossier, install, ledger, overlap_chroma


@dataclass
class Scope:
    """Everything the tier needs: the dossier's section -> citekeys
    mapping, the chroma collection, and the ledger connection."""

    citekeys_by_section: dict[str, list[str]]
    collection: object
    connection: Any
    embedder: overlap_chroma.Embedder = field(default_factory=overlap_chroma.Embedder)

    # Every caller of `open_scope` owns what it opened; `unavailable_reason`
    # once leaked a connection per draft per report (#516/m-79).
    def close(self) -> None:
        """Release the ledger connection this scope holds."""
        self.connection.close()


def unavailable_reason(draft: Path) -> str | None:
    """Why tier 3 cannot run for `draft`, or `None` when it can.

    A sentence, since each way it is unavailable wants a different fix.
    Reported rather than swallowed: an unbuilt tier saying nothing looks
    like a built tier that found nothing.
    """
    scope, reason = open_scope(draft)
    if scope is not None:
        scope.close()
    return reason


def open_scope(draft: Path) -> tuple[Scope | None, str | None]:
    """`(scope, None)` when tier 3 can run for `draft`, `(None, reason)`
    when it cannot. Cheapest and most likely checks first: no dossier is
    decided by two file reads, before anything imports torch.
    """
    scoped, reason = _dossier_scope(draft)
    if scoped is None:
        return None, reason

    stack = overlap_chroma.optional_stack()
    if stack is None:
        return None, (
            "the enrichment layer is not installed; it adds the "
            "chromadb/sentence-transformers stack this tier embeds with. Run, "
            f"{install.enrich_remedy()}."
        )

    collection = overlap_chroma.built_collection(stack[0])
    if collection is None:
        return None, (
            f"{config.CHROMA_DIR} holds no embedded corpus for "
            f"{config.EMBEDDING_MODEL} -- run `python -m chitragupta.enrich` to build it"
        )
    # Read-only: `ledger.connect()` is a writer, and this review aid must
    # never take the write lock or create the ledger (#516/m-79). The
    # refusal's own text also covers a ledger that needs a sync.
    try:
        connection = ledger.read_connection()
    except ledger.NoLedger as exc:
        return None, " ".join(str(exc).split("\n"))
    return Scope(scoped, collection, connection), None


def _dossier_scope(draft: Path) -> tuple[dict[str, list[str]] | None, str | None]:
    """The draft's `sections.md` mapping, or why there isn't one.

    A draft outside `content/drafts/`, or a dossier with no citekeys, is
    not an error: most drafts on most hosts are in that state.
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
