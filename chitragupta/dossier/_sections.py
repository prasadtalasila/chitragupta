"""Markdown/LaTeX heading parsing and the `Section` shape everything
else in this package attributes citekeys against.

Split out of chitragupta/dossier.py (#219). `_cmd_sections` and
`_sections_citekeys` live here rather than in a shared CLI module
because they are this module's whole reason to have a CLI surface at
all -- `sections()`/`attribute_citekeys()` computed for a human to read
is exactly what the `dossier sections` command is.
"""

import argparse
import re
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from chitragupta import citation_gate
from chitragupta.dossier import SECTIONS_MD, _SECTIONS_TEMPLATE, dossier_dir, draft_relpath

# A citekey as the dossier templates write one: inside backticks, starting
# with a letter, and carrying at least one run of `_`/`:`/`-` separators
# followed by more alphanumerics -- the shape BibTeX gives a key
# (`talasila_composable_2025`). Requiring a separator is what keeps
# ordinary backticked prose out: `status` and `content` have none, and
# `--force` also fails the letter start.
#
# The separator run is `+`, not a single character, because a real key in
# this project's own corpus is `zech_digital-twins-as--service_2024` --
# BibTeX collapses "as-a-service" into a doubled hyphen. Matching only one
# separator dropped it silently.
#
# Both delimiters, because the dossier is written by hand and by two
# different habits. No template shows an example row, so each file settled
# on whatever the skill filling it in reached for: `evidence.md` headings
# are backticked, while `sections.md` copies the form the draft cites with
# (`@key`). Reading only the backticked form lost every section mapping in
# the shipped example dossier, which is what made `missing` report a
# departed citekey with no sections to go and edit.
#
# A false *negative* is the worse failure, and always was: this set is
# subtracted from the ledger's citekeys to find what a dossier never
# considered, so a prose token that looks key-shaped (`draft-reviser`) is
# inert -- it is not in the ledger, so subtracting it changes nothing,
# while a missed real key gets reported as "never considered" when it was
# cited. False positives are no longer entirely free, though: since the
# drift report, this same set is also differenced the other way to find
# citekeys that have *left* the ledger, where an invented one would be
# reported as a broken citation that isn't. The separator requirement is
# what holds that line, and it is the *only* thing holding it: a match
# needs a letter start and at least one `_`/`:`/`-` run followed by more
# alphanumerics, so `@someone` and `@2` are not keys while
# `@noauthor_digital_nodate` is. Nothing here requires a trailing year --
# a real key in this corpus ends in `_nodate`.
_KEY = r"[A-Za-z][A-Za-z0-9]*(?:[_:-]+[A-Za-z0-9]+)+"


_CITEKEY_TOKEN = re.compile(rf"`({_KEY})`|@({_KEY})")


# The same two delimiters with the separator requirement dropped. This is
# only ever read alongside a *known* set of ledger citekeys (#506/M-28):
# `Knuth1984` and `Lamport94` are the default style of several reference
# managers, and `_KEY` cannot see them at all, so a dossier written that
# way contributed nothing to any parse -- a cited paper leaving the corpus
# was never reported in `drift().missing`, which is the exact false
# negative the comment above calls the worse failure.
#
# Membership in the ledger, not shape, is what makes these safe to accept:
# the reason `_KEY` needs a separator is that a shapeless token could be
# prose (`@someone`) invented into a broken-citation report, and a token
# that equals a real ledger citekey cannot be invented by construction.
# So this pattern is deliberately never used on its own -- it is read only
# alongside `known`, and only ever as an *addition* to the strict scan.
_LOOSE_KEY = r"[A-Za-z][A-Za-z0-9_:-]*"

_LOOSE_CITEKEY_TOKEN = re.compile(rf"`({_LOOSE_KEY})`|@({_LOOSE_KEY})")


def _citekeys(text: str, known: "set[str] | None" = None) -> list[str]:
    """Every citekey token in `text`, in either delimiter, in order.

    Pass `known` -- a ledger's citekeys -- on any path that differences
    this result against that ledger, and separator-free keys spelled
    exactly as the ledger spells them are read too.

    A union of the two scans, never a substitution of one for the other.
    Filtering a single loose scan by "in `known`, or strictly key-shaped"
    reads like the same thing and is not: `_LOOSE_KEY` is greedy over
    `[_:-]`, so `@smith_x_2024:` tokenises as `smith_x_2024:`, which is
    neither in the ledger nor a strict match -- and a key the strict scan
    had always found would have been *lost* the moment a caller passed
    `known`. That is a new false negative in the direction the comment
    above calls the worse failure, arriving with the fix for one.
    """
    strict = [backticked or at_form for backticked, at_form in _CITEKEY_TOKEN.findall(text)]
    if known is None:
        return strict
    seen = set(strict)
    found = list(strict)
    for backticked, at_form in _LOOSE_CITEKEY_TOKEN.findall(text):
        token = backticked or at_form
        if token in known and token not in seen:
            seen.add(token)
            found.append(token)
    return found


@dataclass
class Section:
    title: str
    level: int
    start: int  # 1-indexed line of the heading itself
    end: int  # 1-indexed last line before the next heading

    @property
    def lines(self) -> int:
        return self.end - self.start + 1


# Headings for *outline extraction*: where does each section start and
# stop, so a revision can Read and Edit one section instead of the whole
# file. chitragupta/review/citation_provenance.py has a similar-looking pair of regexes
# doing a different job -- segmenting claim-bearing blocks for scoring --
# and the two are deliberately not shared: that module needs list items
# and table rows to be blocks, which would be noise in an outline.
# The whole rest of the line is captured and the optional ATX closing
# sequence (`## Title ##`) stripped in `sections()` instead of by a
# `(.*?)\s*#*\s*$` tail here: that tail's adjacent ambiguous quantifiers
# backtrack super-linearly on pathological input (Sonar S8786), and a
# plain-code strip is both linear and easier to confirm faithful.
_MD_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


_TEX_HEADING = re.compile(r"^\s*\\(chapter|(?:sub){0,2}section|paragraph)\*?\{(.*)$")


_TEX_LEVELS = {
    "chapter": 1,
    "section": 2,
    "subsection": 3,
    "subsubsection": 4,
    "paragraph": 5,
}


_FENCE = re.compile(r"^\s*(?:```|~~~)")


_VERBATIM_BEGIN = re.compile(r"\\begin\{(verbatim|lstlisting|minted|Verbatim)\*?\}")


_VERBATIM_END = re.compile(r"\\end\{(verbatim|lstlisting|minted|Verbatim)\*?\}")


def _braced(text: str) -> str:
    """The contents of a `{...}` group, given everything after the `{`.

    Brace-balanced rather than matched by regex, because both regex
    readings are wrong on titles this project actually produces: a lazy
    `.*?` stops at the first `}` and truncates `\\emph{twin}` mid-word, a
    greedy `.*` runs past the closing brace and swallows a trailing
    `\\label{...}`. A backslash escape is consumed as a pair so that a
    literal `\\{` in a title doesn't open a group.
    """
    depth, out, index = 1, [], 0
    while index < len(text):
        char = text[index]
        if char == "\\" and index + 1 < len(text):
            out.append(text[index : index + 2])
            index += 2
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                break
        out.append(char)
        index += 1
    return "".join(out)


def _prose_lines(lines: list[str]) -> Iterator[tuple[int, str]]:
    """(line number, line) for every line outside fenced code blocks and
    LaTeX verbatim environments -- the fence tracking `sections()`'s
    docstring says is not a nicety, shared so no caller re-derives it."""
    in_fence = False
    in_verbatim = False
    for number, line in enumerate(lines, 1):
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if _VERBATIM_BEGIN.search(line):
            in_verbatim = True
        if _VERBATIM_END.search(line):
            in_verbatim = False
            continue
        if not in_fence and not in_verbatim:
            yield number, line


def sections(text: str) -> list[Section]:
    """The draft's outline: one `Section` per heading, with line ranges.

    Code is skipped first, which is not a nicety. `tutorial.md` in the
    shipped example content is mostly shell and Python, and a `# Step 1`
    comment inside a fenced block is indistinguishable from a Markdown
    heading to anything that doesn't track fences -- so an outline built
    without this reports sections that don't exist and hands a reviser
    line ranges that cut a code block in half.

    Markdown and LaTeX are both recognised, since thesis-chapter-writer
    emits `.tex` and the other four emit `.md`.
    """
    lines = text.splitlines()
    found: list[Section] = []

    for number, line in _prose_lines(lines):
        md = _MD_HEADING.match(line)
        if md:
            # Strip whitespace, then one closing-hash run, then the
            # whitespace preceding it -- the same shape the regex's old
            # `\s*#*\s*$` tail matched, so `## Title ##` and `## Title`
            # both yield "Title" while an interior `#` survives.
            title = md.group(2).strip().rstrip("#").rstrip()
            found.append(Section(title, len(md.group(1)), number, number))
            continue
        tex = _TEX_HEADING.match(line)
        if tex:
            found.append(
                Section(
                    _braced(tex.group(2)).strip(),
                    _TEX_LEVELS.get(tex.group(1), 2),
                    number,
                    number,
                )
            )

    for current, following in zip(found, found[1:]):
        current.end = following.start - 1
    if found:
        found[-1].end = len(lines)
    return found


def attribute_citekeys(
    text: str, *, latex: bool = False
) -> tuple[list[tuple[Section, list[str]]], list[str]]:
    """(section, its citekeys) for every heading, plus the unattributed ones.

    The join key is the line number: `sections()` gives each heading a
    line range, `citation_gate.extract_citekeys()` gives every citekey the
    line it was cited on, and the intersection is the relation
    `sections.md` records. Both halves already handle the two syntaxes
    and skip code, so `.md` (`[@key]`) and `.tex` (`\\citep{key}`) need no
    separate treatment here.

    Duplicates collapse, keeping first-cited order -- the file answers
    "which section leans on this paper", and a key cited three times in
    one section is one answer, not three.

    A key cited before the first heading belongs to no section and is
    returned separately rather than dropped or forced into the first row.
    Attributing it to a section that does not contain it would be a wrong
    answer handed to a reviser, which is the failure this whole file
    exists to prevent.
    """
    outline = sections(text)
    per_section: list[tuple[Section, list[str]]] = [(section, []) for section in outline]
    unattributed: list[str] = []
    # latex selects LaTeX-aware code blanking (backtick is a quote there,
    # not code markup) -- without it a citation between two LaTeX-quoted
    # phrases silently vanished from the derived table.
    for line, citekey in citation_gate.extract_citekeys(text, latex=latex):
        for section, keys in per_section:
            if section.start <= line <= section.end:
                if citekey not in keys:
                    keys.append(citekey)
                break
        else:
            if citekey not in unattributed:
                unattributed.append(citekey)
    return per_section, unattributed


def sections_markdown(text: str, *, latex: bool = False) -> str:
    """The finished `sections.md` for a draft, header and all.

    Deterministic, so it can be regenerated rather than maintained: the
    template already says the file is "rebuildable from the draft", and
    this is that sentence made executable. A pipe in a heading is escaped
    rather than left to break the row -- `_ROW_SPLIT` reads `\\|` as
    literal, so the round trip through `citekeys_by_section()` returns
    the heading as written.
    """
    per_section, _ = attribute_citekeys(text, latex=latex)
    rows = "".join(
        f"| {section.title.replace('|', r'\|')} | {', '.join(f'`{key}`' for key in keys)} |\n"
        for section, keys in per_section
    )
    return _SECTIONS_TEMPLATE + rows


def _cmd_sections(args: argparse.Namespace) -> int:
    draft = Path(args.draft)
    if not draft.is_file():
        print(f"No such draft: {draft}", file=sys.stderr)
        return 1
    if args.write and not args.citekeys:
        # Refused rather than assumed: the bare form prints an outline,
        # and writing that into sections.md would replace the citekey
        # relation with a heading list.
        print("--write needs --citekeys.", file=sys.stderr)
        return 1
    text = draft.read_text(encoding="utf-8")
    if args.citekeys:
        return _sections_citekeys(draft, text, args.write)
    outline = sections(text)
    if not outline:
        print(f"No headings in {draft_relpath(draft)}.")
        return 0
    print(f"{draft_relpath(draft)}")
    for section in outline:
        indent = "  " * (section.level - 1)
        span = f"{section.start}-{section.end}"
        print(f"  {span:>12}  ({section.lines:>4} lines)  {indent}{section.title}")
    print("\n  Read one section with offset=<start>, limit=<lines>; edit inside that")
    print("  range rather than rewriting the file.")
    return 0


def _sections_citekeys(draft: Path, text: str, write: bool) -> int:
    """`sections --citekeys`: the derived table, printed or written.

    Exit code 1 when the draft has no headings, because there is then no
    table to build and a caller that piped this somewhere should hear
    about it rather than write an empty file.
    """
    latex = draft.suffix.lower() == ".tex"
    per_section, unattributed = attribute_citekeys(text, latex=latex)
    if not per_section:
        print(f"No headings in {draft_relpath(draft)}.", file=sys.stderr)
        return 1

    table = sections_markdown(text, latex=latex)
    if write:
        target = dossier_dir(draft) / SECTIONS_MD
        if not target.parent.is_dir():
            print(
                f"No dossier for {draft_relpath(draft)} -- run `init` first.",
                file=sys.stderr,
            )
            return 1
        target.write_text(table, encoding="utf-8")
        print(f"{target}: {len(per_section)} section(s) from {draft_relpath(draft)}")
    else:
        print(table, end="")

    if unattributed:
        # Said out loud rather than dropped: a citekey cited above the
        # first heading is real evidence the table cannot place, and a
        # reviser reading only the table would never learn it exists.
        print(
            "Cited before the first heading, so in no section: "
            + ", ".join(f"`{key}`" for key in unattributed),
            file=sys.stderr,
        )
    return 0
