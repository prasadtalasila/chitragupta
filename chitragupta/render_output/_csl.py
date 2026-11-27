"""The CSL style a render formats its citations and bibliography with."""

import re
from pathlib import Path

from chitragupta import config


# The `<citation>` opening tag, matched textually: ElementTree would rewrite
# namespaces and reflow the file, and the temp copy must stay a one-attribute diff.
_CSL_CITATION_TAG_RE = re.compile(r"<citation(\s[^>]*?)?(/?)>")


def _resolve_csl(csl: str | Path) -> Path:
    """Resolves a `--csl` value the way a shell-typed path should resolve.

    The CWD first, like every other file argument. A relative path missing there
    falls back to the project root (`[render] csl` is documented relative to it),
    then the shipped assets, which are not under the project root once
    pip-installed (docs/PACKAGING.md). Project first, so a user's own
    `assets/csl/ieee.csl` wins. With no hit, returns the CWD path so the error
    names what was typed.
    """
    path = Path(csl)
    if path.is_absolute() or path.exists():
        return path
    for root in (config.PROJECT_ROOT / path, config.shipped(str(path))):
        if root.is_file():
            return root
    return path


def _collapsed_csl(csl_path: Path, tmp_dir: Path) -> Path:
    """Returns a CSL style path whose citations collapse consecutive runs.

    IEEE's guide uses "[1]-[4]"; CSL's knob is `collapse="citation-number"`.
    Added to a temp copy so `assets/csl/ieee.csl` stays byte-identical to
    upstream. A style already setting `collapse` is returned unchanged.
    """
    text = csl_path.read_text(encoding="utf-8")
    match = _CSL_CITATION_TAG_RE.search(text)
    if match is None or "collapse=" in (match.group(1) or ""):
        return csl_path

    patched = (
        text[: match.start()]
        + f'<citation collapse="citation-number"{match.group(1) or ""}{match.group(2)}>'
        + text[match.end() :]
    )
    out = tmp_dir / csl_path.name
    out.write_text(patched, encoding="utf-8")
    return out
