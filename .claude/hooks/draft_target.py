"""Was this write a draft? -- the one decision both PostToolUse hooks share.

`citation_gate_hook.py` gates a draft and `style_check_hook.py` checks its
prose, and they differ only in what they do once they know a draft was
written. This module is that "once they know", factored out rather than
copied, because two hooks disagreeing about which writes they cover is a
worse bug than either could have alone -- and it is the bug a copied forty
lines produces the first time one copy is fixed. docs/HOOKS.md argues the
fault-isolation objection to sharing anything between a gate and a
non-gate: what must not be shared is the *failure* of a check, which
separate processes guarantee, and what must be shared is the *definition
of a draft*.

Every part below was learned from a real near-miss, and is recorded here
because none of it is guessable from the payload:

- **`file_path` may be relative.** Claude Code's Write/Edit tools document
  it as absolute and it has always been so in practice, but a substring
  match on "/content/drafts/" would silently skip a relative
  "content/drafts/<slug>.md" -- no leading slash to match, no error, just
  an ungated draft. So a relative path is resolved rather than ignored.
- **The repo root comes from this file's own location**, never from the
  target path and never from the working directory. A hook is run from
  wherever the harness happens to be.
- **Containment is `is_relative_to` on resolved paths**, not a string
  test, so `content/drafts/../../etc/passwd` cannot pass for a draft.
- **The suffix must be one this pipeline writes.** `.md` from the four
  Markdown genres and the revisers, `.tex` from thesis-chapter-writer.

Malformed stdin fails open in all three shapes that have been hit --
invalid JSON, valid JSON that is not an object, and a `tool_input` that is
not a dict. Each means "no file path was given", and a hook that raises
there is a hook that stops reporting.
"""

from __future__ import annotations

import json
from pathlib import Path

DRAFT_EXTENSIONS = (".md", ".tex")
REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def from_stdin(stream, repo_root: Path | None = None) -> Path | None:
    """The draft this PostToolUse payload wrote, or None for anything else.

    None covers every "not our business" case -- unparseable stdin, a
    payload of the wrong shape, no file path, a write outside
    `content/drafts/`, and a suffix this pipeline does not produce. A hook
    that gets None returns 0 and says nothing.

    `repo_root` exists for the tests, which relocate a copy of a hook into
    a temporary tree; production callers pass nothing and get this file's
    own location, which is the point.
    """
    return target(_file_path(stream), repo_root)


def _file_path(stream) -> str:
    """The `tool_input.file_path` in this payload, or "" if there isn't one."""
    try:
        payload = json.load(stream)
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
        return ""  # can't identify a target file from this -- fail open, not loud
    if not isinstance(payload, dict):
        return ""  # valid JSON (a bare array, string, number) but not the shape
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return ""  # missing, null, or the wrong shape -- same as "no file_path"
    raw = tool_input.get("file_path", "")
    return raw if isinstance(raw, str) else ""


def target(raw_path: str, repo_root: Path | None = None) -> Path | None:
    """The resolved draft `raw_path` names, or None if it is not one.

    Split from `from_stdin` so a caller that already has a path -- a test,
    or a hook reading the payload for something else too -- can ask the
    same question without building a JSON document to ask it with.
    """
    if not raw_path:
        return None
    root = (repo_root or REPO_ROOT).resolve()
    path = Path(raw_path)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()

    drafts = (root / "content" / "drafts").resolve()
    if not path.is_relative_to(drafts) or path.suffix not in DRAFT_EXTENSIONS:
        return None
    return path
