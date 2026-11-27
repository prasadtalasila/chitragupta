"""Where a rendered draft lands, and which inputs count as Markdown.

`_output_dir` holds the policy; the mirroring is `config.mirrored_dir()`.
"""

from pathlib import Path

from chitragupta import config
from chitragupta.render_output._errors import OutsideContentDir


# Input suffixes the `md` format passes through; anything else (.tex above all)
# is a real conversion and goes to pandoc.
_MARKDOWN_SUFFIXES = {".md", ".markdown"}


def _output_dir(input_path: Path) -> Path:
    """Where `input_path`'s rendered output goes: the draft's place under
    `DRAFTS_DIR` mirrored into `RENDERED_DIR`, or flat `RENDERED_DIR` for a
    draft elsewhere under `content/`.

    **Every path this returns resolves inside `config.CONTENT_DIR`.** Only the
    part below `DRAFTS_DIR` is carried over, both sides resolved first, so no
    argument can mirror elsewhere. A `content/rendered`, `content/drafts` or
    topic directory resolving outside (config or symlinks) raises
    `OutsideContentDir` rather than redirecting: unlike a skipped escaping
    image, there is no correct output left to produce.

    The rule lives in `config` because this package must stay importable
    under bare `python`, which rules out `chitragupta/dossier/`. A non-draft
    caller (review reports) passes `render(output_dir=...)` instead of adding
    a second mirror root here, which once put review-layer paths in every render.
    """
    for label, directory in (("rendered", config.RENDERED_DIR), ("drafts", config.DRAFTS_DIR)):
        if not config.resolves_inside(directory, config.CONTENT_DIR):
            raise OutsideContentDir(
                f"{directory} resolves to {directory.resolve()}, outside the content "
                f"directory {config.CONTENT_DIR.resolve()}. Rendering mirrors a draft's "
                f"path from content/drafts/ into content/rendered/, so a '{label}' that "
                "points out of the content directory has no mirror to compute and would "
                "write where nothing else in this pipeline looks. Move it back, or point "
                "[content].dir (config.toml) at wherever it really lives."
            )

    mirrored = config.mirrored_dir(input_path, config.DRAFTS_DIR, config.RENDERED_DIR)
    if mirrored is None:
        return config.RENDERED_DIR

    if not config.resolves_inside(mirrored, config.RENDERED_DIR):
        raise OutsideContentDir(
            f"{mirrored} resolves to {mirrored.resolve()}, outside "
            f"{config.RENDERED_DIR.resolve()}. A draft's own path is never a reason to "
            "write outside the content directory -- remove the symlink, or render the "
            "draft from a topic directory that isn't one."
        )
    return mirrored


def _target_dir(input_path: Path, output_dir: str | Path | None) -> Path:
    """Where this render lands: the mirrored default, or the caller's own,
    which is confined to `content/` exactly like the default.
    """
    if output_dir is None:
        return _output_dir(input_path)
    out_dir = Path(output_dir)
    if not config.resolves_inside(out_dir, config.CONTENT_DIR):
        raise OutsideContentDir(
            f"{out_dir} resolves to {out_dir.resolve()}, outside the content "
            f"directory {config.CONTENT_DIR.resolve()}. Naming an output "
            "directory does not widen where this pipeline may write -- see "
            "config.require_inside_content, and point [content].dir "
            "(config.toml) at the tree you are really working in."
        )
    return out_dir
