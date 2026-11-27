"""The enrichment layer's view of the corpus: the bibliography, nothing else.

Every document comes from the ledger sync builds from the bib file, so
every document is citable and its citekey is its whole identity. Raw PDFs
outside the bib file are deliberately not indexed: they could never be
cited, and supporting them cost every stage a non-citable case. Catalogue
a paper, re-export and re-sync instead.
"""

from dataclasses import dataclass
from pathlib import Path

from chitragupta import ledger, ledger_paths


@dataclass
class CorpusDoc:
    # The citekey is the whole identity: the artefact stem and the cited
    # reference, never two fields that could differ (#57).
    # chitragupta/bib_reader.py's citekey_problem() guarantees it is a
    # usable filename.
    citekey: str
    title: str
    pdf_path: str | None
    text_path: str | None = None


# The one gate on the two host-path ledger columns (#821), stored relative
# to their roots (#966): no stage re-checks a `CorpusDoc` path, so
# confining them here covers every stage, including later ones.
def _as_str(path: Path | None) -> str | None:
    return None if path is None else str(path)


def build_corpus() -> list[CorpusDoc]:
    """Every ledger item, as the enrichment stages consume them."""
    with ledger.reading() as con:
        rows = ledger.all_items(con)

    return [
        CorpusDoc(
            citekey=item["citekey"],
            title=item["title"] or "Untitled",
            pdf_path=_as_str(ledger_paths.pdf_file(item["pdf_path"])),
            text_path=_as_str(ledger_paths.parsed_file(item["parsed_path"])),
        )
        for item in rows
    ]
