"""`chitragupta init [DIR] [--force] [--dry-run]`: scaffold a project directory.

A wheel installs importable modules. That is not what this project ships:
a user with only `pip install chitragupta-cli` has no `config.toml`, no
`.claude/skills/` (so no hook registers the citation gate), no `content/`
tree and no `AGENTS.md` for the skills to cite. `scripts/release.py`'s
zip is the existing answer to "what does a consumer actually need"; this
is the pip-installed one, writing the same project directory the zip
ships today.

**Reads from `SOURCE_ROOT`, not from the source tree.** Once this code is
installed, `chitragupta/config.py`'s `shipped()` already resolves the
project's vendored assets (the CSL style, the Vale rules, the default
acronym list) from `PACKAGE_ROOT.parent` -- one level above the installed
package, wherever that is. `pyproject.toml`'s `[tool.poetry].include`
ships `.claude/`, `docs/` and the four root `.md` files to that exact
sibling location for the same reason, so this module reads from the same
seam `shipped()` already established rather than inventing a second one.

**Copying `assets/` does not change what the pipeline reads by
default.** `shipped()` still resolves the vendored CSL style, Vale
config and acronym list from the *installed package's* location, not
from the copy this scaffolds -- editing the copied file has no effect
until `config.toml`'s `[render].csl`/`[render].vale_config`/
`[style].acronyms` is repointed at it (docs/CONFIG.md). The copy exists
so those files are discoverable and editable without a user having to
locate `site-packages` by hand; it is not a live override by itself.

**The pin that keeps the two lists honest.** `scripts/release.py`'s
`EXCLUDE_TOP_LEVEL` is a *denylist* over every git-tracked path: a new
root-level file ships in the release zip unless someone adds it there.
`TOP_LEVEL` below is an *allowlist* over what a pip-installed reader
actually needs: a new root-level file is *not* scaffolded unless someone
adds it here. Two lists that must agree will drift -- #208 is the
precedent, a root-level file that entered the zip silently and was caught
by review rather than by a check. `DELIBERATE_DIFFERENCES` is the one
named set both `tests/test_init.py` and this module read, so a future
drift fails a test naming which list needs editing rather than passing
unnoticed on both sides.
"""

import argparse
import shutil
import sys
from pathlib import Path

from chitragupta.progname import prog_for

# Deliberately not `from chitragupta.config import PACKAGE_ROOT`: that
# module raises at import time when no `config.toml` exists yet
# (`chitragupta/hook_launchers.py`'s docstring names the same trap), which
# is exactly the state `init` exists to fix -- a user running it for the
# first time has no project yet. `PACKAGE_ROOT` needs no project to
# compute, only this file's own location, so it is a one-line copy
# rather than an import.
PACKAGE_ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = PACKAGE_ROOT.parent

# Copied verbatim -- files and whole directory trees -- from SOURCE_ROOT
# into the target directory, unchanged. Every one of these has to be
# present for the scaffolded project to actually work: the genre skills
# cite AGENTS.md by name, CLAUDE.md routes, docs/ is the exhaustive
# per-flag reference, and .claude/ registers the hooks that enforce the
# citekey invariant. assets/ is the one exception to "has to be present":
# the pipeline's own defaults resolve it from the installed package
# regardless (see the module docstring), so this copy is for the user to
# find and edit, not something anything here reads. DOCKER.md is a
# second: `docker/` itself is deliberately not scaffolded (see
# DELIBERATE_DIFFERENCES), but the doc that says "how do I run this in a
# container" still has to reach someone who only ever ran `pip install`.
COPY_VERBATIM = (
    ".claude",
    "docs",
    "assets",
    "AGENTS.md",
    "CLAUDE.md",
    "SOUL.md",
    "README.md",
    "DOCKER.md",
)


class ScaffoldSourceMissing(Exception):
    """An installation that cannot write a complete scaffold -- see
    `scaffold`, which refuses rather than writing a partial one."""


# The one entry that changes name on the way in. config.toml is
# gitignored per-user data (chitragupta/config.py's PROJECT_MARKER), so
# init writes the user's own starting copy, never the tracked template
# under its own name -- the same distinction a git checkout already
# draws with `cp config.toml.example config.toml`.
CONFIG_EXAMPLE = "config.toml.example"
CONFIG_DEST = "config.toml"

# Created empty, so config.toml's default paths (content.dir, bib.path's
# parent) resolve to something that exists before a first
# `corpus sync` populates them.
EMPTY_DIRS = (
    "papers",
    "content/drafts",
    "content/dossiers",
    "content/specs",
    "content/review",
    "content/rendered",
)

TOP_LEVEL = frozenset({CONFIG_DEST, *COPY_VERBATIM, "papers", "content"})

# Kept separate from the module docstring above and passed to argparse
# rather than `description=__doc__`, for the reason tests/test_cli_help_is_short.py
# pins on every other entry point in this package (#152): the docstring
# is design commentary aimed at a reader of the file, and printing forty
# lines of it before the flags buries the two lines that answer "how do
# I run this".
DESCRIPTION = (
    "Scaffold a project directory -- config.toml, .claude/, "
    "papers/, content/, assets/ and the prose docs."
)

# What scripts/release.py's zip ships (every git-tracked top-level entry
# minus its own EXCLUDE_TOP_LEVEL) that `init` deliberately does not
# scaffold, each for a stated reason -- see the module docstring for why
# this has to be a named set rather than an unremarked gap.
DELIBERATE_DIFFERENCES = frozenset(
    {
        # Dev/checkout-only machinery: does something only inside a git
        # checkout of this repository, or names a version/lock fact a `pip
        # install` resolves independently at install time.
        "poetry.lock",
        "poetry.toml",
        "pyproject.toml",
        "scripts",
        "docker",
        "mkdocs.yml",
        ".gitattributes",
        ".markdownlint.yaml",
        ".pylintrc",
        ".opencodereview",
        # The C1/C2 debt register. It ships, because someone unzipping a
        # release to work on the pipeline needs it -- `scripts/code_standards.py`
        # and `tests/test_code_standards_scan.py` both read it. It is not
        # scaffolded, for the reason every entry in this block shares:
        # an `init`-ed project has no `chitragupta/` or `scripts/` tree
        # whose sizes it could describe. The size hook `.claude/` does
        # scaffold is inert there for the same reason, and says so.
        "code-standards-register.toml",
        # The git pre-commit hook and its directory. It ships for the same
        # reason `scripts/` does -- someone unzipping a release to work on
        # the pipeline can use it -- and `init` does not scaffold it: an
        # `init`-ed project has no workflows to lint, and pointing a
        # drafting user's `core.hooksPath` at a hook they never asked for
        # would be a surprising thing for a scaffolder to do.
        "git-hooks",
        # Audience is someone changing chitragupta's own source, which a
        # pip-installed, init-ed project does not have -- #267 gives
        # CLAUDE.md's routing table the "no src/ to change" row this implies.
        "DEVELOPER-AGENTS.md",
        "DEVELOPER.md",
        "DOCKER-DEVELOPER.md",
        # About the chitragupta *software itself*, not the user's own project.
        "LICENSE",
        "CITATION.cff",
        # The source code -- already installed via pip, not copied a second
        # time into the user's project directory.
        "chitragupta",
    }
)


def _write_one(src: Path, dst: Path, *, force: bool, dry_run: bool) -> str:
    """One file: create, report-as-existing, or (with force) overwrite.

    Never destroys silently -- an existing file survives untouched
    unless `force` names it in the same line it overwrites.
    """
    if not dst.exists():
        verb = "would create" if dry_run else "created"
        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        return f"{verb}: {dst}"
    if not force:
        return f"exists, unchanged: {dst}"
    verb = "would overwrite" if dry_run else "overwrote"
    if not dry_run:
        shutil.copy2(src, dst)
    return f"{verb}: {dst}"


def _write_tree(src: Path, dst: Path, *, force: bool, dry_run: bool) -> list[str]:
    """`src` copied file by file, not directory by directory.

    A recursive overwrite-the-whole-tree copy would delete a user's own
    file under, say, `.claude/skills/` the moment `--force` is used --
    exactly what "never destroys" rules out. Each file gets its own
    create/exists/overwrite verdict instead.

    `__pycache__` is skipped -- not disk cruft from a checkout, but
    something `pip install` itself creates: it byte-compiles every `.py`
    file it installs, including `.claude/hooks/*.py`, which sit in
    site-packages as data rather than as part of the `chitragupta`
    package. Measured against an installed wheel (#263's own trap):
    without this filter, the very first `init` run ships a fresh
    `__pycache__/*.pyc` into the user's project.
    """
    if src.is_file():
        return [_write_one(src, dst, force=force, dry_run=dry_run)]
    return [
        _write_one(f, dst / f.relative_to(src), force=force, dry_run=dry_run)
        for f in sorted(src.rglob("*"))
        if f.is_file() and "__pycache__" not in f.parts
    ]


def _write_empty_dir(dst: Path, *, dry_run: bool) -> str:
    if dst.is_dir():
        return f"exists, unchanged: {dst}/"
    if not dry_run:
        dst.mkdir(parents=True)
    return f"{'would create' if dry_run else 'created'}: {dst}/"


def scaffold(dest: Path, *, force: bool = False, dry_run: bool = False) -> list[str]:
    """Write (or, with `dry_run`, describe) the project scaffold into `dest`.

    Returns the report `main()` prints -- in every mode, including
    `dry_run` -- so `--dry-run` prints exactly the tree a real run
    writes, from this one manifest, rather than a second and
    hand-maintained listing of it.
    """
    missing = [
        name for name in (*COPY_VERBATIM, CONFIG_EXAMPLE) if not (SOURCE_ROOT / name).exists()
    ]
    if missing:
        # Refused before anything is written (#509/m-37). `_write_tree`
        # on an absent source `rglob`s nothing and returns `[]`, so a
        # wheel built without `.claude/` scaffolded a project with no
        # citation-gate hook, printed a report that simply did not
        # mention it, and exited 0. The one thing a scaffold must not do
        # is report success for a project missing the gate -- and a
        # partial scaffold is worse than none, since the user has no
        # reason to look.
        raise ScaffoldSourceMissing(
            f"this installation is missing {', '.join(missing)}, so the scaffold "
            f"it would write is incomplete. Expected under {SOURCE_ROOT}. "
            "Reinstall chitragupta-cli, or run from a git checkout."
        )

    report = []
    for name in COPY_VERBATIM:
        report.extend(_write_tree(SOURCE_ROOT / name, dest / name, force=force, dry_run=dry_run))
    report.append(
        _write_one(SOURCE_ROOT / CONFIG_EXAMPLE, dest / CONFIG_DEST, force=force, dry_run=dry_run)
    )
    for rel in EMPTY_DIRS:
        report.append(_write_empty_dir(dest / rel, dry_run=dry_run))
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog_for("init"), description=DESCRIPTION)
    parser.add_argument(
        "dir", nargs="?", default=".", type=Path, help="Where to write the project (default: .)"
    )
    parser.add_argument(
        "--force", action="store_true", help="Overwrite existing files, named one by one"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print the tree that would be written; write nothing"
    )
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    try:
        report = scaffold(args.dir, force=args.force, dry_run=args.dry_run)
    except ScaffoldSourceMissing as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    for line in report:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
