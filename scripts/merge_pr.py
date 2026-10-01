#!/usr/bin/env python3
"""Check a PR's squash-commit body against the documented format, and merge
the PR with it (#357, #827).

The author writes the body in the PR description's `## Commit message`
section, as one ` ```text ` fence. This script accepts that text unchanged
or refuses it, naming the line; it never strips, joins or rewrites, and
nothing else in the description reaches the commit. `--check` is the same
check without a merge, run on every description edit by
`.github/workflows/commit-message.yml`.

Why the body is written rather than assembled (the scraper this replaced
duplicated bullets and copied trailers and escape sequences into `main`),
why `CommitBody` is an allowlist grammar rather than a set of filters, and
why no repository setting can do any of this: DEVELOPER-AGENTS.md's
"Commit messages" and "Merging", and `plans/827-commit-message-format.md`.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# git's own convention for a body line: `git log` indents the body by
# four, so 72 still fits an 80-column terminal. Counted in code points,
# not display cells -- a full-width character displays twice as wide, and
# measuring that (unicodedata.east_asian_width) is more than an
# English-language repository needs. Whoever hits it can wrap earlier.
MAX_LINE = 72

_SECTION = "commit message"
_OPEN, _CLOSE = "```text\n", "\n```"
# Empty on purpose: pre-filled example text would pass the check if
# pasted unchanged, and land in main as the commit body.
_SKELETON = "## Commit message\n\n```text\n```"

# GitHub's closing-keyword vocabulary, in every form it accepts, followed
# by an issue reference in each form it accepts: `#N`, `owner/repo#N` and
# an issue URL. An optional colon after the keyword (`Fixes: #12`)
# closes too. Deliberately not a bare `#\d+`: "the drift in #421" is an
# ordinary cross-reference, closes nothing, and is fine anywhere.
_CLOSING_RE = re.compile(
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?):?\s+"
    r"(?:[\w.-]+/[\w.-]+)?(?:#\d+|https://github\.com/[\w.-]+/[\w.-]+/issues/\d+)",
    re.IGNORECASE,
)


class FormatError(ValueError):
    """The body breaks the documented format; the message says where."""


class CommitBody:
    """A squash-commit body in DEVELOPER-AGENTS.md's format, validated on
    construction, so holding one is proof it conforms. A plain class, not
    a dataclass: the tests load this script by path without registering
    it in `sys.modules`, which `dataclasses` needs to resolve annotations.

    The grammar, one line at a time::

        body         := bullet+                  (no blank lines)
        bullet       := "- " Verb rest
        continuation := "  " non-space rest      (exactly two spaces)
        Verb         := letters only, first one upper-case

    plus, over the whole text: every line `str.isprintable()` (which
    already excludes C0/C1 controls, DEL, tabs, the bidi overrides and
    isolates, zero-width characters and non-ASCII spaces -- no
    hand-written code-point range to fall behind Unicode), every line at
    most `MAX_LINE` characters, and no closing keyword anywhere.

    The verb rule is what keeps trailers out: `Co-authored-by:`,
    `Signed-off-by:` and `Closes:` each carry a hyphen or a colon, so none
    is a word of letters. It does not check that the word is really a
    verb -- "Fix" against "Fixed" is a review question, and a word list
    would refuse real verbs nobody thought to add.

    Refuses on the *first* line that breaks a rule, naming the line
    number, the rule, and the line itself as `repr()` so an invisible
    character is visible in the message.
    """

    __slots__ = ("_text",)

    def __init__(self, text: str):
        if not text:
            raise FormatError("the commit message is empty: write at least one `- Verb ...` bullet")
        lines = text.split("\n")
        for number, line in enumerate(lines, start=1):
            problem = _line_problem(line, first=number == 1)
            if problem:
                raise FormatError(f"commit message line {number}: {problem}: {line!r}")
        keyword = _CLOSING_RE.search(text)
        if keyword:
            number = text.count("\n", 0, keyword.start()) + 1
            raise FormatError(
                f"commit message line {number}: carries the closing keyword "
                f"{keyword.group(0)!r}, which closes that issue when the commit "
                "lands on main. Put it in the PR description instead"
            )
        self._text = text

    def __str__(self) -> str:
        return self._text


def _line_problem(line: str, *, first: bool) -> "str | None":
    """Which rule `line` breaks, or None. `first` because a continuation
    line needs a bullet above it to continue."""
    if not line.isprintable():
        return "contains a control or invisible character"
    if len(line) > MAX_LINE:
        return f"is {len(line)} characters; wrap at {MAX_LINE}"
    if line.startswith("- "):
        verb = line[2:].split(" ", 1)[0]
        if not (verb.isalpha() and verb[0].isupper()):
            return "a bullet starts with a capitalised verb of letters only (Fix, Add, Remove)"
        return None
    if line.startswith("  ") and line[2:3] not in ("", " ") and not first:
        return None
    return "is neither a `- Verb ...` bullet nor a continuation indented two spaces"


def _sections(pr_body: str) -> "list[tuple[str, str]]":
    """Every `## `-headed section as `(heading, content)`, in body order."""
    parts = re.split(r"(?m)^## (.+)$", pr_body)
    return list(zip(parts[1::2], parts[2::2]))


def commit_body(pr_body: str) -> CommitBody:
    """The `CommitBody` in `pr_body`'s `## Commit message` section.

    The section is one ` ```text ` fence and nothing else, so finding the
    body needs no Markdown parser: prose beside the fence, a second
    fence, or another fence type is refused rather than guessed at.
    """
    # A description edited in GitHub's web editor can come back from the
    # API with CRLF line endings. The CR there is a line ending, not
    # content; any other CR stays, and the printable check refuses it.
    pr_body = pr_body.replace("\r\n", "\n")
    found = [
        content for heading, content in _sections(pr_body) if heading.strip().lower() == _SECTION
    ]
    if not found:
        raise FormatError(f"the PR description has no commit message. Add:\n\n{_SKELETON}")
    if len(found) > 1:
        raise FormatError("the PR description has more than one `## Commit message` section")
    section = found[0].strip()
    inner = section[len(_OPEN) : -len(_CLOSE)]
    if not (section.startswith(_OPEN) and section.endswith(_CLOSE)) or "```" in inner:
        raise FormatError(
            "the `## Commit message` section must hold exactly one ```text fence "
            "and nothing else; move any explanation to the Description"
        )
    return CommitBody(inner)


# The two spans GitHub does not parse a keyword inside: an inline code
# span and a fenced block. Both matter here for the same reason -- the
# mistake propagates by *quoting* a template or a plan, and a plan
# quoting the line a PR should carry is exactly where #430's came from.
_CODE_SPAN_RE = re.compile(r"```.*?```|`[^`]*`", re.DOTALL)


def inert_closing_keywords(pr_body: str) -> list[str]:
    """Closing keywords sitting inside a code span, which do nothing.

    GitHub links and closes an issue from `Closes #N` in a PR body, and
    silently does not when the same text is inside backticks or a fence.
    The failure has no symptom at merge time: the PR merges, the issue
    stays open, and the next person reads a closed PR beside an open
    issue and cannot tell whether that was deliberate.

    Seen on #430, which carried ``Closes #421.`` in backticks -- copied
    from `plans/f3-agenda-reviser.md`, which quotes that line as what PR
    1 should say. The issue had to be closed by hand afterwards.

    Reported rather than corrected, and never blocking: a PR
    legitimately quoting a keyword (this repository's own plans do) must
    still be mergeable. `--dry-run` is where a person sees this, which is
    the point at which it is still cheap to fix.
    """
    return [
        match.group(0)
        for span in _CODE_SPAN_RE.finditer(pr_body)
        for match in _CLOSING_RE.finditer(span.group(0))
    ]


def _gh(*args: str, input_text: "str | None" = None) -> str:
    """`gh`'s stdout, decoded as UTF-8 rather than the host locale -- the
    same reasoning `check_version_bump.py::_git` documents, and this reads
    PR titles and descriptions, which are not guaranteed ASCII."""
    result = subprocess.run(
        ["gh", *args],
        input=input_text,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=REPO_ROOT,
    )
    return result.stdout


def _pr_body(pr_number: int) -> str:
    return _gh("pr", "view", str(pr_number), "--json", "body", "--jq", ".body")


def _merge(pr_number: int, body: str) -> None:
    """`gh pr merge --squash`, with the checked body on stdin.

    On this host `gh pr merge` has reported a worktree-cleanup error even
    when the remote merge succeeded -- cosmetic, not a real failure, and
    re-running the merge is the wrong response to it (the PR is already
    merged). So a failure here is checked against the PR's actual state
    before being treated as real.
    """
    try:
        _gh("pr", "merge", str(pr_number), "--squash", "--body-file", "-", input_text=body)
    except subprocess.CalledProcessError:
        state = _gh("pr", "view", str(pr_number), "--json", "state", "--jq", ".state").strip()
        if state != "MERGED":
            raise
        print(
            "gh pr merge reported an error, but the PR is already merged "
            "-- a cosmetic worktree-cleanup failure seen on this host. "
            "Not re-running it."
        )


def _version_rules():
    """`scripts/check_version_bump.py`, loaded by path -- the two ways
    this file runs put different directories on `sys.path`, so no plain
    `import` works in both. Inside a function so importing this module
    never mutates `sys.path`: a stray entry shadowing the stdlib has
    cost this repository once (`pdf_text.drop_stdlib_shadowing_path_entries`).
    """
    spec = importlib.util.spec_from_file_location(
        "check_version_bump", REPO_ROOT / "scripts" / "check_version_bump.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _args(argv: "list[str] | None") -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python scripts/merge_pr.py",
        description="Check the squash-commit body in a PR's `## Commit message` "
        "section against DEVELOPER-AGENTS.md's format, and merge with "
        "gh pr merge --squash.",
    )
    parser.add_argument("pr_number", type=int, nargs="?", help="the PR number to merge")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run", action="store_true", help="print the checked body without merging"
    )
    mode.add_argument(
        "--check",
        action="store_true",
        help="check a PR description read from stdin, and merge nothing (what CI runs)",
    )
    args = parser.parse_args(argv)
    if args.check and args.pr_number is not None:
        parser.error("--check reads a PR description on stdin and takes no PR number")
    if not args.check and args.pr_number is None:
        parser.error("a PR number is required, unless --check is given")
    return args


def _checked(pr_body: str) -> "CommitBody | None":
    """The body, printed with any warning about the description; None,
    after printing why on stderr, when it breaks the format."""
    try:
        body = commit_body(pr_body)
    except FormatError as error:
        print(f"refusing: {error}", file=sys.stderr)
        return None
    print(body)
    for dead in inert_closing_keywords(pr_body):
        print(
            f"warning: `{dead}` is inside a code span, so GitHub will not "
            "close that issue on merge. Remove the backticks, or close it "
            "by hand afterwards."
        )
    return body


def main(argv: "list[str] | None" = None) -> int:
    args = _args(argv)
    if args.check:
        # Bytes decoded as UTF-8, not the runner's locale: the same
        # reasoning as `_gh`.
        body = _checked(sys.stdin.buffer.read().decode("utf-8"))
        return 0 if body is not None else 1
    body = _checked(_pr_body(args.pr_number))
    if body is None:
        return 1
    # Last, and immediately before the merge: the value of the check is
    # that nothing happens between it and `gh pr merge`. `--dry-run`
    # reports it too, since that is where a person looks first and a
    # body for a merge that would be refused is misleading.
    if _version_rules().blocks_a_merge():
        return 1
    if args.dry_run:
        return 0
    _merge(args.pr_number, str(body))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
