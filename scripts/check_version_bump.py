#!/usr/bin/env python3
"""Fail a PR whose version bump has silently gone missing (#212).

Every PR must raise `[tool.poetry].version`, because `release.yml`
verifies the pushed tag against that value on `main`. Two branches
therefore always touch the same line, and the two ways that goes wrong are
not equally visible:

- **Different numbers collide loudly.** Git reports a merge conflict, and
  it is fixed in a minute.
- **The same number merges silently.** Git sees a byte-identical line and
  takes it without a word. The branch lands on `main` still claiming a
  version that has already been spent, the bump is gone, and nothing says
  so until `release.yml` refuses a tag with an error that names neither
  the collision nor the PR that caused it.

That happened three times on 2026-08-15, twice silently, and once
(#209/#205) it reached `main` and needed a follow-up PR to correct.

**The primary check is against `main`, not against the tags**, and this is
the part worth reading before changing anything here. A tag-existence test
looks like the obvious check and is blind to a real window: between a PR
merging and its tag being pushed, the version is spent and no tag records
it. On this repository that window has been as short as 34 seconds and, at
the other extreme, lasts as long as it takes a person to reach step 8 of
DEVELOPER-AGENTS.md's cycle. Comparing against `main` needs no tag to
exist, so it closes that window; the tag check is kept as a cheap second
line for the odd state where a tag runs ahead of `main`.

Ordering is numeric, not lexical, because `5.9.0` sorts above `5.10.0` as
a string and that is precisely the comparison this has to get right.
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
import subprocess
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def parse(version: str) -> tuple:
    """`version` as a comparable tuple of integers.

    A component that is not a plain integer keeps its string form and
    sorts after the numbers, which is enough for the pre-release suffixes
    this project does not currently use but might. The point is only that
    two versions order correctly, never that this reimplements PEP 440.
    """
    parts = []
    for chunk in version.strip().split("."):
        parts.append((0, int(chunk)) if chunk.isdigit() else (1, chunk))
    return tuple(parts)


def version_in(text: str) -> str:
    """The `[tool.poetry].version` in a pyproject.toml's contents."""
    return tomllib.loads(text)["tool"]["poetry"]["version"]


def problems(current: str, base: str, tags: "list[str] | tuple[str, ...]") -> list[str]:
    """Every reason this version may not be merged, in the order to read them.

    Returns an empty list when the bump is sound. Separated from the git
    plumbing below so the rules can be tested without a repository.
    """
    found = []
    if parse(current) <= parse(base):
        found.append(
            f"pyproject.toml says {current}, and main is already at {base}. "
            "Another PR took that number while this branch was open -- an "
            "identical version line merges without a conflict, so the bump "
            "silently disappeared. Raise it above main's and re-run the "
            "checks (DEVELOPER-AGENTS.md, 'Shipping a code change')."
        )
    if f"v{current}" in tags:
        found.append(
            f"pyproject.toml says {current}, which is already released as "
            f"v{current}. Whatever this branch ships, it is not that."
        )
    return found


def on_pypi(version: str, fetch) -> "bool | None":
    """Whether `version` is already published as chitragupta-cli.

    True, False, or **None for "could not tell"** -- the three cases are
    kept distinct on purpose. A published version is *immutable*: PyPI
    refuses a re-upload even after a deletion, and yanking does not free
    the number. So this is the one release check that has to block rather
    than warn, and equally the one that must never block on a network
    hiccup. A `None` is reported as a warning; only a definite `True`
    fails the build.

    `fetch` is injected rather than called directly so the rule is
    testable without reaching the network -- the same separation
    `problems()` already has from the git plumbing.
    """
    try:
        payload = fetch(f"https://pypi.org/pypi/chitragupta-cli/{version}/json")
    except Exception:  # noqa: BLE001 -- any transport failure means "unknown"
        return None
    if payload is None:
        return None
    return payload is not False


def _fetch_json(url: str):
    """`False` for a 404, the decoded body otherwise, None if unreadable.

    A 404 is the *answer* here -- the version is not on PyPI -- not a
    failure, so it is distinguished from every other error rather than
    lumped in with them.
    """
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return False if exc.code == 404 else None
    except (urllib.error.URLError, ValueError, TimeoutError):
        return None


def unreleased(base: str, tags: "list[str] | tuple[str, ...]") -> "str | None":
    """A warning when the base branch's version was never tagged.

    Deliberately a warning and not a problem, because the condition is
    *legitimate and transient*: the version bump lands in the PR and the
    tag is pushed afterwards, so for a while after every merge main
    carries a version with no tag. Failing on it would fail every merge.

    What it catches is the same state *persisting*. `release.yml` fires
    on a pushed `v*` tag and nothing else, so a version that reaches main
    and never gets tagged simply never becomes a release -- silently, and
    for as long as nobody looks at the releases page. That is not
    hypothetical: v5.40.1, v5.41.0, v6.0.0, v6.1.0 and v6.2.0 all reached
    main and none of them was released until the gap was noticed by eye,
    five versions later.

    Surfaced on every pull request rather than on the push that causes
    it, because a PR is the thing a person is already reading. One
    unreleased version is business as usual; seeing the same one quoted
    back at you across several PRs is the signal.
    """
    if f"v{base}" in tags:
        return None
    return (
        f"main is at {base}, and there is no v{base} tag -- so that "
        "version has never been released and its archive does not exist. "
        "release.yml runs on a pushed tag and on nothing else. If the "
        "release for it is still owed, cut it: `git tag -a v"
        + base
        + " <commit> -m v"
        + base
        + " && git push origin v"
        + base
        + "` "
        "(DEVELOPER-AGENTS.md, 'Versioning and releases')."
    )


def _git(*args: str) -> str:
    """Git's stdout, decoded as UTF-8 rather than as the host's locale.

    `text=True` alone decodes with `locale.getpreferredencoding()`, which
    is cp1252 on CI's Windows leg -- and this reads a *file* out of git,
    not just tag names, so a non-ASCII byte anywhere in `pyproject.toml`
    would mangle or raise there and nowhere else.
    """
    return subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True, encoding="utf-8", cwd=REPO_ROOT
    ).stdout


# `fetch` is injected here for the same reason `on_pypi()`'s is (#425).
# Without it, the only ways to drive `main()` off the network were
# `--offline`, which skips the PyPI rule rather than exercising it, and
# patching `on_pypi` itself, which stubs out the code under test. Seven
# tests took neither and requested a real URL on every full-suite run;
# one of them asserts that no `::warning::` is emitted, and a transport
# hiccup produces exactly that -- an intermittent red that reads as a
# broken branch. The default is pinned by a test so it cannot be
# swapped for a fake and quietly disarm the check in CI.
#
# Stated here rather than in a docstring because `main()` sits exactly
# on C1's 25-statement limit and a docstring is an `ast.Expr` -- it
# would count as the 26th. CODE-STANDARDS.md's counting rule is what
# makes this the free place to put it: a `#` comment is charged by
# neither C1 nor C2.
def main(argv: "list[str] | None" = None, fetch=_fetch_json) -> int:
    parser = argparse.ArgumentParser(
        prog="python scripts/check_version_bump.py",
        description="Fail when a PR's version bump has been lost to a collision.",
    )
    parser.add_argument(
        "--base-ref",
        default="origin/main",
        help="What this branch must out-rank (default origin/main)",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Skip the PyPI check (no network in this environment)",
    )
    args = parser.parse_args(argv)

    # The working tree is the *merge* commit on a pull_request event, so
    # its pyproject is already the merged value; reading it twice would
    # compare a file with itself. The base side has to come out of git.
    current = version_in((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    try:
        base = version_in(_git("show", f"{args.base_ref}:pyproject.toml"))
        tags = _git("tag", "--list").split()
    except subprocess.CalledProcessError:
        # Almost always a shallow clone that never fetched the base ref.
        # Say that, rather than letting a CalledProcessError traceback
        # stand in for it -- this runs in CI, where the traceback would be
        # the whole of what a reader sees.
        print(
            f"::error::cannot read {args.base_ref}. Fetch it first: "
            "`git fetch --depth=1 origin main`, and the tags with "
            "`+refs/tags/*:refs/tags/*`.",
            file=sys.stderr,
        )
        return 1

    # Emitted before the errors and regardless of them: it is about the
    # *base* branch, so it is equally true whether or not this branch's
    # own bump is sound, and it must not change the exit code.
    owed = unreleased(base, tags)
    if owed:
        print(f"::warning::{owed}", file=sys.stderr)

    # A published version can never be reused, so this blocks -- but a
    # network failure must not. See on_pypi() for why the three outcomes
    # are kept distinct.
    published = on_pypi(current, fetch) if not args.offline else None
    if published is True:
        print(
            f"::error::{current} is already published as chitragupta-cli "
            f"{current} on PyPI, and a published version can never be "
            "re-uploaded -- not after a deletion, and yanking does not free "
            "the number. Choose the next version.",
            file=sys.stderr,
        )
        return 1
    if published is None and not args.offline:
        print(
            "::warning::could not reach PyPI to check whether "
            f"{current} is already published; continuing.",
            file=sys.stderr,
        )

    found = problems(current, base, tags)
    for problem in found:
        print(f"::error::{problem}", file=sys.stderr)
    if not found:
        print(f"version {current} out-ranks {args.base_ref}'s {base}, and is untagged.")
    return 1 if found else 0


def blocks_a_merge() -> bool:
    """Whether a merge must not proceed, re-checked against a freshly
    fetched `main`. Called by `scripts/merge_pr.py` immediately before
    `gh pr merge`.

    Nothing new is checked here -- it is `main()` above, the same rules
    `ci.yml` runs, and the `git fetch` is the whole of what this adds.
    Those rules read `origin/main` and the tag list out of local git,
    and the collision they catch is caused by a merge or a tag landing
    *inside* the window between a branch's last CI run and its merge --
    so an unfetched read looks at a snapshot from before the thing it is
    looking for. On #560 the colliding tag was created 18 seconds before
    the merge ran and was not in the local list.

    `--offline` skips only the PyPI rule, which is not what this is for
    and would put a network round-trip in front of every merge.

    **Exit 1 blocks, whatever produced it** -- including a base ref that
    cannot be read at all, which `main()` also exits 1 for. That is the
    right way round here, unlike the caution `on_pypi` needs: a merge is
    itself a network operation, so a state where this cannot tell is one
    where `gh pr merge` was not going to work either, and stopping costs
    nothing. Anything that is not 1 proceeds.

    It reads the caller's own `pyproject.toml`, so `merge_pr.py` has to
    be run from the branch being merged.

    DEVELOPER-AGENTS.md's "Merging" section owns the rest -- why this is
    not a duplicate of the CI run, why the cycle's step 8 cannot close
    the window, and why there is no override.
    """
    subprocess.run(["git", "fetch", "origin", "--tags", "--quiet"], check=False, cwd=REPO_ROOT)
    if main(["--offline"]) != 1:
        return False
    print(
        "Refusing to merge: the version bump is no longer sound against "
        "main. Raise pyproject.toml's version, push, and re-run -- there "
        "is deliberately no override, since bumping is the fix either way."
    )
    return True


if __name__ == "__main__":
    raise SystemExit(main())
