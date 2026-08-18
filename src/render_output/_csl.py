"""The CSL style a render formats its citations and bibliography with.

`assets/csl/ieee.csl` stays byte-identical to what the CSL project
publishes; the one attribute this project wants on top of it is added to
a temp copy here (see `_collapsed_csl`).
"""

import re
from pathlib import Path

from src import config


# The `<citation>` element opening tag, with or without attributes
# already on it. Upstream CSL styles hand-format this file, so matching
# the tag textually (rather than parsing and re-serializing the whole
# document with ElementTree, which rewrites namespace prefixes and
# reflows every other element) keeps the temp copy a one-attribute diff
# against the vendored original -- which is the point of not editing the
# vendored file in the first place.
_CSL_CITATION_TAG_RE = re.compile(r"<citation(\s[^>]*?)?(/?)>")


def _resolve_csl(csl: str | Path) -> Path:
    """Resolves a `--csl` value the way a shell-typed path should resolve.

    Against the current working directory first: that is what a path
    typed at a shell means, and it is already how this CLI resolves its
    `input` argument, so `--csl ./house-style.csl` behaves like every
    other file argument.

    A *relative* path that doesn't exist there falls back to the repo
    root. Without that, the two ways of naming the same style disagree --
    `config.toml`'s `[render] csl` is documented as repo-root-relative
    (and `--help` prints the shipped default in that form), so
    `--csl assets/csl/ieee.csl` would work from the repo root and fail
    from anywhere else, for no reason the user could see.

    When neither candidate exists, returns the CWD-relative one, so the
    error names the path that was actually typed.
    """
    path = Path(csl)
    if path.is_absolute() or path.exists():
        return path
    from_repo_root = config.REPO_ROOT / path
    return from_repo_root if from_repo_root.is_file() else path


def _collapsed_csl(csl_path: Path, tmp_dir: Path) -> Path:
    """Returns a CSL style path whose citations collapse consecutive runs.

    Upstream `ieee.csl` renders `[@a; @b; @c; @d]` as "[1], [2], [3], [4]".
    The IEEE Reference Guide's own examples use the collapsed "[1]-[4]"
    form, and CSL has exactly one knob for it: `collapse="citation-number"`
    on `<citation>`. Rather than carry a modified copy of a CC BY-SA style
    in-tree (where the deviation is invisible in a diff against upstream
    and easy to lose across a style bump), the attribute is added here, to
    a temp copy, and assets/csl/ieee.csl stays byte-identical to what the
    CSL project publishes.

    A style that already sets `collapse` is returned unchanged -- its
    author made a deliberate choice, and overriding it would silently
    change how someone's own style renders.
    """
    text = csl_path.read_text(encoding="utf-8")
    match = _CSL_CITATION_TAG_RE.search(text)
    if match is None or "collapse=" in (match.group(1) or ""):
        return csl_path

    patched = (
        text[:match.start()]
        + f'<citation collapse="citation-number"{match.group(1) or ""}{match.group(2)}>'
        + text[match.end():]
    )
    out = tmp_dir / csl_path.name
    out.write_text(patched, encoding="utf-8")
    return out
