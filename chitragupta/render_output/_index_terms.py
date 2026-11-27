"""A book fragment's index entries (#1168): `assets/pandoc/index_terms.lua`.

Places one `\\index{<id>}` per term per chapter and writes `<unit>.index.json`
for `registry index`. Keyed on a term table being named, not on `--fragment`.
"""

from pathlib import Path

from chitragupta import config

FILTER = config.shipped("assets", "pandoc", "index_terms.lua")


def sidecar_path(out_dir: Path, unit_id: str) -> Path:
    return Path(out_dir) / f"{unit_id}.index.json"


def pandoc_args(input_path: Path, terms: "str | Path | None", out_dir: Path) -> list[str]:
    """The argv that indexes `input_path`, or none without a term table.

    The unit id is the draft's own stem (its outline id), not pandoc's temp copy."""
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
