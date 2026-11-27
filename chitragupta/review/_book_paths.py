"""Which directory answers a question about an assembled book.

The assembly and fragments live in `content/rendered/<book>/`, the units'
`.md` in `content/drafts/<book>/`, the acceptance records in
`content/specs/<book>/`. Fragments resolve beside the assembly, where LaTeX
resolves `\\input`; records are reached from the drafts directory, since
`spec.spec_dir` requires a path under `config.DRAFTS_DIR`. Named here so
`refuse_a_unit` cannot drift from `compute`, and in its own module because
C2 leaves `review/__init__.py` and `citekey_union.py` no headroom.
"""

from pathlib import Path

from chitragupta import config


def drafts_dir_for(assembled: Path) -> Path:
    """The `content/drafts/` book directory `assembled` is checked against.

    Falls back to `assembled.parent` outside `content/rendered/`, as
    `report_dir` does: an older book still has its units beside it. Says
    nothing about existence; `spec.spec_dir`'s refusal names the missing
    spec.
    """
    mirrored = config.mirrored_dir(assembled, config.RENDERED_DIR, config.DRAFTS_DIR)
    return Path(assembled).parent if mirrored is None else mirrored


def review_dir_for(draft: Path) -> "Path | None":
    """`draft`'s place under `config.REVIEW_DIR`, or None if it has none.

    `content/rendered/` is tried after `content/drafts/` so every book's
    `book.union.md` does not collide in one flat file. None falls to
    `report_dir`'s flat fallback, which collides with nothing.
    """
    for source in (config.DRAFTS_DIR, config.RENDERED_DIR):
        mirrored = config.mirrored_dir(draft, source, config.REVIEW_DIR)
        if mirrored is not None:
            return mirrored
    return None
