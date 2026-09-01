"""What a human approved, read back off disk.

Split from `chitragupta/spec/__init__.py` for the reason `_cli.py` was split
from it: that module is the outline's parse and the paths, this one is the
*record of a decision about* an outline, and together they crossed the
250-code-line limit docs/CODE-STANDARDS.md sets. Nothing here parses an
outline; everything here reads `signoff.md`.

The two questions are deliberately separate functions rather than one
answer. "Is the whole book as approved?" is what `spec status` reports;
"is *this chapter* as approved?" is what `unit accept` needs, and
conflating them is exactly the defect #465 recorded.
"""

import re
from pathlib import Path

from chitragupta.spec import chapter_digests, signoff_path

# `- spec digest: `a1b2c3d4e5f6`` in signoff.md.
_DIGEST_LINE = re.compile(r"^-\s*spec digest:\s*`?([0-9a-f]{12})`?", re.MULTILINE)

# `- chapter `ch-01`: `a1b2c3d4e5f6`` in signoff.md -- one per chapter.
#
# Two spellings of the id, and the split is what #506/m-63 was about.
# `spec.__init__._HEADING` accepts `{#ch:intro}` -- its id group is
# `[^}\s]+`, which allows a colon -- and `_cli.py`'s writer always emits
# the id inside backticks. Read back by a single `[^`\s:]+` group, that
# line did not match at all: `ch:intro` signed off cleanly and was then
# never in `signed_off_chapters`, so its units were refused forever.
# The backticked alternative therefore takes anything but a backtick,
# which is exactly what the writer can produce; the bare alternative
# keeps the old colon exclusion, because there a colon is the field
# separator and `ch:intro: `digest`` genuinely cannot be split.
_CHAPTER_LINE = re.compile(
    r"^-\s*chapter\s+(?:`([^`\n]+)`|([^`\s:]+))\s*:\s*`?([0-9a-f]{12})`?",
    re.MULTILINE,
)


def recorded_digest(book: Path) -> str | None:
    """The digest `sign` recorded for `book`, or None if none was.

    None covers both "nobody signed off" and "a signoff.md exists but
    carries no digest" -- a hand-written one, say. Both mean the same
    thing to every caller: no approval this module can check.
    """
    path = signoff_path(book)
    if not path.is_file():
        return None
    match = _DIGEST_LINE.search(path.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def recorded_chapter_digests(book: Path) -> dict[str, str]:
    """The per-chapter digests `sign` recorded for `book`.

    Empty for a `signoff.md` written before chapter lines existed -- every
    book already on disk. Callers read that as "no finer answer available"
    and fall back to the whole-book digest, which is what
    `signed_off_chapters` does. Nothing migrates an old file: doing so
    would re-approve chapters on a human's behalf, which is the one thing
    a record of a person's decision may never do.
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

    None means "no per-chapter record" -- an unsigned book, or one signed
    before chapter lines existed. A caller that gets None has only the
    whole-book digest to go on and must say so rather than guess, because
    guessing either way is wrong: assume approved and prose nobody read
    gets accepted; assume not and every book already on disk stops.
    """
    recorded = recorded_chapter_digests(book)
    if not recorded:
        return None
    current = chapter_digests(text)
    return {chapter for chapter, value in current.items() if recorded.get(chapter) == value}
