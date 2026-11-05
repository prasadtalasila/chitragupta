"""A book fragment's index entries (#1168): `assets/pandoc/index_terms.lua`.

`draft render --fragment --index-terms <index-terms.json>` places one
`\\index{<id>}` per term per chapter and writes `<unit>.index.json`
beside the fragment, which `registry index` reads once the book is
typeset (chitragupta/registry/_index_finish.py). The term table is
`registry build --index`'s (chitragupta/registry/_index_terms.py).

Keyed on the term table being named, not on `--fragment`: a thesis
fragment and a standalone render get no `\\index` at all.
"""

from pathlib import Path

from chitragupta import config

FILTER = config.shipped("assets", "pandoc", "index_terms.lua")


def sidecar_path(out_dir: Path, unit_id: str) -> Path:
    """Where a chapter's sidecar is written: beside its fragment."""
    return Path(out_dir) / f"{unit_id}.index.json"


def pandoc_args(input_path: Path, terms: "Path | None", out_dir: Path) -> list[str]:
    """The argv that indexes `input_path`, or none without a term table.

    The unit id is the draft's own stem, not the temporary copy pandoc
    reads: a draft's stem is its outline id (book-assembler step 4)."""
    if terms is None:
        return []
    unit_id = Path(input_path).stem
    return [
        "--lua-filter",
        str(FILTER),
        "--metadata",
        f"chitragupta-index-terms={Path(terms).resolve()}",
        "--metadata",
        f"chitragupta-index-unit={unit_id}",
        "--metadata",
        f"chitragupta-index-sidecar={sidecar_path(out_dir, unit_id).resolve()}",
    ]
