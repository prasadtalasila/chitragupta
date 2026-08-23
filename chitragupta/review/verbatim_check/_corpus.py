"""Corpus lookup: the citekey -> bib entry -> PDF/parsed-text path chain
every tier and CLI mode in this package reads from.

Split out of what was one 2357-line chitragupta/review/verbatim_check.py
(#361): `BIB`/`PARSED_DIR` and the functions that read them live here,
the package root others import from -- mirroring chitragupta/dossier/'s
own root submodule.
"""

import re
import subprocess
from pathlib import Path

from chitragupta import config

BIB = config.BIB_FILE_PATH
PARSED_DIR = config.PARSED_DIR


def bib_entry(citekey: str) -> str:
    if not BIB.exists():
        # papers/bibliography.bib is gitignored, per-host data (see
        # AGENTS.md) -- absent on a fresh clone/CI checkout until someone
        # exports their own. Treat that the same as "citekey not in the
        # bib file" rather than crashing on a raw FileNotFoundError.
        return ""
    text = BIB.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"@\w+\{" + re.escape(citekey) + r",", text)
    if not m:
        return ""
    # Brace-match to the entry's real end rather than stopping at the
    # first "\n}": that sequence occurs *inside* multi-line field values
    # too (an `annote` holding a URL list is the common case here), which
    # truncated the entry mid-way and hid every field after it --
    # including `file`, so 40 papers looked like they had no PDF at all.
    depth = 0
    for i in range(text.index("{", m.start()), len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[m.start():i + 1]
    return text[m.start():]  # unbalanced braces: hand back what we have


def pdf_path(citekey: str) -> Path | None:
    """The `file` field's attachment format is `Desc:path:mimetype`,
    `;`-separated per attachment -- the same shape chitragupta.bib_reader
    parses, and it must be split the same way here.

    Splitting on ':' and taking the first segment that merely *ends in*
    `.pdf` picks the human-readable description, not the path: this
    project's export writes both, as
    `Smith - 2024 - Title.pdf:pdfs/21/Smith - 2024 - Title.pdf:application/pdf`.
    Those two coincide only when the attachment sits directly beside the
    .bib, so the mistake was invisible in a flat fixture directory and
    silently lost 196 of 501 real PDFs -- `locate`/`overlap` then fell
    back to parsed text and reported page 1 for everything.
    """
    entry = bib_entry(citekey)
    m = re.search(r"file = \{(.*?)\},", entry, re.S)
    if not m:
        return None
    # Anchor a relative attachment path to the bib file's own directory,
    # matching chitragupta.bib_reader._resolve_pdf_path -- not REPO, which is
    # wrong the moment BIB_FILE points somewhere outside the checked-out
    # repo (a relative path in the file field is only ever relative to
    # wherever the .bib itself lives).
    bib_dir = BIB.resolve().parent
    for attachment in m.group(1).split(";"):
        parts = attachment.split(":")
        if len(parts) < 3:
            continue
        if "pdf" not in parts[-1].lower():
            continue
        p = Path(":".join(parts[1:-1]).strip())
        if not p.is_absolute():
            p = bib_dir / p
        if p.is_file():
            return p
    return None


def pages(citekey: str) -> list[str]:
    """Return list of page texts, 1-indexed by position+1 (PDF page order)."""
    p = pdf_path(citekey)
    if p is None:
        parsed = PARSED_DIR / f"{citekey}.txt"
        if not parsed.exists():
            return []
        # pdftotext leaves stray NUL/control bytes in some files, which
        # makes grep treat them as binary and report nothing. Strip them
        # so a false "no match" can't be mistaken for a real absence.
        raw = parsed.read_text(encoding="utf-8", errors="replace")
        return re.sub(r"[\x00-\x08\x0e-\x1f]", " ", raw).split("\f")
    out = subprocess.run(  # pragma: no cover-windows
        ["pdftotext", "-layout", str(p), "-"],
        capture_output=True, text=True, check=True,
    )
    return out.stdout.split("\f")  # pragma: no cover-windows


WORD = re.compile(r"[a-z0-9]+")


def norm(text: str) -> list[str]:
    return WORD.findall(text.lower())


def sentences_citing(draft: str | Path, citekey: str) -> list[str]:
    """Whole paragraphs mentioning the citekey, not just the citing sentence.

    Paraphrased-but-uncited sentences sitting next to a citation are
    exactly where borrowed wording hides, so compare the whole
    paragraph against the source.
    """
    text = Path(draft).read_text(encoding="utf-8")
    paras = re.split(r"\n\s*\n", text)
    return [re.sub(r"\s+", " ", p) for p in paras if citekey in p]
