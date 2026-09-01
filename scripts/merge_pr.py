#!/usr/bin/env python3
"""Compose a conforming squash-commit body and merge the PR (#357).

DEVELOPER-AGENTS.md's "Merging" section already worked out why this has to
happen at merge time rather than through a repository setting:
`squash_merge_commit_message` takes exactly three values --
`PR_BODY`/`COMMIT_MESSAGES`/`BLANK` -- and none of them transforms text, so
no setting turns a PR description into the documented bulleted-list commit
body. This is that supply step, made a command instead of a paragraph a
session has to still be holding at the end of a long run.

**Source of the bullets, and why not raw commits.** The body is pulled from
the PR's own description -- every `## `-headed section except the
template's checkbox ones (`Type of Change`, `Test plan`, `Checklist`,
whose `- [x] ...` lines are not content) -- not from the branch's commit
messages. Concatenating commit subjects is the same low-quality mechanism
the old `COMMIT_MESSAGES` squash default used, and checked against this
batch's own real PRs it degenerates further than that: three of #364/#365/
#366 are single-commit branches, so a commit-subject fallback there is one
bullet restating the (occasionally truncated) commit title -- almost
exactly the `* <title>` preamble this issue exists to kill. Scanning every
non-checkbox section instead of one named heading also survives a PR that
does not follow the template's exact heading names (#365 used `## Summary`
where the template says `## Description`). A prose lead-in before the
bullets is the normal shape of these sections, not an edge case -- the
template's own `## Description` prompt asks for "why this change" -- so
extraction pulls bullet blocks out of the surrounding prose rather than
requiring a whole section to already be in the target shape.
`bullets_from_commits` exists only as the fallback for a PR body with no
bullets anywhere in it.

**The enforcement question, decided.** A test over `git log` was already
rejected in the debt register for the title-side fix, and for the same
reason it does not work here either: `actions/checkout` fetches depth 1, so
CI has no history to walk, and a scan that self-skips on absent history
would be green on the one host that never has it. Unlike the title fix,
there is no repository setting to fall back on -- this is a command, and a
command can be bypassed by merging through the web UI instead. The choice
made here is **producer-is-enforcement**: `scripts/merge_pr.py` becomes the
one documented way to merge (DEVELOPER-AGENTS.md's Merging section), the
same standing the OpenCodeReview step already has as "not in CI and not a
dependency -- so it is the developing agent that has to invoke it. Nothing
else will." A CI job with a deeper checkout that re-scans `main`'s recent
history was considered and rejected instead: it would only catch a bypass
after it had already landed, and it costs a dedicated job plus a
bounded-window policy to avoid false negatives past that window -- a
detection mechanism built to guard a convention that has exactly one
sanctioned command is a heavier answer than the gap it closes.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

_BULLET_RE = re.compile(r"^[-*]\s+(.*)$")

# A code fence opener/closer at column 0 (``` or ~~~). Dash lines inside
# a fenced block are code, not content -- a Description quoting a YAML
# snippet must not land that snippet in main's commit history. Column 0
# deliberately, though CommonMark allows three spaces of indent: an
# indented marker here is far likelier a wrapped bullet's continuation
# line that happens to start with ``` or ~~~ (seen live on PR 518, where
# " ~~~)," truncated the composed body as an "unclosed fence") -- and an
# indented dash line never matches _BULLET_RE anyway, so an indented
# fence has nothing here to protect against. Matched on the marker's
# first three characters only; a longer fence still toggles.
_FENCE_RE = re.compile(r"^(```|~~~)")

# A checkbox bullet's payload. The heading exclusion below catches the
# template's three checklist sections by name; a checkbox under any
# other heading (a hand-added "Reviewer checklist") is still a checkbox,
# not a commit-body bullet.
_CHECKBOX_RE = re.compile(r"^\[[ xX]\]\s")

# Template sections whose bullets are checkboxes, not content -- matched
# case-insensitively since a PR body is free text, not the template file
# itself. "Additional information" is left scannable rather than added
# here: it is free-form reviewer notes, not a fixed checklist, so a bullet
# in it is as likely to be real content as anything under "Description".
_EXCLUDED_HEADINGS = frozenset({"type of change", "test plan", "checklist"})


def _sections(pr_body: str) -> "list[tuple[str, str]]":
    """Every `## `-headed section as `(heading, content)`, in body order.

    Splitting on every heading rather than looking for one named section
    is what survives a PR that does not use the template's exact heading
    (#365 used `## Summary` where the template says `## Description`) --
    the heading text is read, not assumed.
    """
    parts = re.split(r"(?m)^## (.+)$", pr_body)
    return list(zip(parts[1::2], parts[2::2]))


def _bullets_in(text: str) -> list[str]:
    """Every `-`/`*` bullet in `text`, wrapped continuation lines joined
    back onto the bullet they continue, any prose paragraph -- lead-in,
    between two bullet blocks, or trailing -- discarded rather than kept
    as a bullet or as a preamble.

    The join always inserts one space, which is occasionally wrong: a
    hand-wrapped line that breaks mid-token (`chromadb/` \\n
    `sentence-transformers`, seen in a real PR body) comes back with a
    spurious space rather than the original unbroken word. Recovering
    that correctly needs knowing whether a given wrap was a word boundary
    or not, which the text alone does not say -- accepted as a cosmetic
    gap rather than solved with a heuristic likely to guess wrong more
    often than this does.
    """
    bullets: list[str] = []
    current = None
    for line in _outside_fences(text):
        stripped = line.strip()
        if not stripped:
            current = None
            continue
        match = _BULLET_RE.match(line)
        if match and not _CHECKBOX_RE.match(match.group(1)):
            bullets.append(match.group(1).strip())
            current = len(bullets) - 1
            continue
        if match:
            current = None  # a checkbox: not content, and not a bullet to continue
            continue
        if line[:1].isspace() and current is not None:
            bullets[current] = f"{bullets[current]} {stripped}"
            continue
        current = None
    return bullets


def _outside_fences(text: str) -> "list[str]":
    """`text`'s lines with every fenced code block removed.

    Each stripped region leaves one blank line behind so a wrapped
    bullet can never continue across where a fence stood. An unclosed
    fence swallows the rest of the text, as CommonMark reads it.
    """
    kept: list[str] = []
    fence = None
    for line in text.splitlines():
        marker = _FENCE_RE.match(line)
        if marker and (fence is None or marker.group(1) == fence):
            fence = marker.group(1) if fence is None else None
            kept.append("")
        elif fence is None:
            kept.append(line)
    return kept


# GitHub's own closing-keyword vocabulary, in every form it accepts, and
# an issue reference after it. Deliberately not `\b#\d+` on its own: a
# bare "#421" inside a code span is an ordinary cross-reference, not a
# disabled instruction, and reporting one would train the reader to skip
# the warning.
_CLOSING_RE = re.compile(r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#\d+", re.IGNORECASE)

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


def bullets_from_commits(subjects: list[str]) -> list[str]:
    """The fallback source: one bullet per distinct, non-blank commit
    subject, order preserved. Used only when the PR's Description carries
    no bullets to pull from."""
    seen: list[str] = []
    for subject in subjects:
        subject = subject.strip()
        if subject and subject not in seen:
            seen.append(subject)
    return seen


def bullets_from_description(pr_body: str) -> list[str]:
    """Every bullet in the PR body, across all sections except the
    template's checkboxes, in body order."""
    bullets = []
    for heading, content in _sections(pr_body):
        if heading.strip().lower() in _EXCLUDED_HEADINGS:
            continue
        bullets.extend(_bullets_in(content))
    return bullets


def compose_body(pr_body: str, commit_subjects: list[str]) -> tuple[str, str]:
    """The squash-commit body, and which source it came from
    (`"description"` or `"commits"`) so a caller can say so."""
    bullets = bullets_from_description(pr_body)
    source = "description"
    if not bullets:
        bullets = bullets_from_commits(commit_subjects)
        source = "commits"
    return "\n".join(f"- {b}" for b in bullets), source


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


def _pr_commit_subjects(pr_number: int) -> list[str]:
    output = _gh(
        "pr", "view", str(pr_number), "--json", "commits", "--jq", ".commits[].messageHeadline"
    )
    return [line for line in output.splitlines() if line.strip()]


def _merge(pr_number: int, body: str) -> None:
    """`gh pr merge --squash`, with the composed body on stdin.

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


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python scripts/merge_pr.py",
        description="Compose the squash-commit body DEVELOPER-AGENTS.md's "
        "Merging section documents, from the PR's Description "
        "(or its commits, as a fallback), and merge with "
        "gh pr merge --squash.",
    )
    parser.add_argument("pr_number", type=int, help="the PR number to merge")
    parser.add_argument(
        "--dry-run", action="store_true", help="print the composed body without merging"
    )
    args = parser.parse_args(argv)

    body = _pr_body(args.pr_number)
    text, source = compose_body(body, _pr_commit_subjects(args.pr_number))
    print(text)
    print(f"(composed from the PR's {source})")
    for dead in inert_closing_keywords(body):
        print(
            f"warning: `{dead}` is inside a code span, so GitHub will not "
            "close that issue on merge. Remove the backticks, or close it "
            "by hand afterwards."
        )
    if args.dry_run:
        return 0
    _merge(args.pr_number, text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
