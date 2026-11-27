"""Path identity, the corpus fingerprint, and the constants every other
submodule in this package needs -- the shared plumbing, not a layer.

Every submodule imports from here and this imports none of them, which
keeps the package a DAG (#219). Shared constants such as `_ROW_SPLIT`
and `_SECTIONS_TEMPLATE` live here so no module reaches into another's
private name.
"""

import argparse
import hashlib
import re
import sqlite3
from pathlib import Path

from chitragupta import config, ledger
from chitragupta.ledger_citable import PARSED

# One constant per dossier filename: a filename spelled at every use
# site is a rename that misses one.
SCOPE_MD = "scope.md"


# The genres `dossier init --genre` names, one per genre skill. Not
# validated (a refusal would block a draft over a label), but named so
# `review/_units.py`'s genre-to-unit table can be checked against it;
# otherwise a new genre is silently measured at the fallback.
GENRES = (
    "survey",
    "thesis-chapter",
    "textbook-chapter",
    "tutorial",
    "deep-research",
    "digest",
    "research-paper",
)


EVIDENCE_MD = "evidence.md"


REJECTED_MD = "rejected.md"


SECTIONS_MD = "sections.md"


STEERING_MD = "steering.md"


REVISIONS_MD = "revisions.md"


RETRIEVAL_MD = "retrieval.md"


# A `retrieval.md` `mode` that can't collide with a real logged call
# ("search"/"evidence"). Lives here so neither `_retrieval.py` (writer)
# nor `_retrieval_queries.py` (reader) reaches across a private name.
_REVISION_MARKER_MODE = "revision"


# `outline.md` (#455), opt-in via `dossier init --outline`. Outside
# `FILES`, or `status` would report it as a gap in every dossier.
OUTLINE_MD = "outline.md"

# `paper.md`: a research paper's paper-level inputs. Written only for
# that genre; outside `FILES` for the reason above. See `_paper.py`.
PAPER_MD = "paper.md"


# The files `init` writes, in `status` order; the value is how `status`
# counts entries (advisory; see `_count`).
FILES: dict[str, str] = {
    SCOPE_MD: "prose",
    EVIDENCE_MD: "blocks",
    REJECTED_MD: "rows",
    SECTIONS_MD: "rows",
    STEERING_MD: "prose",
    REVISIONS_MD: "prose",
    RETRIEVAL_MD: "rows",
}


class DossierError(Exception):
    """A path that isn't a draft, or an archive that isn't safe to unpack."""


def dossier_dir(draft: Path) -> Path:
    """Where `draft`'s dossier lives.

    Raises rather than guessing for a draft outside `content/drafts/`:
    an unmirrored dossier would be found by nothing later. One directory
    per *draft* (name appended), so two drafts in a topic keep separate
    dossiers.
    """
    mirrored = config.mirrored_dir(draft, config.DRAFTS_DIR, config.DOSSIERS_DIR)
    if mirrored is None:
        raise DossierError(
            f"{draft} is not under {config.DRAFTS_DIR}. A dossier mirrors its "
            "draft's path, so the draft has to live where the genre skills "
            "save it."
        )
    target = mirrored / Path(draft).stem
    # `mirrored_dir` keeps the draft side in; the target side can still
    # escape via a symlinked topic directory, which is checked here as
    # `render_output` and `citation_provenance` check theirs.
    if not config.resolves_inside(target, config.DOSSIERS_DIR):
        raise DossierError(
            f"{target} resolves to {target.resolve()}, outside "
            f"{config.DOSSIERS_DIR.resolve()}. A dossier is only useful where "
            "the rest of the pipeline looks for it, and a copy of content/ is "
            "meant to be the whole record of the work -- remove the symlink on "
            "the topic directory, or point [content].dir (config.toml) at the "
            "tree you are really working in."
        )
    return target


def draft_name(draft: Path) -> str:
    """The draft's path relative to `content/drafts/`, suffix dropped --
    the name `export` matches against and `list` prints."""
    resolved = Path(draft).resolve()
    try:
        relative = resolved.relative_to(config.DRAFTS_DIR.resolve())
    except ValueError:
        return Path(draft).stem
    return relative.with_suffix("").as_posix()


def find_draft(dossier: Path) -> Path | None:
    """The draft a dossier belongs to, if it is still on disk.

    Tries every suffix a genre skill emits (`.md`, or `.tex` from
    thesis-chapter-writer).
    """
    try:
        relative = dossier.resolve().relative_to(config.DOSSIERS_DIR.resolve())
    except ValueError:
        return None
    for suffix in (".md", ".tex"):
        candidate = config.DRAFTS_DIR / relative.with_suffix(suffix)
        if candidate.is_file():
            return candidate
    return None


def all_dossiers() -> list[Path]:
    """Every dossier directory, nearest-first by name."""
    if not config.DOSSIERS_DIR.is_dir():
        return []
    found = {path.parent for path in config.DOSSIERS_DIR.rglob("*.md") if path.name in FILES}
    return sorted(found)


def _corpus_rows() -> list[sqlite3.Row] | None:
    """Every parsed ledger item, or None if there is no readable ledger.

    Parsed only (#1118): an unparsed row is not citable. Opened with
    `ledger.read_connection`: an inspection must not lock or migrate.

    `timeout` is sqlite's default, not 0 (#552): with no WAL, `timeout=0`
    made a reader overlapping a commit fail, which read as "no ledger"
    and ran drift against no corpus. A busy ledger past the timeout still
    returns None rather than adding a third state for every caller.
    `status` and `parsed_path` keep a superseded parse out (#490);
    `collections` filters scoped candidates (#254).
    """
    try:
        con = ledger.read_connection()
    except (ledger.NoLedger, sqlite3.Error):
        return None
    try:
        con.row_factory = sqlite3.Row
        return con.execute(
            "SELECT citekey, title, parsed_path, status, collections FROM items WHERE status = ?",
            (PARSED,),
        ).fetchall()
    except sqlite3.DatabaseError:
        return None
    finally:
        con.close()


def known_citekeys() -> set[str] | None:
    """Every parsed citekey in the ledger, or None if there is no readable one.

    None distinguishes "no corpus" from "an empty corpus" for `status`.
    """
    rows = _corpus_rows()
    return None if rows is None else {row["citekey"] for row in rows}


def digest(citekeys: set[str]) -> str:
    """A short, order-independent fingerprint of a set of citekeys.

    Twelve hex characters: enough to tell corpora apart, short enough
    for one line of `scope.md`.
    """
    joined = "\n".join(sorted(citekeys))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:12]


# The corpus line in scope.md, written by `init` and read by `status`.
# Absent in a hand-written dossier, which just loses the drift check.
_CORPUS_LINE = re.compile(
    r"^-\s*corpus:\s*(\d+)\s+citekeys?,\s*digest\s*`?([0-9a-f]+)`?", re.MULTILINE
)


def recorded_corpus(dossier: Path) -> tuple[int, str] | None:
    """(citekey count, digest) as recorded in `scope.md` at draft time."""
    scope = dossier / SCOPE_MD
    if not scope.is_file():
        return None
    match = _CORPUS_LINE.search(scope.read_text(encoding="utf-8"))
    if not match:
        return None
    return int(match.group(1)), match.group(2)


_SECTIONS_TEMPLATE = """# Sections and their citekeys

<!-- Rebuildable from the draft, and worth keeping anyway: a revision can
     see which section owns a citation without reading the draft. -->

| section | citekeys |
|---|---|
"""


def draft_relpath(draft: Path) -> str:
    try:
        return Path(draft).resolve().relative_to(config.PROJECT_ROOT).as_posix()
    except ValueError:
        return str(draft)


_ROW_SPLIT = re.compile(r"(?<!\\)\|")


def _resolve_dossier(draft_or_dossier: Path) -> Path:
    path = Path(draft_or_dossier)
    return path if path.is_dir() else dossier_dir(path)


def dossier_name(dossier: Path) -> str:
    """A dossier's path under `content/dossiers/` -- what `list` prints."""
    try:
        return dossier.resolve().relative_to(config.DOSSIERS_DIR.resolve()).as_posix()
    except ValueError:
        return dossier.name


def _cmd_list(args: argparse.Namespace) -> int:
    found = all_dossiers()
    if not found:
        print(f"No dossiers under {config.DOSSIERS_DIR}.")
    else:
        for dossier in found:
            draft = find_draft(dossier)
            name = dossier.resolve().relative_to(config.DOSSIERS_DIR.resolve()).as_posix()
            marker = "" if draft else "   (draft missing)"
            print(f"  {name}{marker}")
        print(f"\n  {len(found)} dossier(s) under {draft_relpath(config.DOSSIERS_DIR)}.")
    return 0


# Re-exported so `from chitragupta import dossier` keeps reaching these
# names (#219); the list is an AST scan's result, not everything
# exportable. Position is load-bearing: each submodule imports the core
# names above from this module, so importing them earlier would fail.
# pylint: disable=wrong-import-position
from chitragupta.dossier._archive import export, restore
from chitragupta.dossier._citekeys import citekeys_by_section
from chitragupta.dossier._glossary import glossary_terms
from chitragupta.dossier._create import init
from chitragupta.dossier._drift import drift, drift_all
from chitragupta.dossier._language import set_language
from chitragupta.dossier._retrieval import log_retrieval
from chitragupta.dossier._sections import sections, sections_markdown
from chitragupta.dossier._versions import Snapshot, VersionError, list_versions, resolve, take
from chitragupta.dossier._cli import main
