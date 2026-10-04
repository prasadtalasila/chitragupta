"""Path containment: is a path inside `content/`, and where does one
`content/` subtree's path land under another.

Split from `chitragupta/config.py` (#441). Re-exported through
`config.py`'s own shim (`from chitragupta import config_path` there)
rather than requiring every one of this module's many callers --
`render_output`, `citation_gate`, `references`, `review`, `dossier` --
to add a second tier-1 import alongside `config`, which would widen a
contract `docs/ARCHITECTURE.md` documents explicitly. `config.py` still
owns `CONTENT_DIR` itself; `require_inside_content` reads it as
`config.CONTENT_DIR` (a live attribute lookup on the shared `config`
module), not a bare name imported at this module's own load time --
`tests/conftest.py`'s `isolated_config` fixture patches
`config.CONTENT_DIR` directly, and a bare import here would keep
reading the value from before that patch.

The `from chitragupta import config` this needs is deferred inside
`require_inside_content` rather than sitting at module level, for the
same reason `chitragupta/enrich/_docling_pool.py` defers its own
back-import: `config.py` imports *this* module (to re-export these four
names), so if this module is ever imported before `config.py` is (a
bare `import chitragupta.config_path`, or any other module reaching it
first), a top-level `from chitragupta import config` here would resume
`config.py`'s own in-progress execution, hit its `from
chitragupta.config_path import (...)` line, and find this module still
mid-import -- an `ImportError` on a name that exists moments later.
Deferring the import until the function actually runs sidesteps the
partial-initialization window entirely.
"""

import sys
from pathlib import Path


class OutsideContentDir(RuntimeError):
    """A path a tool was asked to read or write lies outside CONTENT_DIR.

    Raised rather than worked around. Every path this pipeline reads or
    writes lives under `content/`, which is what makes a `dossier export`
    or a copy of that one directory a complete record of the work -- a
    draft kept somewhere else is invisible to backup, to `dossier`, and
    to every later revision.
    """


def resolves_inside(path: Path, root: Path) -> bool:
    """Whether `path` really lives under `root`, once both are resolved.

    Resolving both sides is the whole point: it is what makes a symlink
    and a `..` component answer for where they actually land rather than
    for how they are spelled.
    """
    return Path(path).resolve().is_relative_to(Path(root).resolve())


def confined_path(value: "str | Path | None", root: Path) -> "Path | None":
    """`value` as a path, or `None` -- reported, never silently -- when
    it does not land inside `root`.

    For the two path-shaped strings this pipeline is *handed* rather
    than computes: `parsed_path`/`pdf_path` read back out of a ledger
    row (which reach here through `ledger_paths`, stored relative to
    their root and anchored at it before this check), and the path
    inside a bib entry's `file` field (issue 821).
    Both are data some other tool wrote -- a reference manager, an
    older release, a collaborator's export, a hand edit of a gitignored
    sqlite file -- so both can name any file on the host, and every
    consumer used to open whichever one they named. That made
    `~/.ssh/id_rsa` indexable as a paper's parsed text, and quotable
    into a draft as corpus evidence.

    Returns a value rather than raising because the callers are bulk
    readers over a whole corpus, and one refused row must not take the
    other six hundred down with it. `None` is the answer they already
    have a branch for -- "nothing readable here" -- so a refused row
    reads as unparsed rather than as a new kind of failure. An absent
    or empty value returns `None` too, and *silently*, because that is
    the routine case: most rows in a fresh ledger have no parsed text
    yet, and a warning per row would bury the one that matters.

    The refusal itself is never quiet. This project's own named worst
    failure mode is the silent skip that drops a paper from the corpus,
    so a refusal names the offending value and the root it had to land
    under, on stderr, leaving stdout clean for the `--json` callers.

    `resolves_inside` resolves both sides, which is what makes a symlink
    answer for where it actually lands -- the case that matters on a
    shared `content/`, where the name can be inside the corpus and the
    bytes outside it. Resolving can also raise rather than answer: a NUL
    byte gives `ValueError`, and a name the platform will not accept
    gives `OSError` on Windows. Both are refusals, not crashes.
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
    """`target_root` carrying `path`'s own place under `source_root`.

    The one rule four directories under `content/` obey: a draft at
    `content/drafts/<topic>/survey.md` has its renders at
    `content/rendered/<topic>/`, its dossier at
    `content/dossiers/<topic>/survey/`, and its review reports at
    `content/review/<topic>/`. One topic directory, one draft's worth of
    everything.

    Returns `None` when `path` is not under `source_root`, rather than
    picking an answer, because the callers disagree about what that means
    and each is right for itself. `render_output._output_dir` and
    `review.report_path` fall back to the flat target directory: both
    accept an input that is legitimately elsewhere under `content/`, and
    writing its output flat is a better answer than refusing to produce
    any. `dossier.dossier_dir` raises, because a dossier written
    somewhere unmirrored would be found by nothing later. Policy stays
    with the caller; only the rule lives here.

    Note this says nothing about which inputs a caller will *accept* --
    that is a separate decision each one makes for itself, before it gets
    here (`render_output` and `references` confine reads to `content/`
    with `require_inside_content`, and `review.require_reviewable` does
    the same for the three review aids).

    Only the part of `path` *below* `source_root` is ever carried over,
    and both sides are resolved before being compared, so the result can
    hold neither a `..` nor a symlink's spelling. It is still the
    caller's job to check the result resolves inside `target_root`:
    `source_root` and `target_root` are configuration, and a symlinked
    one can land outside without any argument being at fault.

    Lives here rather than in either caller because `chitragupta/render_output.py`
    is committed to stdlib plus `config`/`citation_gate`/`references` so a
    genre skill can render under bare `python` -- it cannot import
    `chitragupta/dossier/`, and before this the rule was written out three times
    and missed in a fourth place (`citation_provenance`), which is how
    two drafts named `survey.md` came to share one report.
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
