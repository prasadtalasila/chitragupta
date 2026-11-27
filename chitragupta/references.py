"""Builds a "## References" section for a genre draft's Markdown source,
from `content/ledger.sqlite` only. Stdlib-only, so it runs under bare
`python`; never reads `bibliography.bib` (`bib_reader.py` is the sole
reader, AGENTS.md), so entry fields travel through `bib_fields`.

Lists only citekeys the draft already cites, found with `citation_gate`'s
own extraction, so it can never introduce one; run it after the gate
passes. A cited key with no ledger row is a hard error (AGENTS.md's
citekey invariant), never dropped.

Numbered IEEE-style by first appearance, as pandoc's citeproc does, so
the list and the PDF agree on [1]. Each entry ends in its citekey in a
code span, which the gate blanks, so listing a key never looks like
citing it. `numbered_markdown` returns a derived copy with inline numbers;
it is never the draft, which the gate could then no longer check.

Usage:
    python -m chitragupta.draft references <file.md> [--heading TEXT]
"""

import re
import sys
from pathlib import Path

from chitragupta import citation_gate, config, ledger
from chitragupta.reference_entries import entries
from chitragupta.references_renumber import renumber
from chitragupta.references_section import section_end, section_start
from chitragupta.help_format import ClickParser
from chitragupta.progname import prog_for


def used_citekeys(text: str, *, latex: bool = False) -> list[str]:
    """Every citekey cited in `text`, deduped, in order of first appearance,
    the order citeproc numbers by (alphabetical would make [4] the PDF's [7]).
    """
    seen: dict[str, None] = {}
    for _, key in citation_gate.extract_citekeys(text, latex=latex):
        seen.setdefault(key, None)
    return list(seen)


def build_section(
    citekeys: list[str], con, heading: str = "References", label_citekeys: bool = True
) -> str:
    """The References section for `citekeys`, numbered in the given order.
    `label_citekeys` appends each key in a code span; the numbered copy
    turns it off, as its inline numbers already index the list.
    """
    built = entries(citekeys, con)
    lines = [f"## {heading}", ""]
    for number, key in enumerate(citekeys, start=1):
        entry = built[key]
        lines.append(f"[{number}] {entry} `{key}`" if label_citekeys else f"[{number}] {entry}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def numbered_markdown(text: str, con, heading: str | None = None) -> str:
    """`text` with its citekeys replaced by IEEE numbers, over a matching
    reference list.

    A derived copy: the draft keeps `[@citekey]` for the gate and pandoc.
    An existing References section is rebuilt from the ledger so entries
    match the numbering, reusing the draft's own heading text.
    """
    keys = used_citekeys(text)
    # A draft with no citations comes back unchanged, so a hand-written
    # "References" of URLs is not silently deleted.
    if not keys:
        return text

    lines = text.splitlines(keepends=True)
    index = section_start(lines)
    tail = ""
    if index is not None:
        if heading is None:
            heading = re.sub(r"^#+\s*", "", lines[index].strip())
        # M-8: only the References section is dropped, not an appendix
        # after it.
        tail = "".join(lines[section_end(lines, index) :])
        text = "".join(lines[:index]).rstrip() + "\n"

    numbering = {key: number for number, key in enumerate(keys, start=1)}
    body = renumber(text, numbering)
    section = build_section(keys, con, heading or "References", label_citekeys=False)
    result = body.rstrip() + "\n\n" + section
    if tail.strip():
        # A key cited only in the tail is already numbered, since
        # `used_citekeys` read the whole original text.
        result = result.rstrip() + "\n\n" + renumber(tail, numbering).lstrip("\n")
    return result


def write_numbered(path: Path, out_dir: Path, text: str | None = None) -> Path:
    """Writes `path`'s numbered copy into `out_dir`, returning its path.
    `text` lets `render_output`'s `--format md` path pass its
    figure-substituted copy instead of the draft on disk.
    """
    if text is None:
        text = path.read_text(encoding="utf-8")
    # A draft citing nothing never opens the ledger, so it renders unsynced.
    rendered = text
    if used_citekeys(text):
        with ledger.reading() as con:
            rendered = numbered_markdown(text, con)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{path.stem}.md"
    out_path.write_text(rendered, encoding="utf-8")
    return out_path


def apply(path: Path, heading: str = "References") -> str:
    path = config.require_inside_content(path)
    text = path.read_text(encoding="utf-8")
    keys = used_citekeys(text, latex=citation_gate.is_latex(path))
    if not keys:
        return f"{path}: no citekeys cited -- nothing to do"

    with ledger.reading() as con:
        section = build_section(keys, con, heading)

    lines = text.splitlines(keepends=True)
    idx = section_start(lines)
    if idx is None:
        head, tail = text, ""
    else:
        # M-8: only the old References section is replaced; an appendix
        # after it must survive.
        head = "".join(lines[:idx])
        tail = "".join(lines[section_end(lines, idx) :])
    new_text = head.rstrip() + "\n\n" + section.rstrip() + "\n"
    if tail.strip():
        new_text = new_text.rstrip() + "\n\n" + tail.lstrip("\n")
    path.write_text(new_text, encoding="utf-8")
    return f"{path}: wrote References section with {len(keys)} citekey(s)"


def main(argv: list[str] | None = None) -> int:
    parser = ClickParser(
        prog=f"{prog_for('draft')} references",
        description="Append/replace a References section built from a "
        "Markdown draft's own cited citekeys.",
    )
    parser.add_argument("input", help="Path to the draft file (Markdown)")
    parser.add_argument(
        "--heading",
        default="References",
        help='Heading text, e.g. "6. References" to match a draft\'s own '
        'numbered headings (default: "References")',
    )
    args = parser.parse_args(argv)

    try:
        print(apply(Path(args.input), args.heading))
    except (KeyError, config.OutsideContentDir, ledger.NoLedger) as exc:
        # A citekey the ledger lacks, or a path outside content/: refusals
        # for stderr, not tracebacks.
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    return 0
