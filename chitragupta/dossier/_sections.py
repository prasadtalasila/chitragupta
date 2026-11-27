"""Markdown/LaTeX heading parsing and the `Section` shape everything
else in this package attributes citekeys against."""

import argparse
import re
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from chitragupta import _pandoc_cites, citation_gate
from chitragupta.dossier import SECTIONS_MD, _SECTIONS_TEMPLATE, dossier_dir, draft_relpath

# A citekey as the dossier templates write one: backticked or `@`-prefixed
# (files settled on different habits, and reading only one form lost
# every section mapping in the shipped example), starting with a letter,
# with at least one run of `_`/`:`/`-` separators. The run is `+` because
# BibTeX can collapse a hyphenated word into a doubled hyphen. No trailing
# year is required (keys can end in `_nodate`).
#
# A false *negative* is the worse failure (a cited key reported "never
# considered"). But this set is also differenced the other way to find
# keys that *left* the ledger, where an invented key becomes a false
# broken citation; the separator requirement is the only thing holding
# that line.
_KEY = r"[A-Za-z][A-Za-z0-9]*(?:[_:-]+[A-Za-z0-9]+)+"


_CITEKEY_TOKEN = re.compile(rf"`({_KEY})`|@({_KEY})")


# The same delimiters without the separator requirement (#506/M-28), for
# separator-free reference-manager keys `_KEY` cannot see. Safe only
# because it is read alongside a *known* set of ledger citekeys, and only
# as an addition to the strict scan: a token equal to a real ledger key
# cannot be invented. Charset is the gate's own `PANDOC_KEY`.
_LOOSE_KEY = _pandoc_cites.PANDOC_KEY

_LOOSE_CITEKEY_TOKEN = re.compile(rf"`({_LOOSE_KEY})`|@({_LOOSE_KEY})")


def _citekeys(text: str, known: "set[str] | None" = None) -> list[str]:
    """Every citekey token in `text`, in either delimiter, in order.

    Pass `known` (the ledger's citekeys) on any path that differences
    against that ledger, so separator-free keys are read too. A union of
    both scans, never a filtered loose scan: the loose grammar reads a key
    followed by `.v2` as one token, which would lose the strict match
    inside it.
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


# Headings for outline extraction, deliberately not shared with
# citation_provenance.py's block regexes (it needs list items and table
# rows as blocks). The ATX closing `##` is stripped in `sections()`, not
# by a `\s*#*\s*$` tail, which backtracks super-linearly (Sonar S8786).
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

    Brace-balanced, not a regex: lazy matching truncates at a nested
    `}`, greedy runs into a trailing label. Escapes are consumed as a
    pair so an escaped brace doesn't open a group.
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
    LaTeX verbatim environments, shared so no caller re-derives it."""
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

    Code is skipped first: a `# Step 1` comment inside a fenced block
    would otherwise be a heading and cut a code block in half. Markdown
    and LaTeX are both recognised.
    """
    lines = text.splitlines()
    found: list[Section] = []

    for number, line in _prose_lines(lines):
        md = _MD_HEADING.match(line)
        if md:
            # Same shape as the old `\s*#*\s*$` tail: `## Title ##` and
            # `## Title` both yield "Title"; an interior `#` survives.
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

    Joined on line number. Duplicates collapse in first-cited order. A key
    cited before the first heading is returned separately: attributing it
    to a section that does not contain it would mislead a reviser.
    """
    outline = sections(text)
    per_section: list[tuple[Section, list[str]]] = [(section, []) for section in outline]
    unattributed: list[str] = []
    # LaTeX-aware blanking (backtick is a quote there), or a citation
    # between LaTeX quotes silently vanished.
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

    Deterministic, so it is regenerated rather than maintained. A pipe in
    a heading is escaped so the round trip returns the heading as written.
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
        # Refused: writing the bare outline into sections.md would replace
        # the citekey relation with a heading list.
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

    Exit 1 with no headings, so a piping caller hears about it rather
    than writing an empty file.
    """
    latex = citation_gate.is_latex(draft)
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
        # Said out loud: a reviser reading only the table would never learn
        # of a citekey cited above the first heading.
        print(
            "Cited before the first heading, so in no section: "
            + ", ".join(f"`{key}`" for key in unattributed),
            file=sys.stderr,
        )
    return 0
