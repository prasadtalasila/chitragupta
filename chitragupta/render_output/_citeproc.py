"""Preparing a draft and the bibliography for `pandoc --citeproc`.

All three fixups here are applied only to temp copies: the draft and the
real `bibliography.bib` are never modified.
"""

import re
import unicodedata
from pathlib import Path

from chitragupta import _pandoc_cites, references_section

# C0 controls other than the whitespace pdflatex accepts (\t \n \r), plus
# DEL: never legitimate in a rendered document.
_UNSAFE_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _sanitize_for_latex(text: str) -> str:
    r"""`text` with control characters stripped and accents stored as one
    code point -- the two things no output format wants, and nothing else.

    NULs arrive via quotes from `pdftotext` output (#389); decomposed accents
    too, and pdflatex rejects both. NFC changes storage, never the letter.
    Not NFKC: that rewrote `m²`, `H₂O` and `µm` (#948); printing those is
    `assets/latex/chitragupta-unicode.sty`'s job.
    """
    return _UNSAFE_CONTROL_RE.sub("", unicodedata.normalize("NFC", text))


def _alias_for(citekey: str) -> str:
    # pandoc's citation tokenizer truncates a citekey at "--", so each run is
    # aliased to a single hyphen plus markers (collision-free against the ledger).
    # Every hyphen in a run is separated: replacing only "--" leaves a 3-hyphen
    # run still holding "--", and the source silently drops out. A run of n
    # hyphens becomes "-" + "x2d-" * (n-1).
    return re.sub(r"-{2,}", lambda m: "-" + "x2d-" * (len(m.group()) - 1), citekey)


def _safe_render_inputs(
    input_path: Path,
    bib_path: Path,
    tmp_dir: Path,
    text: str | None = None,
) -> tuple[Path, Path]:
    """Returns (markdown_path, bib_path) safe to hand to `pandoc --citeproc`.

    `text` overrides the file's contents, so `render()`'s figure substitutions
    are not lost; the filename stays `input_path`'s for pandoc's errors.

    Three fixups, on temp copies only (draft and bibliography.bib are never
    modified): a manual References section's entries become citeproc's anchor
    (`_swap_manual_refs_for_citeproc`); `--` citekeys are aliased in both
    files; control characters are stripped (`_sanitize_for_latex`). Returns
    the original paths when none applies.
    """
    on_disk = input_path.read_text(encoding="utf-8")
    original = on_disk if text is None else text
    text = _sanitize_for_latex(_swap_manual_refs_for_citeproc(original))
    bad_keys = {key for _, _, key in _pandoc_cites.citations(text) if "--" in key}
    if not bad_keys:
        # Against the disk, not `original`: a caller's figure substitutions
        # already differ from the file, and returning `input_path` would drop them.
        if text == on_disk:
            return input_path, bib_path
        safe_md = tmp_dir / input_path.name  # pragma: no cover-windows
        safe_md.write_text(text, encoding="utf-8")  # pragma: no cover-windows
        return safe_md, bib_path  # pragma: no cover-windows

    bib_text = bib_path.read_text(encoding="utf-8")
    for key in bad_keys:
        alias = _alias_for(key)
        text = re.sub(
            r"(?<![A-Za-z0-9._%+-])(-?@)" + re.escape(key) + r"(?![A-Za-z0-9_-])",
            r"\1" + alias,
            text,
        )
        # Anchored on the entry header's trailing "," so aliasing a key does not
        # also touch a separate entry whose key extends it (e.g. a `-1` suffix).
        bib_text = re.sub(
            r"(@\w+\{)" + re.escape(key) + r"(,)",
            r"\1" + alias + r"\2",
            bib_text,
            count=1,
        )

    safe_md = tmp_dir / input_path.name
    safe_bib = tmp_dir / bib_path.name
    safe_md.write_text(text, encoding="utf-8")
    safe_bib.write_text(bib_text, encoding="utf-8")
    return safe_md, safe_bib


def drop_manual_refs(text: str) -> str:
    """`text` without its References section at all -- heading and entries.

    For a fragment, whose citations go to the book's one `\\bibliography`: a
    per-chapter list would be a second, differently numbered answer, and its
    heading an empty chapter. Temp copy only: editing the draft would mark
    every unit `stale:` via `output_digest`. `section_end` keeps a later
    appendix or acknowledgments section (M-8).
    """
    lines = text.splitlines(keepends=True)
    idx = references_section.section_start(lines)
    if idx is None:
        return text
    tail = "".join(lines[references_section.section_end(lines, idx) :])
    out = "".join(lines[:idx]).rstrip() + "\n"
    if tail.strip():
        out = out + "\n" + tail.lstrip("\n")
    return out


def aliased_bib_text(bib_text: str) -> str:
    """`bib_text` with **every** `--`-bearing citekey aliased, not just one
    draft's.

    A book's `.bib` serves one `bibtex` pass over every separately rendered
    chapter, so per-draft aliasing would let the last unit decide. Unconditional:
    a file with no `--` key comes back unchanged anyway.
    """
    return re.sub(
        r"(@\w+\{)([^,\s]*--[^,\s]*)(,)",
        lambda m: m.group(1) + _alias_for(m.group(2)) + m.group(3),
        bib_text,
    )


# Pandoc's idiom for "put the bibliography here"; `fenced_divs` is on by default.
_REFS_ANCHOR = "::: {#refs}\n:::\n"


def _swap_manual_refs_for_citeproc(text: str) -> str:
    """Replaces a `draft references` section's *entries* with an anchor citeproc
    fills in, keeping the draft's own heading.

    Temp copy only: the draft keeps its citekey-labelled entries, which the gate
    traces back to literal keys (the project's citation invariant). The rendered
    artifact takes citeproc's numbered bibliography instead. The heading stays
    because citeproc emits none and a skill may have numbered it.
    """
    lines = text.splitlines(keepends=True)
    idx = references_section.section_start(lines)
    if idx is None:
        return text
    heading = lines[idx] if lines[idx].endswith("\n") else lines[idx] + "\n"
    # M-8: only the manual entries are swapped -- a later appendix or
    # acknowledgments section must reach pandoc too, as it does on the md path.
    tail = "".join(lines[references_section.section_end(lines, idx) :])
    out = "".join(lines[:idx]).rstrip() + f"\n\n{heading}\n{_REFS_ANCHOR}"
    if tail.strip():
        out = out.rstrip() + "\n\n" + tail.lstrip("\n")
    return out
