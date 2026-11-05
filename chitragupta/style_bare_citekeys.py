"""The `python -m chitragupta.draft style` finding for a citekey printed raw.

A ledger citekey written without its `@` ("the frameworks
gil_survey_2024 evaluates") or in a code span (`` `obaidat_hubcap_2022` ``)
is not a citation, so the gate, which counts citations, passes it, and
the PDF prints the key itself, where a reader can resolve nothing (#1119).
Both reached a user's drafts the same way: a drafting agent that wanted a
paper as a noun wrote its key, and a reviser remarking on the corpus
copied the dossier's own `` `key` `` notation into the prose.

**Advisory, like every style rule.** DEVELOPER-AGENTS.md bars a second
gate beside `chitragupta/citation_gate.py`, and the gate stays strict
about what *is* cited. There is no silencer: a reader-facing draft has no
legitimate bare key (docs/WRITING-STANDARDS.md §16).

**Only what a reader sees is read.** Measured over 77 real drafts, a
plain token match found 786 bare keys and 785 were noise: the
`` [n] entry `key` `` labels `references.build_section` writes (render
strips that section before pandoc), and keys inside
`<!-- single-source: ... -->` comments. So the References section is
blanked, then everything pandoc does not read as prose, then every
citation by its span, and only what is left is scanned.

**Which keys.** Every ledger row, parsed or not: an unparsed key printed
raw is still a defect, only one whose repair is not to cite it. Only a
key with a digit, `_` or `:` is looked for, so a pure-letter key such as
`smith` is never matched against the ordinary word.
"""

import re
import sqlite3
from pathlib import Path

from chitragupta import _markdown_inert, _pandoc_cites, citation_gate, ledger
from chitragupta import references_section, style_elements
from chitragupta.ledger_citable import unparsed_citekeys
from chitragupta.render_output import _paths
from chitragupta.render_output._tables import line_of

RULES = {"bare-citekey": "chitragupta.BareCitekey"}

# A key-shaped token, whole: not preceded by a character that could
# continue a key or open a citation, so `doe_2024` is never found inside
# `doe_2024-1` or `x.doe_2024`. In a `.tex` unit an underscore is written
# `\_`, which the second pattern accepts and the lookup strips.
_BEFORE = r"(?<![\w@\-:.#$%&+?<>~/\\])"
_MD_TOKEN_RE = re.compile(_BEFORE + _pandoc_cites.PANDOC_KEY)
_TEX_TOKEN_RE = re.compile(_BEFORE + r"[A-Za-z0-9](?:\w|\\_|-+(?=\w)|[:.](?=\w))*")
_LOOKED_FOR_RE = re.compile(r"[\d_:]")

# A code span whose whole content is one token, and LaTeX's own form.
_CODE_SPAN_RE = re.compile(r"(`+)\s*([^`\s]+)\s*\1")
_TEXTTT_RE = re.compile(r"\\texttt\{([^{}\s]+)\}")


def _blank(text: str, start: int, end: int) -> str:
    """`text` with [start, end) blanked to spaces, newlines kept."""
    return text[:start] + re.sub(r"[^\n]", " ", text[start:end]) + text[end:]


def _ledger_keys() -> "tuple[set[str], dict[str, str]] | None":
    """(every ledger key worth looking for, the unparsed ones' statuses),
    or None when there is no ledger to read."""
    try:
        with ledger.reading() as con:
            known, unparsed = ledger.known_citekeys(con), unparsed_citekeys(con)
    except (ledger.NoLedger, ledger.StaleLedger, ledger.UnreadableLedger, sqlite3.Error):
        return None
    return {key for key in known if _LOOKED_FOR_RE.search(key)}, unparsed


def _without_references(text: str) -> str:
    lines = text.splitlines(keepends=True)
    start = references_section.section_start(lines)
    if start is None:
        return text
    end = references_section.section_end(lines, start)
    offset = sum(len(line) for line in lines[:start])
    return _blank(text, offset, offset + sum(len(line) for line in lines[start:end]))


def _without_citations(prose: str, labels: set, source: str, latex: bool) -> str:
    spans = [
        (start, end)
        for start, end, _ in _pandoc_cites.citations(prose, labels, latex=latex, source=source)
    ]
    spans += [match.span() for match in citation_gate._LATEX_CITE_RE.finditer(prose)]
    for start, end in spans:
        prose = _blank(prose, start, end)
    return prose


def _finding(key: str, line: int, where: str, unparsed: dict, latex: bool) -> dict:
    cite = f"\\citep{{{key}}}" if latex else f"[@{key}]"
    if where == "code":
        message = (
            f"`{key}` is a ledger citekey set as code, so the reader sees a key "
            "they cannot resolve. If this is a note about the corpus, move it to "
            f"the dossier's revisions.md; if it means to cite the paper, write {cite} "
            "(WRITING-STANDARDS.md §16)."
        )
        return style_elements.finding(RULES, "bare-citekey", key, line, message, "review")
    if key not in unparsed:
        message = (
            f"`{key}` is a ledger citekey written as plain text, so it prints raw. "
            f"Write {cite} instead, IEEE's numbered citation used as a noun "
            f'("In {cite}, the authors ...") (WRITING-STANDARDS.md §16).'
        )
        return style_elements.finding(RULES, "bare-citekey", key, line, message)
    message = (
        f"`{key}` is a ledger citekey written as plain text, but it has no parsed "
        f"PDF (status {unparsed[key]}), so it cannot be cited either. Reword the "
        "sentence without it, or cite a parsed source (WRITING-STANDARDS.md §16)."
    )
    return style_elements.finding(RULES, "bare-citekey", key, line, message, "review")


def _tokens(scan: str, pattern: "re.Pattern", keys: set) -> "list[tuple[int, str]]":
    found = []
    for match in pattern.finditer(scan):
        # PANDOC_KEY may open with `*`, so `*doe_2024*` (emphasis) matches
        # as `*doe_2024`; the key itself starts after the asterisks.
        token = match.group(0)
        key = token.lstrip("*").replace("\\_", "_")
        if key in keys:
            found.append((match.start() + len(token) - len(token.lstrip("*")), key))
    return found


def _tex_hits(text: str, keys: set) -> "list[tuple[int, str, str]]":
    """(offset, key, "prose" | "code") for a `.tex` unit: comments and
    verbatim blanked, then every `\\cite`-family command."""
    prose = citation_gate._blank_code(text, latex=True, prose_only=True)
    prose = _without_citations(prose, set(), text, latex=True)
    hits = []
    for match in _TEXTTT_RE.finditer(prose):
        key = match.group(1).replace("\\_", "_")
        if key in keys:
            hits.append((match.start(), key, "code"))
        prose = _blank(prose, *match.span())
    return hits + [(at, key, "prose") for at, key in _tokens(prose, _TEX_TOKEN_RE, keys)]


def _markdown_hits(text: str, keys: set) -> "list[tuple[int, str, str]]":
    """The same for Markdown, whose `text` has its References blanked."""
    prose, labels = citation_gate.markdown_prose(text)
    prose = _without_citations(prose, labels, text, latex=False)
    hits = [(at, key, "prose") for at, key in _tokens(prose, _MD_TOKEN_RE, keys)]
    for start, end in _markdown_inert.non_prose_spans(text, code_only=True):
        match = _CODE_SPAN_RE.fullmatch(text[start:end])
        if match and match.group(2) in keys:
            hits.append((start, match.group(2), "code"))
    return hits


def findings(draft: Path) -> "list[dict]":
    """One finding per ledger citekey a reader would see printed raw."""
    ledger_keys = _ledger_keys()
    if ledger_keys is None:
        return []
    keys, unparsed = ledger_keys
    text = draft.read_text(encoding="utf-8")
    latex = draft.suffix.lower() not in _paths._MARKDOWN_SUFFIXES
    if not latex:
        text = _without_references(text)
    hits = sorted(_tex_hits(text, keys) if latex else _markdown_hits(text, keys))
    return [_finding(key, line_of(text, at), where, unparsed, latex) for at, key, where in hits]
