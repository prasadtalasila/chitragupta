"""Path identity, the corpus fingerprint, and the constants every other
submodule in this package needs -- the shared plumbing, not a layer of
its own.

Split out of what was one 1770-line src/dossier.py (#219): every other
submodule in this package imports from here, and this one imports
nothing from any of them, which is what keeps the package a DAG rather
than a tangle. `_ROW_SPLIT` and `_SECTIONS_TEMPLATE` live here rather
than with the modules that look like their obvious home (status,
create) because both are genuinely shared across three or more
submodules -- moving either into one specific module would have made
the others reach into a private (`_`-prefixed) name across a file
boundary, which is worse than the mild surprise of finding them here.
"""

import argparse
import hashlib
import re
import sqlite3
from pathlib import Path

from src import config

# One constant per dossier filename, because each recurs across this
# module -- as FILES keys, template keys, path joins and report lookups
# -- and a filename spelled at every use site is a rename that misses
# one. All seven are named, not only the ones repeated often enough for
# a duplicated-literal check to notice: a dict keyed by five constants
# and two bare strings would read as if the two were different in kind.
SCOPE_MD = "scope.md"


EVIDENCE_MD = "evidence.md"


REJECTED_MD = "rejected.md"


SECTIONS_MD = "sections.md"


STEERING_MD = "steering.md"


REVISIONS_MD = "revisions.md"


RETRIEVAL_MD = "retrieval.md"

# The files a dossier holds, in the order `init` writes them and `status`
# reports them. The value is how `status` counts entries in that file --
# see `_count`, and the "counts are advisory" note there.
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

    Raises rather than guessing if the draft isn't under
    `content/drafts/`: the mirroring rule is the only thing tying the two
    together, and a dossier written somewhere unmirrored would be found
    by nothing later. That refusal is this module's policy;
    `config.mirrored_dir` holds only the shared rule, and answers `None`
    so each caller can decide.

    One shape difference from the other three consumers of that rule: a
    dossier is a *directory per draft*, not per topic, so the draft's own
    name is appended. `content/drafts/dt/survey.md` gets
    `content/dossiers/dt/survey/`, which is what lets two drafts in one
    topic directory keep separate dossiers.
    """
    mirrored = config.mirrored_dir(draft, config.DRAFTS_DIR, config.DOSSIERS_DIR)
    if mirrored is None:
        raise DossierError(
            f"{draft} is not under {config.DRAFTS_DIR}. A dossier mirrors its "
            "draft's path, so the draft has to live where the genre skills "
            "save it."
        )
    target = mirrored / Path(draft).stem
    # The draft's own path can't get out -- `mirrored_dir` resolves both
    # sides before subtracting them, so no argument carries a `..` or a
    # symlink's spelling past it. What can is the target side: a topic
    # directory under content/dossiers/ that is itself a symlink out of
    # the tree. `render_output._output_dir` and
    # `citation_provenance.write_report` both check their own mirrored
    # result for exactly this; this is the third consumer of that rule and
    # was the one that didn't.
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

    The inverse of `dossier_dir`, except that the suffix was dropped on
    the way in -- so this looks for any suffix a genre skill emits
    (`.md` from four of them, `.tex` from thesis-chapter-writer).
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
    found = {
        path.parent
        for path in config.DOSSIERS_DIR.rglob("*.md")
        if path.name in FILES
    }
    return sorted(found)


def _corpus_rows() -> list[sqlite3.Row] | None:
    """Every ledger item, or None if there is no readable ledger.

    Opened read-only and with `timeout=0`, exactly as `src.ledger`'s own
    CLI does and for the same reason: this is an inspection, and it must
    not take a write lock, run a migration, or block behind a sync that
    happens to be mid-run. `src.ledger.connect()` would do all three --
    it mkdirs `content/`, executes the schema and runs migrations -- so
    nothing here goes through it, and `src.retrieval.search()`, which
    does, is off limits for the same reason (see `_ephemeral_index`).

    Three columns rather than one because the drift scan needs the same
    fields `src.retrieval` indexes on: `title` and `parsed_path` are what
    a BM25 entry is built from, and `title` is also what makes a reported
    candidate legible without a second lookup.
    """
    if not config.LEDGER_PATH.exists():
        return None
    try:
        con = sqlite3.connect(f"file:{config.LEDGER_PATH}?mode=ro", uri=True, timeout=0)
    except sqlite3.Error:
        return None
    try:
        con.row_factory = sqlite3.Row
        return con.execute("SELECT citekey, title, parsed_path FROM items").fetchall()
    except sqlite3.DatabaseError:
        return None
    finally:
        con.close()


def known_citekeys() -> set[str] | None:
    """Every citekey in the ledger, or None if there is no readable one.

    None (rather than an empty set) distinguishes "no corpus on this
    machine" from "a corpus with nothing in it" -- `status` says
    different things about those two.
    """
    rows = _corpus_rows()
    return None if rows is None else {row["citekey"] for row in rows}


def digest(citekeys: set[str]) -> str:
    """A short, order-independent fingerprint of a set of citekeys.

    Twelve hex characters, which is plenty to answer the only question
    asked of it -- "is this the same corpus the draft was written
    against?" -- and short enough to sit on one line of `scope.md`
    without looking like something a reader has to parse.
    """
    joined = "\n".join(sorted(citekeys))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:12]


# `- corpus: 501 citekeys, digest `a1b2c3d4e5f6`` in scope.md. Written by
# `init`, read by `status`, and safe to be absent -- a hand-written
# dossier that never recorded one just loses the drift check.
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
    """`draft` relative to the repo root where possible, for display."""
    try:
        return Path(draft).resolve().relative_to(config.REPO_ROOT).as_posix()
    except ValueError:
        return str(draft)


_ROW_SPLIT = re.compile(r"(?<!\\)\|")


def _resolve_dossier(draft_or_dossier: Path) -> Path:
    """A dossier directory, given either it or the draft it belongs to."""
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


# Re-exported so `from src import dossier` keeps reaching these by the
# same name it always has, from every file outside this package that
# used to reach a flat src/dossier.py this way. Found by an AST scan for
# every `dossier.<attr>` across src/, scripts/, tests/ and bench/ (a text
# grep missed multi-line `from src import (...)` blocks, e.g.
# src/overlap_embed.py's) -- this list is exactly that scan's result, not
# everything this package could plausibly export. Every other name is
# reached by importing the submodule that owns it, same as src/review/'s
# submodules already do.
#
# Position is load-bearing, not style: each of these submodules itself
# does `from src.dossier import <core name>` to reach what's above this
# line, so importing any of them before this module has finished
# defining its own core names would fail with an ImportError on a name
# that doesn't exist yet. pylint's wrong-import-position (C0413) is
# right that this is unusual and wrong to do without a reason -- here is
# the reason.
# pylint: disable=wrong-import-position
from src.dossier._archive import export, restore
from src.dossier._citekeys import citekeys_by_section, glossary_terms
from src.dossier._create import init
from src.dossier._drift import drift, drift_all
from src.dossier._language import set_language
from src.dossier._retrieval import log_retrieval, retrieval_cost
from src.dossier._sections import sections, sections_markdown
from src.dossier._cli import main
