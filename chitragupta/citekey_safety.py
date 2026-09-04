"""Is a citekey safe to use as a filename stem? One answer, shared.

Extracted from `chitragupta/bib_reader.py` (#638), and the move is the
point: the validator guarded only the bib-sync side, where `read_library`
rejects an entry whose citekey cannot be a filename -- but the review
layer builds `content/parsed/<citekey>.txt` and
`content/docling/<citekey>.passages.json` paths from citekeys extracted
out of a *draft*, and the LaTeX regex accepts nearly anything inside
`\\cite{...}`. A draft citing `\\citep{../../secret}` therefore read
files outside the content tree. Those readers cannot import
`bib_reader` -- it imports `bibtexparser` at module level, a dependency
the gate-tier and review-tier modules deliberately run without -- so the
check lives here, stdlib-only, and `bib_reader` re-exports it unchanged.

The rules are the union of what POSIX and Windows need, not just this
host's: a bib file that works on Linux must not quietly produce
unwritable paths on the Windows CI leg, and the failure would otherwise
surface as a confusing OSError from deep inside a parse rather than as a
problem with the bib file. bibtexparser hands back whatever sits between
`{` and `,`, which includes `smith/2024` and `../escape2024`: the first
writes into a subdirectory that doesn't exist; the second escapes the
content directory entirely. Neither is hypothetical -- both parse today.
"""

import re

_CITEKEY_ILLEGAL_RE = re.compile(r'[/\\:*?"<>|\x00-\x1f]')

# Reserved on Windows whatever the extension: `CON.txt` is still CON.
_WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def citekey_problem(citekey: str) -> str | None:
    """Why `citekey` is unsafe as a filename stem, or None if it is fine.

    Returns a reason rather than a bool so the caller can name the actual
    problem: "rename it" is only actionable if you say what is wrong with
    it.
    """
    if not citekey or not citekey.strip():
        return "it is empty"
    if citekey in (".", ".."):
        return "it is a path component with a reserved meaning"
    match = _CITEKEY_ILLEGAL_RE.search(citekey)
    if match:
        char = match.group()
        shown = repr(char) if char.isprintable() else f"a control character (0x{ord(char):02x})"
        return f"it contains {shown}, which cannot appear in a filename"
    # Windows silently strips a trailing dot or space, so two citekeys
    # differing only by one would collide on disk there and not here.
    if citekey != citekey.rstrip(". "):
        return "it ends in a dot or a space, which Windows strips from a filename"
    if citekey.split(".")[0].upper() in _WINDOWS_RESERVED:
        return f"'{citekey.split('.')[0]}' is a reserved device name on Windows"
    return None
