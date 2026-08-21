#!/usr/bin/env python3
"""Builds a distributable release/chitragupta-<version>.zip.

Version comes from pyproject.toml's [tool.poetry].version -- the single
source of truth for it (see that file's own comments on why Poetry here
is a lockfile/venv manager only, not a publishing mechanism; this script
doesn't change that, it just reads the version Poetry itself considers
current).

Bundles every git-tracked file (`git ls-files`, so .gitignore's exclusions
-- content/parsed/, papers/bibliography.bib, .venv-full/, etc. -- are
already handled) except:

- this repo's own machinery, which does something only in a git checkout
  of it: tests/, bench/ (parser wall-clock measurement against *this*
  host's own bib corpus, which a release consumer doesn't have), and
  .github/ + .gitignore (CI config, git config and issue/PR templates).

  **Every prose document ships** -- README.md, docs/, SOUL.md, AGENTS.md,
  DEVELOPER-AGENTS.md and DEVELOPER.md -- as does `.claude/` and its genre
  skills. Those skills cite AGENTS.md by name for the citekey invariant,
  and the docs cross-reference each other freely, so excluding any one of
  them leaves dangling references in the rest. Someone who unzips a
  release to work on the pipeline needs the developer docs as much as
  someone who cloned it.
- content/ and papers/, which do have a handful of git-tracked files
  despite mostly being gitignored (e.g. content/drafts/*.md example
  drafts) -- per-host example/personal data that shouldn't ship as
  someone else's example in a fresh release. Shipped as empty placeholder
  directories instead of omitted outright, so config.toml's default paths
  (content.dir, bib.path's parent) still resolve to something that exists
  before a first `sync` run populates them.

Also generates README.pypi.md -- README.md with every relative link and
image rewritten to an absolute GitHub URL, pinned to this release's tag.
README.md itself stays relative-link-friendly on purpose: GitHub and the
mkdocs site (mkdocs.yml's `docs_dir: .`) are built specifically so the
same relative paths resolve identically on both, and rewriting them
there is "a thing that can be wrong" that file's own comment already
rejects for that exact reason. PyPI's renderer has no knowledge of the
GitHub repo at all, so a relative `docs/GENRE.md` link or an
`<img src="docs/logo.svg">` that works on both of those just 404s there
-- confirmed against the real, already-published chitragupta-cli
6.7.0/6.8.0/6.8.1. README.pypi.md is `pyproject.toml`'s `readme`, is
never git-tracked (.gitignore), and this is the one place it is written.

Stdlib only (tomllib, zipfile, shutil, re) -- runs with bare `python3`,
no venv, same as citation_gate.py/references.py. Needs `git` on PATH to
list tracked files; nothing else.

Usage:
    python3 scripts/release.py
"""

import re
import shutil
import subprocess
import tomllib
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Developer-only / this-repo-only material a release doesn't need to ship
# -- everything else git-tracks is fair game (see module docstring).
EXCLUDE_TOP_LEVEL = {
    "tests",
    ".github",
    ".gitignore",
    "bench",
    # Implementation plans for this repository's own PRs
    # (docs/FEATURE-ROADMAP.md is the shipped roadmap; these are the
    # working documents behind individual items). Developer-only
    # material in the same sense as `tests/` and `bench/`: a release
    # consumer working on the pipeline needs DEVELOPER-AGENTS.md and the
    # roadmap, not the half-finished plan for chitragupta PR #291. They
    # are also the one prose directory that is deliberately allowed to go
    # stale, which is the opposite of the contract every shipped document
    # here is held to.
    "plans",
    # CI config that happens to live at the root rather than under
    # .github/: it names *this* repository's SonarQube project key and
    # organisation, so in an unzipped release it is either inert or
    # actively wrong -- a scan run from there would report someone else's
    # code against prasadtalasila_chitragupta.
    "sonar-project.properties",
    # Same category, and the one root-level CI file that is worse than
    # inert in an unzipped release. It holds `after_n_builds: 2`, which is
    # a fact about *this* repository's two-leg test matrix; carried into a
    # repository whose CI makes one upload, it leaves every Codecov status
    # waiting for a second that never comes. The file's own comment names
    # that failure mode as the accepted cost here -- exporting it to
    # someone who never chose it is a different thing.
    "codecov.yml",
    # Same category again: the coverage config CI's Windows leg uses to
    # exclude the pandoc/pdflatex/pdftotext call sites its ~30
    # self-skipping tests would otherwise leave uncovered
    # (docs/TECHNICAL-DEBT.md #3.6). Meaningful only alongside this
    # repository's own test suite, which a release doesn't ship either.
    "coveragerc-windows.toml",
}

# Ships as an empty placeholder directory instead of its tracked contents
# -- see module docstring.
EMPTY_TOP_LEVEL = {"content", "papers"}


def _poetry_table() -> dict:
    with open(REPO_ROOT / "pyproject.toml", "rb") as f:
        return tomllib.load(f)["tool"]["poetry"]


def get_version() -> str:
    return _poetry_table()["version"]


def get_repository() -> str:
    return _poetry_table()["repository"]


def tracked_files() -> list[str]:
    """Every git-tracked path relative to REPO_ROOT, minus EXCLUDE_TOP_LEVEL
    and EMPTY_TOP_LEVEL (the latter ships as an empty directory instead --
    see build_release)."""
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "-z"],
        capture_output=True, check=True,
    )
    paths = [p for p in result.stdout.decode().split("\0") if p]
    skip = EXCLUDE_TOP_LEVEL | EMPTY_TOP_LEVEL
    return [p for p in paths if p.split("/", 1)[0] not in skip]


def build_release() -> tuple[Path, int]:
    version = get_version()
    name = f"chitragupta-{version}"
    release_dir = REPO_ROOT / "release"
    staging = release_dir / name

    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    paths = tracked_files()
    for rel_path in paths:
        src = REPO_ROOT / rel_path
        dst = staging / rel_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    for empty_dir in EMPTY_TOP_LEVEL:
        (staging / empty_dir).mkdir(parents=True, exist_ok=True)

    zip_path = release_dir / f"{name}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(staging.rglob("*")):
            if f.is_file():
                zf.write(f, f.relative_to(release_dir))
            elif f.is_dir() and not any(f.iterdir()):
                # zipfile.write() only carries a directory into the archive
                # via a file inside it -- EMPTY_TOP_LEVEL's placeholders
                # have none, so they need an explicit directory entry.
                zf.writestr(zipfile.ZipInfo(f"{f.relative_to(release_dir)}/"), "")

    shutil.rmtree(staging)
    return zip_path, len(paths)


def render_pypi_readme(version: str) -> str:
    """README.md, with every relative link and image rewritten to an
    absolute GitHub URL pinned to `v<version>` -- see the module
    docstring for why README.md itself is not the thing to change.
    """
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    repository = get_repository()
    tag = f"v{version}"
    blob = f"{repository}/blob/{tag}/"
    raw = repository.replace("github.com", "raw.githubusercontent.com") + f"/{tag}/"

    # <img src="..."> / <source srcset="..."> in the centred logo block,
    # the only raw-HTML asset references in the file.
    text = re.sub(r'(src|srcset)="(?!https?://)([^"]+)"',
                  lambda m: f'{m.group(1)}="{raw}{m.group(2)}"', text)

    # Markdown [text](target) links -- skip ones already absolute and
    # the in-page #anchor ones (the table of contents).
    def _rewrite_link(match: "re.Match") -> str:
        label, target = match.group(1), match.group(2)
        if target.startswith(("http://", "https://", "#")):
            return match.group(0)
        return f"[{label}]({blob}{target})"

    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _rewrite_link, text)


def main() -> int:
    version = get_version()
    zip_path, n_files = build_release()
    print(f"Release archive: {zip_path} ({n_files} files)")
    pypi_readme = REPO_ROOT / "README.pypi.md"
    pypi_readme.write_text(render_pypi_readme(version), encoding="utf-8")
    print(f"PyPI readme: {pypi_readme}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
