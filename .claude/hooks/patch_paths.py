"""Which files does an apply_patch envelope write? -- read from its own headers.

Codex edits files through `apply_patch`, and OpenCode's `apply_patch`
tool takes the same envelope. Neither payload carries a `file_path`: the
targets are named inside the patch text, one header per file operation,
in OpenAI's V4A grammar:

    *** Begin Patch
    *** Add File: <path>
    *** Update File: <path>
    *** Move to: <path>        (optional, right after an Update)
    *** Delete File: <path>
    *** End Patch

This module reads those headers and nothing else. It never applies a
patch and never reads a hunk, because the gate checks the file on disk
after the write, not the diff. A header is only a header at the start of
a line; a `+` line quoting one is content.

`Delete File` is not a write: a deleted draft has no text to gate. An
envelope naming no operation at all is `UnreadablePatch`, so the caller
can fail closed when that envelope concerns a draft (draft_target.py).
Standard library only, like every hook helper here.
"""

from __future__ import annotations

import re

BEGIN = "*** Begin Patch"
_WRITE_HEADER = re.compile(r"^\*\*\* (?:Add File|Update File|Move to): (.+?)\r?$", re.MULTILINE)
_ANY_HEADER = re.compile(r"^\*\*\* (?:Add File|Update File|Move to|Delete File): ", re.MULTILINE)


class UnreadablePatch(ValueError):
    """A patch envelope that names no file operation this module can read."""


def written_paths(text: str) -> list[str]:
    """Every path the patch in `text` adds, updates or moves to, in order, once each.

    `[]` when `text` holds no patch envelope, or one that only deletes.
    """
    if BEGIN not in text:
        return []
    if not _ANY_HEADER.search(text):
        raise UnreadablePatch("an apply_patch envelope with no file header")
    return list(dict.fromkeys(m.group(1).strip() for m in _WRITE_HEADER.finditer(text)))
