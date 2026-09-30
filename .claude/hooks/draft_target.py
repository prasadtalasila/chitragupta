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
- **One write can change several drafts** (#812). Codex's `apply_patch`
  and OpenCode's (through its plugin) carry no `file_path`: the targets
  are the headers of the patch in `tool_input.command`, read by
  patch_paths.py, and every draft a patch adds, updates or moves is
  returned. A relative patch path resolves against the payload's `cwd`
  when it has one, since that is what Codex's paths are relative to.

Malformed stdin fails open in all three shapes that have been hit --
invalid JSON, valid JSON that is not an object, and a `tool_input` that is
not a dict. Each means "no file path was given", and a hook that raises
there is a hook that stops reporting. The one exception is a patch
envelope that mentions a draft but whose headers cannot be read: that
raises `UnreadablePatch`, because failing open there is exactly the
silently inert gate docs/HOOKS.md exists to prevent.
"""

from __future__ import annotations

import json
from pathlib import Path

import patch_paths
from patch_paths import UnreadablePatch  # re-exported: the gate hook blocks on it

DRAFT_EXTENSIONS = (".md", ".tex")
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
# Both separators: a Windows harness may name the draft either way.
_DRAFT_MARKERS = ("content/drafts/", "content\\drafts\\")


def targets_from_stdin(stream, repo_root: Path | None = None) -> list[Path]:
    """Every draft this PostToolUse payload wrote, in order, once each; [] otherwise.

    `[]` covers every "not our business" case -- unparseable stdin, a
    payload of the wrong shape, no file named, a write outside
    `content/drafts/`, and a suffix this pipeline does not produce. A hook
    that gets `[]` returns 0 and says nothing.

    `repo_root` exists for the tests, which relocate a copy of a hook into
    a temporary tree; production callers pass nothing and get this file's
    own location, which is the point.
    """
    payload = _payload(stream)
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return []  # missing, null, or the wrong shape -- same as "no file named"
    base = payload.get("cwd")
    found: list[Path] = []
    for raw in _raw_paths(tool_input):
        if isinstance(base, str) and base and not Path(raw).is_absolute():
            raw = str(Path(base) / raw)  # Codex patch paths are relative to its cwd
        path = target(raw, repo_root)
        if path is not None and path not in found:
            found.append(path)
    return found


def _payload(stream) -> dict:
    try:
        payload = json.load(stream)
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
        return {}  # can't identify a target file from this -- fail open, not loud
    # valid JSON (a bare array, string, number) but not the shape
    return payload if isinstance(payload, dict) else {}


def _raw_paths(tool_input: dict) -> list[str]:
    raw = tool_input.get("file_path")
    if isinstance(raw, str) and raw:
        return [raw]
    text = _patch_text(tool_input.get("command"))
    try:
        return patch_paths.written_paths(text)
    except UnreadablePatch:
        if any(marker in text for marker in _DRAFT_MARKERS):
            raise
        return []  # an unreadable patch that never names a draft is not ours


def _patch_text(command) -> str:
    """The patch text in `command`: a string, or a list of argv-style parts."""
    if isinstance(command, str):
        return command
    if isinstance(command, list):
        return "\n".join(part for part in command if isinstance(part, str))
    return ""


def target(raw_path: str, repo_root: Path | None = None) -> Path | None:
    """The resolved draft `raw_path` names, or None if it is not one.

    Split from `targets_from_stdin` so a caller that already has a path -- a test,
    or a hook reading the payload for something else too -- can ask the
    same question without building a JSON document to ask it with.
    """
    if not raw_path:
        return None
    try:
        root = (repo_root or REPO_ROOT).resolve()
        path = Path(raw_path)
        if not path.is_absolute():
            path = root / path
        path = path.resolve()
        drafts = (root / "content" / "drafts").resolve()
        inside = path.is_relative_to(drafts)
    except (OSError, ValueError):
        # A path this platform will not construct. The observed case is an
        # embedded null byte, which raises ValueError from resolve();
        # OSError is guarded for the platforms where resolution touches the
        # filesystem, though on Linux it does not -- `resolve()` does not
        # stat, so even a path past the length limit gets this far. Neither
        # can be a draft this pipeline wrote.
        #
        # This is caught rather than left to propagate because the caller
        # that matters has no catch-all: citation_gate_hook's `main` runs
        # straight off `raise SystemExit(main())`, so an exception here
        # would exit non-zero *without* the blocking decision, and the
        # write would land ungated. A hook that crashes on a malformed
        # payload is a gate that stops being one.
        return None
    if not inside or path.suffix not in DRAFT_EXTENSIONS:
        return None
    return path
