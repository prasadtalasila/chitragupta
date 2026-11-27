"""Path containment: is a path inside `content/`, and where does one
`content/` subtree's path land under another.

Split from `chitragupta/config.py` (#441), which re-exports it.
`CONTENT_DIR` is read as `config.CONTENT_DIR` at call time, so
`isolated_config`'s patch is seen, and `config` is imported inside the
function: `config.py` imports this module, so a top-level import would
hit a partially initialised `config`.
"""

import os
import sys
from pathlib import Path


class OutsideContentDir(RuntimeError):
    """A path a tool was asked to read or write lies outside CONTENT_DIR.

    Raised, not worked around: `content/` being the whole record of the
    work is what makes a `dossier export` complete.
    """


def resolves_inside(path: Path, root: Path) -> bool:
    """Whether `path` really lives under `root`, once both are resolved,
    so symlinks and `..` answer for where they land.

    A symlink loop is not inside anything: `Path.resolve()` raises on
    3.12/3.13 and returns the link on 3.14, while `os.path.realpath` stops
    at the loop on every version. A NUL byte raises `ValueError` here,
    since Windows `realpath` would not.
    """
    if "\0" in os.fspath(path):
        raise ValueError(f"embedded null byte in {os.fspath(path)!r}")
    resolved = Path(os.path.realpath(path))
    if resolved.is_symlink():
        return False  # pragma: no cover-windows
    return resolved.is_relative_to(Path(os.path.realpath(root)))


def confined_path(value: "str | Path | None", root: Path) -> "Path | None":
    """`value` as a path, or `None` -- reported, never silently -- when
    it does not land inside `root`.

    For paths this pipeline is handed (ledger `parsed_path`/`pdf_path`,
    a bib `file` field, issue 821): another tool wrote them, and
    `~/.ssh/id_rsa` became quotable corpus evidence. Returns rather than
    raises so one refused row does not stop a bulk read. Absent values
    return `None` silently (the routine case); a refusal is printed to
    stderr, keeping stdout clean for `--json`. Resolution errors
    (`ValueError`, Windows `OSError`) are refusals, not crashes.
    """
    if not value:
        return None
    path = Path(value)
    try:
        if resolves_inside(path, root):
            return path
    except (OSError, ValueError):
        pass
    print(
        f"  WARNING refusing {value}: it does not land inside {root}. A path read "
        "out of the ledger or out of a bib `file` field names a host file, so "
        "this pipeline opens one only inside the corpus (issue 821).",
        file=sys.stderr,
    )
    return None


def mirrored_dir(path: Path, source_root: Path, target_root: Path) -> "Path | None":
    """`target_root` carrying `path`'s own place under `source_root`, the
    rule drafts, renders, dossiers and reviews share per topic.

    `None` when `path` is not under `source_root`; the caller decides
    (render/review fall back flat, the dossier raises). Only the part
    below `source_root` is carried, so the result holds no `..`, but the
    caller must still confine it to `target_root`. Lives here because
    render_output cannot import `dossier/`, and copies of the rule let two
    `survey.md` drafts share one report.
    """
    try:
        relative = Path(path).resolve().relative_to(Path(source_root).resolve())
    except ValueError:
        return None
    return Path(target_root) / relative.parent


def require_inside_content(path: Path, what: str = "draft") -> Path:
    """Returns `path`, having refused it if it resolves outside CONTENT_DIR."""
    from chitragupta import config

    if not resolves_inside(path, config.CONTENT_DIR):
        raise OutsideContentDir(
            f"{path} resolves to {Path(path).resolve()}, outside the content "
            f"directory {config.CONTENT_DIR.resolve()}. This pipeline reads and writes "
            f"only under content/, so that one directory is the whole record of "
            f"the work -- move the {what} under content/drafts/ (where the genre "
            f"skills save one, and the only place whose path is mirrored into "
            f"content/rendered/), or point [content].dir in config.toml at the "
            f"tree you are really working in."
        )
    return Path(path)
