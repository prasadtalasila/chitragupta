"""Where a review report may be read from and goes to (#991).

`require_reviewable` and `report_dir` lived in `review/__init__.py` from
the day the layer had one output contract. They moved here when the
eleventh aid's `AIDS` entry needed one more line in a module already at
docs/CODE-STANDARDS.md's 250-code-line ceiling, and this is the boundary
that module's own docstring draws: this half is *where* a report goes,
the other half is what it looks like. `report_path` stays there because
it needs `AIDS`. Both names are re-exported from `review` unchanged, so
no caller moved.
"""

from pathlib import Path

from chitragupta import config
from chitragupta.review import _book_paths


def require_reviewable(draft: Path, what: str = "draft") -> Path:
    """Returns `draft`, having refused it if it is missing or outside `content/`.

    The layer's input contract in one place. The containment half is the
    tier-1 rule 3.17.0 set for `citation_gate`, `references` and
    `render_output` and did not then apply to the three review aids --
    everything this pipeline touches lives under `content/`, so that one
    directory is the whole record of the work. The existence half is here
    so all three commands fail the same way on a mistyped path, instead
    of one returning 1 and two raising `FileNotFoundError`.
    """
    path = config.require_inside_content(Path(draft), what)
    if not path.is_file():
        raise FileNotFoundError(f"No such {what}: {draft}")
    return path


def report_dir(draft: Path) -> Path:
    """Where `draft`'s review reports go: `config.REVIEW_DIR` with the
    draft's own place under `config.DRAFTS_DIR` mirrored into it.

    An assembled book is mirrored from `config.RENDERED_DIR` instead --
    `_book_paths.review_dir_for` owns both cases and why.

    Falls back to a flat `REVIEW_DIR` for a draft under `content/` but
    under neither, matching `render_output._output_dir`'s policy rather
    than `dossier.dossier_dir`'s raise: a review aid that refuses to run
    is a worse answer than one that writes flat, and unlike a dossier,
    nothing later goes looking for the report by its mirrored path.
    """
    for label, directory in (("review", config.REVIEW_DIR), ("drafts", config.DRAFTS_DIR)):
        if not config.resolves_inside(directory, config.CONTENT_DIR):
            raise config.OutsideContentDir(
                f"{directory} resolves to {directory.resolve()}, outside the content "
                f"directory {config.CONTENT_DIR.resolve()}. A review report mirrors "
                f"the draft's path from content/drafts/ into content/review/, so a "
                f"'{label}' that points out of the content directory has no mirror to "
                "compute and would write where nothing else in this pipeline looks. "
                "Move it back, or point [content].dir (config.toml) at wherever it "
                "really lives."
            )

    mirrored = _book_paths.review_dir_for(draft)
    if mirrored is None:
        return config.REVIEW_DIR
    if not config.resolves_inside(mirrored, config.REVIEW_DIR):
        raise config.OutsideContentDir(
            f"{mirrored} resolves to {mirrored.resolve()}, outside "
            f"{config.REVIEW_DIR.resolve()}. A draft's own path is never a reason to "
            "write outside the content directory -- remove the symlink, or review a "
            "draft from a topic directory that isn't one."
        )
    return mirrored
