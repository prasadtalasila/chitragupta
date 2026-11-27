"""`chitragupta init [DIR] [--force] [--dry-run] [--agent NAME]`: scaffold a project directory.

A wheel installs modules but no `config.toml`, skills, hooks (so no
citation gate), `content/` or `AGENTS.md`; this writes the same project
directory the release zip ships. It reads from `SOURCE_ROOT`, the seam
`config.shipped()` already uses. The copied `assets/` are for finding
and editing; the pipeline keeps reading the installed copies until
`config.toml` is repointed (docs/CONFIG.md).

`TOP_LEVEL` is an allowlist, `scripts/release.py`'s `EXCLUDE_TOP_LEVEL` a
denylist, and two such lists drift (#208). `DELIBERATE_DIFFERENCES` is
the named set `tests/test_init.py` checks both against.
"""

import argparse
import re
import shutil
import sys
from pathlib import Path

from chitragupta.developer_skills import developer_skills, is_developer_only
from chitragupta.progname import prog_for
from chitragupta.help_format import ClickParser

# Not imported from chitragupta.config: it raises without a `config.toml`,
# which is exactly the state `init` exists to fix.
PACKAGE_ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = PACKAGE_ROOT.parent

# Copied verbatim, and each needed: skills cite AGENTS.md, .claude/
# registers the gate hooks. assets/ is for the user to edit (nothing reads
# the copy); DOCKER.md must reach pip users though `docker/` is not copied.
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


# Each harness's trees on top of the shared core (#812, #900). `.claude/`
# goes to every harness: it holds the hook scripts all three launch. The
# skill copies are kept in step by tests/test_skill_harness_copies.py.
AGENT_TREES = {"claude": (), "codex": (".codex", ".agents"), "opencode": (".opencode",)}
DEFAULT_AGENTS = ("claude",)


class ScaffoldSourceMissing(Exception):
    """An installation that cannot write a complete scaffold -- see
    `scaffold`, which refuses rather than writing a partial one."""


class ScaffoldTargetUnsafe(Exception):
    """A target holding a `chitragupta` import the hooks would pick up."""


# A hook's child runs from the project root, first on `sys.path`, so
# either name would shadow the installed package (#822). The hooks also
# refuse it (.claude/hooks/safe_path.py); this is the louder half.
SHADOWING_NAMES = ("chitragupta", "chitragupta.py")


# Scaffolded prose says `python -P`, so a `chitragupta/` planted in the
# project after `init` is never imported in place of the install (#891).
# A checkout keeps plain `-m`. HOOKS.md and PACKAGING.md explain `-m`'s
# search order and CLI.md is the verbatim reference, so they stay as-is.
KEEPS_PLAIN_M = ("docs/CLI.md", "docs/HOOKS.md", "docs/PACKAGING.md")
MODULE_FORM = re.compile(r"\b(python3?)(\s+)(-m\s+chitragupta\b|-c\s)")


# config.toml is gitignored per-user data, so init writes the user's copy
# from the tracked template, as `cp config.toml.example config.toml` does.
CONFIG_EXAMPLE = "config.toml.example"
CONFIG_DEST = "config.toml"

# `[style].acronyms` ships pointing here with acronym expansion on, so
# without the file a live setting reads nothing. A seed, not a vendored
# asset: the vendored floor stays in the package and is merged under it.
ACRONYMS_EXAMPLE = "assets/style/acronyms.toml.example"
ACRONYMS_DEST = "content/acronyms.toml"

# So config.toml's default paths exist before a first `corpus sync`.
EMPTY_DIRS = (
    "papers",
    "content/drafts",
    "content/dossiers",
    "content/specs",
    "content/review",
    "content/rendered",
)

# Everything a scaffold can write, with every harness named. The default,
# `--agent claude`, writes all of it bar the other harnesses' trees.
TOP_LEVEL = frozenset(
    {CONFIG_DEST, *COPY_VERBATIM, *(t for trees in AGENT_TREES.values() for t in trees)}
    | {"papers", "content"}
)

# Not `description=__doc__` (#152, tests/test_cli_help_is_short.py): the
# docstring is design commentary and would bury the flags.
DESCRIPTION = (
    "Scaffold a project directory -- config.toml, .claude/, "
    "papers/, content/, assets/, the prose docs, and each --agent's launcher."
)

# What release.py's zip ships that `init` deliberately does not scaffold
# (see the module docstring).
DELIBERATE_DIFFERENCES = frozenset(
    {
        # Dev/checkout-only machinery, or version facts pip resolves itself.
        "uv.lock",
        "pyproject.toml",
        "scripts",
        "docker",
        "mkdocs.yml",
        ".gitattributes",
        ".markdownlint.yaml",
        ".pylintrc",
        ".opencodereview",
        # Ships for pipeline developers; an `init`-ed project has no
        # `chitragupta/` or `scripts/` whose sizes it could describe.
        "code-standards-register.toml",
        # An `init`-ed project has no workflows to lint, and setting a
        # drafting user's `core.hooksPath` would be a surprise.
        "git-hooks",
        # For changing chitragupta's own source, which an init-ed project
        # lacks (#267).
        "DEVELOPER-AGENTS.md",
        "DEVELOPER.md",
        "DOCKER-DEVELOPER.md",
        # About the chitragupta *software itself*, not the user's own project.
        "LICENSE",
        "CITATION.cff",
        # Already installed via pip.
        "chitragupta",
    }
)


def gets_dash_p(src: Path) -> bool:
    """Is `src` prose whose commands `_copy` rewrites (`KEEPS_PLAIN_M`)?"""
    return src.suffix == ".md" and src.relative_to(SOURCE_ROOT).as_posix() not in KEEPS_PLAIN_M


def _copy(src: Path, dst: Path) -> None:
    """`shutil.copy2`, with a prose file's `python -m`/`-c` made `-P`.

    Bytes in and out, so a file's own line endings and encoding survive;
    the pattern is ASCII, so it cannot split a multi-byte character.
    """
    shutil.copy2(src, dst)
    if gets_dash_p(src):
        text = dst.read_bytes().decode("utf-8")
        dst.write_bytes(MODULE_FORM.sub(r"\1\2-P \3", text).encode("utf-8"))


def _write_one(src: Path, dst: Path, *, force: bool, dry_run: bool) -> str:
    """One file: create, report-as-existing, or (with force) overwrite.

    An existing file survives unless `force` names it as it overwrites.
    """
    if not dst.exists():
        verb = "would create" if dry_run else "created"
        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            _copy(src, dst)
        return f"{verb}: {dst}"
    if not force:
        return f"exists, unchanged: {dst}"
    verb = "would overwrite" if dry_run else "overwrote"
    if not dry_run:
        _copy(src, dst)
    return f"{verb}: {dst}"


def _write_tree(src: Path, dst: Path, *, force: bool, dry_run: bool) -> list[str]:
    """`src` copied file by file, so `--force` never deletes a user's own
    file in a tree.

    `__pycache__` is skipped: `pip install` byte-compiles
    `.claude/hooks/*.py` in site-packages (#263).
    """
    if src.is_file():
        return [_write_one(src, dst, force=force, dry_run=dry_run)]
    # Developer-only skills (#1188), and `.claude/worktrees/`, which an
    # editable install's checkout holds on disk.
    skip = developer_skills(SOURCE_ROOT) | {".claude/worktrees"}
    return [
        _write_one(f, dst / f.relative_to(src), force=force, dry_run=dry_run)
        for f in sorted(src.rglob("*"))
        if f.is_file()
        and "__pycache__" not in f.parts
        and not is_developer_only(f.relative_to(SOURCE_ROOT).as_posix(), skip)
    ]


def _write_empty_dir(dst: Path, *, dry_run: bool) -> str:
    if dst.is_dir():
        return f"exists, unchanged: {dst}/"
    if not dry_run:
        dst.mkdir(parents=True)
    return f"{'would create' if dry_run else 'created'}: {dst}/"


def scaffold(
    dest: Path, *, force: bool = False, dry_run: bool = False, agents=DEFAULT_AGENTS
) -> list[str]:
    """Write (or, with `dry_run`, describe) the project scaffold into `dest`.

    Returns the report in every mode, so `--dry-run` prints exactly the
    tree a real run writes.
    """
    trees = list(dict.fromkeys(tree for agent in agents for tree in AGENT_TREES[agent]))
    missing = [
        name
        for name in (*COPY_VERBATIM, *trees, CONFIG_EXAMPLE, ACRONYMS_EXAMPLE)
        if not (SOURCE_ROOT / name).exists()
    ]
    if missing:
        # Refused before anything is written (#509): a scaffold missing the
        # gate hook must never report success, and a partial one is worse
        # than none.
        raise ScaffoldSourceMissing(
            f"this installation is missing {', '.join(missing)}, so the scaffold "
            f"it would write is incomplete. Expected under {SOURCE_ROOT}. "
            "Reinstall chitragupta-cli, or run from a git checkout."
        )
    shadowing = [name for name in SHADOWING_NAMES if (dest / name).exists()]
    if shadowing:
        # Ahead of `force` and `dry_run`: a dry run must not print a tree
        # the real run refuses.
        raise ScaffoldTargetUnsafe(
            f"{dest} already contains {', '.join(shadowing)}, which the hooks this "
            "would install could import in place of the installed chitragupta. "
            "Move it aside, or scaffold into another directory."
        )

    report = []
    for name in (*COPY_VERBATIM, *trees):
        report.extend(_write_tree(SOURCE_ROOT / name, dest / name, force=force, dry_run=dry_run))
    report.append(
        _write_one(SOURCE_ROOT / CONFIG_EXAMPLE, dest / CONFIG_DEST, force=force, dry_run=dry_run)
    )
    report.append(
        _write_one(
            SOURCE_ROOT / ACRONYMS_EXAMPLE, dest / ACRONYMS_DEST, force=force, dry_run=dry_run
        )
    )
    for rel in EMPTY_DIRS:
        report.append(_write_empty_dir(dest / rel, dry_run=dry_run))
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = ClickParser(prog=prog_for("init"), description=DESCRIPTION)
    parser.add_argument(
        "dir", nargs="?", default=".", type=Path, help="Where to write the project (default: .)"
    )
    parser.add_argument(
        "--force", action="store_true", help="Overwrite existing files, named one by one"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print the tree that would be written; write nothing"
    )
    parser.add_argument(
        "--agent",
        action="append",
        choices=sorted(AGENT_TREES),
        dest="agents",
        help="Harness to set up (default: claude); repeat for several",
    )
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    try:
        report = scaffold(
            args.dir,
            force=args.force,
            dry_run=args.dry_run,
            agents=tuple(args.agents or DEFAULT_AGENTS),
        )
    except (ScaffoldSourceMissing, ScaffoldTargetUnsafe) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    for line in report:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
