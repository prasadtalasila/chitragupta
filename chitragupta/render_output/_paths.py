"""Where a rendered draft lands, and which inputs count as Markdown.

`_output_dir` holds the *policy* -- mirror the draft's own place under
`content/drafts/` into `content/rendered/`, fall back flat, and refuse to
write outside `content/`. The mechanism it defers to is
`config.mirrored_dir()`, shared with `dossier` and `review`.
"""

from pathlib import Path

from chitragupta import config
from chitragupta.render_output._errors import OutsideContentDir


# Input suffixes treated as Markdown by the `md` output format (see
# render()). Anything else -- .tex above all -- is a real conversion and
# goes to pandoc.
_MARKDOWN_SUFFIXES = {".md", ".markdown"}


def _output_dir(input_path: Path) -> Path:
    """Where `input_path`'s rendered output goes: `config.RENDERED_DIR`
    with the draft's own place under `config.DRAFTS_DIR` mirrored into
    it, so `content/drafts/dt/survey.md` renders to
    `content/rendered/dt/survey.{md,tex,pdf,docx}`.

    **Every path this returns resolves inside `config.CONTENT_DIR`**,
    which is the invariant the checks below exist for. Since 3.17.0 the
    read side is confined too, but not here: `render()` calls
    `config.require_inside_content` on its input before this is ever
    reached, so what arrives is already somewhere under `content/`. The
    flat fallback below is therefore for a draft that is under `content/`
    but not under `content/drafts/` -- `content/loose.md`, say -- not for
    one "anywhere on disk", which no longer reaches this function.

    What that leaves:

      - A draft not under `DRAFTS_DIR` has no path to mirror, so the
        flat `RENDERED_DIR` stands. So does a flat
        `content/drafts/<slug>.md`, whose relative parent is `.`.
      - Only the part of the draft's path *below* `DRAFTS_DIR` is ever
        carried over, and both sides are resolved before they are
        compared, so `relative` can hold neither a `..` nor a symlink's
        spelling -- there is no argument that mirrors to somewhere else.
      - The three ways the write could still land outside `content/` are
        all configuration or symlinks rather than arguments, and each
        raises `OutsideContentDir` rather than being redirected: a
        `content/rendered` or `content/drafts` that resolves out of
        `CONTENT_DIR`, and a mirrored topic directory that resolves out
        of `RENDERED_DIR`. `_copy_local_images` skips an escaping image
        reference silently because the draft is still rendered correctly
        without that one image; here there is no correct output left to
        produce, so this says so instead.

    The rule itself is `config.mirrored_dir()`, shared with
    `dossier.dossier_dir()` and `review.report_path()` rather than
    written out again here. It lives in `config` because this module's
    docstring commits it to stdlib plus
    `config`/`citation_gate`/`references` so a genre skill can render
    under bare `python`, which rules out importing `chitragupta/dossier/`.
    What stays here is the *policy* -- fall back flat, and refuse to
    write outside `content/` -- which is this module's to decide.

    **One mirror source, and a caller that can say otherwise.** This
    function answers "where does a *draft* render to", so `DRAFTS_DIR` is
    the only source root it knows. A caller rendering something that is
    not a draft -- `chitragupta/review/__init__.py`, turning a review report into
    `.tex`/`.pdf` beside the report -- passes `render(output_dir=...)`
    and never reaches here.

    3.19.2 did that differently, mirroring from `PROVENANCE_DIR` as a
    second source root so a provenance report's renders would stop
    colliding. It worked, but it put a review-layer directory in the path
    of every ordinary draft render, and it landed the renders in
    `content/rendered/` -- the drafting layer's publish output -- rather
    than beside the report they belong to. `output_dir` replaces it:
    "the caller says where" is not a second rule about drafts.
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
