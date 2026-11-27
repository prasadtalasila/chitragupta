"""What a human approved, read back off disk.

Reads `signoff.md`; parses no outline. Whole-book ("spec status") and
per-chapter ("unit accept") approval are separate functions: conflating
them was #465.
"""

import re
from pathlib import Path

from chitragupta.spec import chapter_digests, signoff_path

_DIGEST_LINE = re.compile(r"^-\s*spec digest:\s*`?([0-9a-f]{12})`?", re.MULTILINE)

# One chapter line in signoff.md (#506/m-63): ids may contain a colon, so
# the backticked form takes anything but a backtick (as the writer emits);
# the bare form keeps the colon exclusion, where a colon separates fields.
_CHAPTER_LINE = re.compile(
    r"^-\s*chapter\s+(?:`([^`\n]+)`|([^`\s:]+))\s*:\s*`?([0-9a-f]{12})`?",
    re.MULTILINE,
)


def recorded_digest(book: Path) -> str | None:
    """The digest `sign` recorded for `book`, or None if none was.

    None also for a signoff.md with no digest: no checkable approval.
    """
    path = signoff_path(book)
    if not path.is_file():
        return None
    match = _DIGEST_LINE.search(path.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def recorded_chapter_digests(book: Path) -> dict[str, str]:
    """The per-chapter digests `sign` recorded for `book`.

    Empty for an older signoff.md; callers fall back to the whole-book
    digest. Nothing migrates an old file: that would re-approve chapters
    on a human's behalf.
    """
    path = signoff_path(book)
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8")
    return {
        (match.group(1) or match.group(2)): match.group(3) for match in _CHAPTER_LINE.finditer(text)
    }


def signed_off_chapters(book: Path, text: str) -> set[str] | None:
    """Which of `book`'s chapters are approved as they currently stand.

    None means no per-chapter record; the caller must say so, since
    guessing either way is wrong (unread prose accepted, or every
    existing book stopped).
    """
    recorded = recorded_chapter_digests(book)
    if not recorded:
        return None
    current = chapter_digests(text)
    return {chapter for chapter, value in current.items() if recorded.get(chapter) == value}
