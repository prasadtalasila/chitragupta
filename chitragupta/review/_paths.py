"""Where a review report may be read from and goes to (#991).

Split from `review/__init__.py` at its 250-code-line ceiling: this half is
where a report goes, that half what it looks like. Both names are
re-exported from `review`.
"""

from pathlib import Path

from chitragupta import config
from chitragupta.review import _book_paths


def require_reviewable(draft: Path, what: str = "draft") -> Path:
    """Returns `draft`, having refused it if it is missing or outside `content/`.

    Containment keeps `content/` the whole record of the work; the
    existence check makes every aid fail the same way on a mistyped path.
    """
    path = config.require_inside_content(Path(draft), what)
    if not path.is_file():
        raise FileNotFoundError(f"No such {what}: {draft}")
    return path


def report_dir(draft: Path) -> Path:
    """Where `draft`'s review reports go: `config.REVIEW_DIR` with the
    draft's place under `config.DRAFTS_DIR` mirrored (books: see
    `_book_paths.review_dir_for`).

    Elsewhere under `content/` falls back to flat `REVIEW_DIR`, as
    `render_output._output_dir` does: unlike a dossier, nothing later
    looks the report up by its mirrored path.
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
