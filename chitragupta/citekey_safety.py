"""Is a citekey safe to use as a filename stem? One answer, shared.

Stdlib-only so the review layer, which builds paths from citekeys found
in a *draft*, can use it without bibtexparser: `\\citep{../../secret}`
once read files outside the content tree (#638). `bib_reader`
re-exports it. The rules are POSIX and Windows combined, so a bib that
works on Linux cannot fail deep in a parse on the Windows CI leg.

`citekey_path` is the one place a per-citekey file name is built (#975;
`tldr show ../../x` once read any JSON file).
`tests/test_citekey_path.py` fails on any other `/ f"{citekey}..."` join.
"""

import re
from pathlib import Path

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
    """Why `citekey` is unsafe as a filename stem, or None if it is fine;
    a reason, so the caller can say what to rename.
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


class UnsafeCitekey(ValueError):
    """A citekey `citekey_path` refused to turn into a file name."""


def citekey_path(directory: Path, citekey: str, suffix: str) -> Path:
    """`directory / f"{citekey}{suffix}"`, or `UnsafeCitekey`. A key
    `citekey_problem` accepts is one entry directly inside `directory`.
    """
    problem = citekey_problem(citekey)
    if problem:
        raise UnsafeCitekey(f"citekey {citekey!r} cannot name a file: {problem}")
    return directory / f"{citekey}{suffix}"


# Any character a citekey may hold: everything but whitespace, the
# delimiters a citation is written between, and what `citekey_problem`
# refuses. `.`, `+`, `-` and non-ASCII letters are all key characters.
_KEY_CHAR = r"[^\s\[\](){},;@'\"`|<>:/\\*?]"


def citekey_pattern(citekey: str) -> "re.Pattern[str]":
    """The literal citekey, bounded by every character a citekey may
    contain, so `smith2020` matches neither inside `smith2020b`,
    `smith2020.v2` nor `smith+smith2020`. Dots straight after it are
    sentence punctuation (`see @smith2020.`), since no citekey ends in one.

    Shared by `sync_residue` and `dossier/_renames.py`, so a key one
    reports is exactly a key the other replaces.
    """
    return re.compile(rf"(?<!{_KEY_CHAR}){re.escape(citekey)}(?=\.*(?!{_KEY_CHAR}))")
