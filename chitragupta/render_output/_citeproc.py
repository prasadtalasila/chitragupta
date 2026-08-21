"""Preparing a draft and the bibliography for `pandoc --citeproc`.

Both fixups here are applied only to temp copies: the draft and the real
`bibliography.bib` are never modified.
"""

import re
from pathlib import Path

from chitragupta import references
from chitragupta.citation_gate import _PANDOC_CITE_RE


def _alias_for(citekey: str) -> str:
    # "--" is the one substring pandoc's own citation tokenizer can't
    # carry through a citekey (see module docstring) -- collapsing it to
    # a single hyphen plus a marker keeps the alias readable and, checked
    # against every citekey currently in the ledger, collision-free.
    #
    # Every hyphen in a run has to be separated, not just the first pair:
    # a plain .replace("--", "-x2d-") turns the 3-hyphen run in this
    # corpus's own `tygesen_state---art_2019` into `state-x2d--art`, which
    # still contains "--" and so still truncates -- the citation resolves
    # to nothing and the source silently drops out of the bibliography.
    # A run of n hyphens becomes "-" + "x2d-" * (n-1), which reduces to
    # the original "-x2d-" for the 2-hyphen case.
    return re.sub(r"-{2,}", lambda m: "-" + "x2d-" * (len(m.group()) - 1), citekey)


def _safe_render_inputs(
    input_path: Path, bib_path: Path, tmp_dir: Path, text: str | None = None,
) -> tuple[Path, Path]:
    """Returns (markdown_path, bib_path) safe to hand to `pandoc --citeproc`.

    `text` overrides what is read from `input_path`, so a caller that has
    already rewritten the draft -- `render()`, swapping each figure to the
    form the output format can draw -- passes the rewritten text rather
    than having it re-read from disk and its substitutions lost. The
    filename is still `input_path`'s, because that is what pandoc reports
    in an error message. Defaults to reading the file, which is every
    other caller.

    Two independent fixups, both applied only to temp copies -- the draft
    and the real bibliography.bib are never modified:
      - a `python -m chitragupta.draft references` References section has its entries
        replaced by citeproc's own placement anchor, keeping the draft's
        heading (see _swap_manual_refs_for_citeproc);
      - a citekey containing "--" is aliased in both files, in the input
        and the bib together, because pandoc's citation tokenizer would
        otherwise truncate it mid-key and silently drop the citation.

    Returns the original paths untouched when neither applies.
    """
    on_disk = input_path.read_text(encoding="utf-8")
    original = on_disk if text is None else text
    text = _swap_manual_refs_for_citeproc(original)
    bad_keys = {m.group(1) for m in _PANDOC_CITE_RE.finditer(text) if "--" in m.group(1)}
    if not bad_keys:
        # Against what is *on disk*, not against `original`. Comparing
        # with `original` returns `input_path` whenever this function
        # changed nothing -- which silently discards a caller's figure
        # substitutions, because those already differed from the file
        # before this function ever saw them, and pandoc then reads the
        # unsubstituted draft.
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
        # Anchored on the entry header's trailing "," so e.g. aliasing
        # `zech_digital-twins-as--service_2024` doesn't also touch the
        # separate `zech_digital-twins-as--service_2024-1` entry.
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


# Pandoc's own idiom for "put the bibliography exactly here" -- citeproc
# fills this div in place instead of appending its bibliography to the end
# of the document. `fenced_divs` is on by default in pandoc's markdown.
_REFS_ANCHOR = "::: {#refs}\n:::\n"


def _swap_manual_refs_for_citeproc(text: str) -> str:
    """Replaces a `python -m chitragupta.draft references` section's *entries* with an
    anchor citeproc fills in, keeping the draft's own heading.

    Only ever applied to the temp copy handed to pandoc, never to the
    draft itself. The draft keeps its citekey-labelled entries: a reader
    (or `citation_gate`) can trace one back to a literal key, which is the
    project's whole citation invariant. What that hand-built list cannot
    be is *numbered consistently with the rendered output* -- pandoc
    assigns citation numbers itself -- so the rendered artifact takes
    citeproc's bibliography instead, drawn straight from bibliography.bib
    with authors and venues in it. That is what
    `--metadata suppress-bibliography=true` used to prevent here, back
    when the manual section was the only one with real entries in it.

    The heading stays because it is the draft's own: a genre skill may
    have numbered it to match its other headings (`## 6. References`, via
    `chitragupta.draft references --heading`), and citeproc emits no heading of its own,
    so dropping the whole section left the rendered bibliography
    untitled.
    """
    lines = text.splitlines(keepends=True)
    idx = references.section_start(lines)
    if idx is None:
        return text
    heading = lines[idx] if lines[idx].endswith("\n") else lines[idx] + "\n"
    return "".join(lines[:idx]).rstrip() + f"\n\n{heading}\n{_REFS_ANCHOR}"
