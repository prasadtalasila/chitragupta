"""Builds a "## References" section for a genre draft's Markdown source,
sourced only from `content/ledger.sqlite` (populated by `sync` from
`bibliography.bib`, the source of truth). Stdlib-only (`sqlite3`, `json`),
like `citation_gate.py`, so it runs with bare `python` -- no
`bibtexparser`/venv needed. Deliberately doesn't read `bibliography.bib`
itself; `chitragupta/bib_reader.py` is the only module that does (AGENTS.md), which
is why the fields an entry needs beyond title/year (authors, venue, volume,
pages, publisher) travel through the ledger's `bib_fields` column rather
than being re-read from the bib file here.

Only ever lists citekeys the draft already cites (found with
`citation_gate`'s own extraction regexes), so it can never introduce a
citekey that hasn't already passed the gate. Run this *after*
`python -m chitragupta.draft gate` has reported `OK`. A cited key with no
matching ledger row is a hard error (AGENTS.md's citekey invariant), not
something to silently drop.

Entries are numbered IEEE-style ("[1] J. Doe and R. Roe, "Title," IEEE
Trans. Testing, vol. 1, pp. 1-10, 2021.") and ordered by first appearance
in the draft, which is the order pandoc's own citeproc numbers citations
in -- so this list and the rendered PDF's bibliography agree on which
source is [1]. Each entry keeps its citekey in a trailing code span:
inline citations in the draft source are still `[@citekey]`, so the key is
what makes an entry traceable from the text, and a code span is invisible
to `citation_gate` (it blanks code spans before scanning), so listing a
key here can never look like citing it.

For a reader who wants numbers inline as well, `numbered_markdown` (used
by `render_output --format md`) returns a *derived* copy with every
`[@citekey]` replaced by its number. That copy is never the draft: the
draft's literal citekeys are what `citation_gate` verifies and what
pandoc resolves, and a numbered body would leave the gate reporting
"0 citations ... OK" on a draft it can no longer check at all.

Usage:
    python -m chitragupta.draft references <file.md> [--heading TEXT]
Appends a References section, or replaces one if this was already run on
the file (idempotent) -- built from exactly the citekeys `<file.md>`
cites.
"""

import argparse
import json
import re
import sys
from pathlib import Path

from chitragupta import citation_gate, config, ledger
from chitragupta.references_ieee import format_entry
from chitragupta.references_renumber import renumber

# Re-exported, not used here: tests/test_references.py reaches this as
# references._format_numbers directly.
# pylint: disable=unused-import
from chitragupta.references_renumber import _format_numbers  # noqa: F401

# pylint: enable=unused-import

# Matches the References heading this module writes, bare ("## References")
# or numbered to match a draft's own heading convention ("## 6. References"),
# at any heading level -- used both to detect an existing section (for
# render_output.py, which strips it before handing the draft to pandoc)
# and to find where to splice in a replacement.
#
# The section number is multi-level (`\d+(?:\.\d+)*`), not a single digit
# group: a book numbers its headings per chapter, so every chapter of a
# book-length draft ends in "## 1.14 References", which an earlier
# `(?:\d+[.)]\s*)?` did not match. The consequence was silent and
# expensive -- `section_start` returned None, so the whole bibliography
# stayed in the draft for every caller that acts on it. For
# `verbatim_check.scan` that meant scanning the reference list against
# the corpus, where two documents citing the same paper share its title
# and venue verbatim: on this project's own 15-chapter book that was
# 97.7% of all findings and 100% of the long-run bucket, none of them
# reuse. The trailing separator stays optional because "1.14 References"
# carries none, while "6. References" and "6) References" still do.
_HEADING_RE = re.compile(r"^#{1,6}\s*(?:\d+(?:\.\d+)*[.)]?\s*)?References\s*$", re.IGNORECASE)

# Any Markdown ATX heading, for section_end below -- deliberately not
# level-restricted: a heading nested under References (e.g. an
# "### Acknowledgments" some genre skill emits right after the
# bibliography) still marks where the References section stops, the same
# "next heading, any level" extent dossier.sections() uses for its own
# outline.
_ANY_HEADING_RE = re.compile(r"^#{1,6}\s")


def used_citekeys(text: str) -> list[str]:
    """Every citekey cited in `text`, deduped, in order of first appearance.

    First-appearance order rather than alphabetical because the numbers
    this list gets ([1], [2], ...) have to be the same numbers pandoc's
    citeproc assigns when the same draft is rendered to PDF, and citeproc
    numbers by first appearance. Sorted order would produce a Markdown
    list whose [4] is the PDF's [7].
    """
    seen: dict[str, None] = {}
    for _, key in citation_gate.extract_citekeys(text):
        seen.setdefault(key, None)
    return list(seen)


def has_section(text: str) -> bool:
    return section_start(text.splitlines(keepends=True)) is not None


def section_start(lines: list[str]) -> int | None:
    """Index of the References heading in `lines`, or None.

    A heading inside a fenced code block doesn't count. Both callers act
    on the answer destructively -- `apply` replaces everything from here
    down, and render_output strips it from what pandoc sees -- so a
    tutorial that *shows* a `## References` line in an example would
    otherwise have the rest of its lesson silently truncated.
    citation_gate's own code-blanking is what the gate uses to avoid the
    same class of false positive, and it preserves line structure, so
    indices still line up with `lines`.
    """
    blanked = citation_gate._blank_code("".join(lines)).splitlines()
    for i, line in enumerate(blanked):
        if _HEADING_RE.match(line.strip()):
            return i
    return None


def section_end(lines: list[str], start: int) -> int:
    """Index of the next heading line after `lines[start]` (of any
    level), or `len(lines)` if none follows -- i.e. `lines[start:end]` is
    the whole section `lines[start]` heads, heading included.

    General-purpose despite living beside the References-specific helpers
    above -- every caller passes `section_start`'s return, but nothing
    here requires that heading to be References specifically. The same
    "next heading, any level" extent `chitragupta/dossier/_sections.py`'s
    `sections()` computes for its own outline, kept as a separate,
    smaller implementation here rather than importing the dossier
    (drafting-review) layer from this corpus-adjacent module.

    Every caller used to treat "the References heading" as "to end of
    file" -- `apply`/`numbered_markdown` deleted whatever came after it,
    `render_output` stripped it from what pandoc sees, and the verbatim
    scanner masked it from detection. All three silently lost or hid an
    appendix or acknowledgments section introduced by its own heading
    after References, which is not part of it (M-8/m-33/m-34). Fence-aware
    the same way section_start is, and for the same reason: a `#` shown
    inside a code example must not end the section early.
    """
    blanked = citation_gate._blank_code("".join(lines)).splitlines()
    for i in range(start + 1, len(blanked)):
        if _ANY_HEADING_RE.match(blanked[i].strip()):
            return i
    return len(lines)


def entries(citekeys: list[str], con) -> dict[str, str]:
    """citekey -> its IEEE entry, without a number, for every key given.

    The one place this project turns a set of citekeys into formatted
    bibliography entries, and the one place a cited key with no ledger
    row is refused. `build_section` numbers what this returns;
    `chitragupta/evidence_appendix.py` uses the same entries as the
    attribution line above each quoted span, so a reference list and an
    evidence sidecar built from the same draft name their sources
    identically rather than in two spellings that could drift.

    A missing row is a hard error (AGENTS.md's citekey invariant), never
    a silently dropped entry.
    """
    placeholders = ",".join("?" * len(citekeys))
    rows = {
        citekey: (title, year, bib_fields)
        for citekey, title, year, bib_fields in con.execute(
            f"SELECT citekey, title, year, bib_fields FROM items WHERE citekey IN ({placeholders})",
            citekeys,
        )
    }
    missing = [k for k in citekeys if k not in rows]
    if missing:
        raise KeyError(
            "citekey(s) cited in the draft but missing from the ledger -- "
            "run `python -m chitragupta.corpus sync`, or re-check "
            "`python -m chitragupta.draft gate` "
            f"was run and passed first: {', '.join(missing)}"
        )

    built = {}
    for key in citekeys:
        title, year, bib_fields = rows[key]
        # A row written before the bib_fields column existed stores NULL;
        # a value that isn't valid JSON would mean a hand-edited ledger.
        # Both fall back to the title/year columns rather than failing --
        # the next `python -m chitragupta.corpus sync` repopulates either one.
        try:
            fields = json.loads(bib_fields) if bib_fields else {}
        except (TypeError, ValueError):
            fields = {}
        built[key] = format_entry(key, title, year, fields)
    return built


def build_section(
    citekeys: list[str], con, heading: str = "References", label_citekeys: bool = True
) -> str:
    """The References section for `citekeys`, numbered in the given order.

    `label_citekeys` appends each entry's key in a code span. On by
    default, because in the *draft* the inline markers are `[@citekey]`
    and the label is what ties one to its entry. The numbered copy
    (`numbered_markdown`) turns it off: there the inline markers are
    numbers, the numbers already index this list, and a trailing key
    would just be noise to a reader.
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

    The draft keeps `[@citekey]` markers -- they are what
    `citation_gate` verifies, and what pandoc resolves when rendering --
    so this returns a *derived* copy for a reader who wants numbered
    Markdown rather than a PDF. Both are numbered by first appearance,
    so this copy, the draft's own reference list, and the rendered PDF
    all agree on which source is [1].

    Any existing References section is rebuilt rather than renumbered:
    the entries have to match the numbering this just applied, and
    rebuilding from the ledger is the only way to be sure they do. The
    draft's own heading text is reused when it has one, so a chapter
    numbering its headings (`## 6. References`) keeps doing so.
    """
    keys = used_citekeys(text)
    # Checked before anything is removed. A draft with no citations has
    # nothing to number and nothing to rebuild, so it comes back exactly
    # as it went in -- otherwise a document that merely *has* a section
    # matching the heading (a hand-written "References" of URLs, say)
    # would come back with that section silently deleted.
    if not keys:
        return text

    lines = text.splitlines(keepends=True)
    index = section_start(lines)
    tail = ""
    if index is not None:
        if heading is None:
            heading = re.sub(r"^#+\s*", "", lines[index].strip())
        # M-8: only the References section itself is dropped here, not
        # everything after it -- an appendix or acknowledgments section
        # introduced by its own heading is not part of References.
        tail = "".join(lines[section_end(lines, index) :])
        text = "".join(lines[:index]).rstrip() + "\n"

    numbering = {key: number for number, key in enumerate(keys, start=1)}
    body = renumber(text, numbering)
    section = build_section(keys, con, heading or "References", label_citekeys=False)
    result = body.rstrip() + "\n\n" + section
    if tail.strip():
        # A citekey cited only in the tail (an appendix citing a source
        # References didn't already cover) still needs the same
        # first-appearance numbering applied to the body above --
        # `used_citekeys` was read from the whole original text, so its
        # number is already in `numbering` and its entry already in
        # `section`.
        result = result.rstrip() + "\n\n" + renumber(tail, numbering).lstrip("\n")
    return result


def write_numbered(path: Path, out_dir: Path, text: str | None = None) -> Path:
    """Writes `path`'s numbered copy into `out_dir`, returning its path.

    `text` overrides what's read from `path` -- `render_output.render`'s
    own `--format md` path passes its figure-substituted copy through here
    rather than letting this re-read the unsubstituted draft from disk,
    since that path never reaches the substitution pandoc's callers get.
    """
    if text is None:
        text = path.read_text(encoding="utf-8")
    with ledger.connection() as con:
        rendered = numbered_markdown(text, con)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{path.stem}.md"
    out_path.write_text(rendered, encoding="utf-8")
    return out_path


def apply(path: Path, heading: str = "References") -> str:
    path = config.require_inside_content(path)
    text = path.read_text(encoding="utf-8")
    keys = used_citekeys(text)
    if not keys:
        return f"{path}: no citekeys cited -- nothing to do"

    with ledger.connection() as con:
        section = build_section(keys, con, heading)

    lines = text.splitlines(keepends=True)
    idx = section_start(lines)
    if idx is None:
        head, tail = text, ""
    else:
        # M-8: only the old References section is replaced -- an
        # appendix or acknowledgments section introduced by its own
        # heading after it is not part of References and must survive.
        head = "".join(lines[:idx])
        tail = "".join(lines[section_end(lines, idx) :])
    new_text = head.rstrip() + "\n\n" + section.rstrip() + "\n"
    if tail.strip():
        new_text = new_text.rstrip() + "\n\n" + tail.lstrip("\n")
    path.write_text(new_text, encoding="utf-8")
    return f"{path}: wrote References section with {len(keys)} citekey(s)"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m chitragupta.draft references",
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
    except (KeyError, config.OutsideContentDir) as exc:
        # Both are "this draft can't be processed, and here is why" rather
        # than a bug: a citekey the ledger doesn't hold, or a path outside
        # content/. Reported on stderr like any other refusal instead of
        # as a traceback.
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    return 0
