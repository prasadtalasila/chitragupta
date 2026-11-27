"""The `python -m chitragupta.draft style` finding for an acronym's
expansion written in a different case from the vocabulary (#1187).

The case in `content/acronyms.toml` is authoritative: capitalised means a
proper name, lower case a common noun. Advisory (`repair="review"`), since
whether the vocabulary or the draft is wrong is a person's call. The one
tolerance is a first letter capitalised at a sentence or heading start.
Code and the References section are blanked first, offsets kept.
"""

import re
from pathlib import Path

from chitragupta import acronyms, citation_gate, style_elements
from chitragupta.render_output._tables import line_of

RULES = {"acronym-case": "chitragupta.AcronymCase"}

# Indentation and one list or quote marker before a line-start phrase.
_LINE_START_RE = re.compile(r"(?:^|\n)[ \t]*(?:(?:[-*+>]|\d+[.)])[ \t]+)*\Z")
_SENTENCE_START_RE = re.compile(r"[.!?]\s+\Z")
_HEADING_RE = re.compile(r"\s*(?:#{1,6}\s|\\(?:chapter|(?:sub)*section)\b)")


def _pattern(expansion: str, acronym: str) -> re.Pattern:
    """The expansion, whatever its case and wherever a wrap falls, then
    `(ACRO)`. Fully escaped: a user's expansion may carry anything."""
    words = r"\s+".join(re.escape(word) for word in expansion.split())
    return re.compile(rf"(?<!\w)({words})\s*\({re.escape(acronym)}\)", re.IGNORECASE)


def _tolerated(text: str, match: re.Match, expansion: str) -> bool:
    """Only the first letter differs, capitalised, at a sentence or heading
    start. The reverse flip is a real case error (#1187)."""
    written = " ".join(match.group(1).split())
    wanted = " ".join(expansion.split())
    if written[1:] != wanted[1:] or not (written[0].isupper() and wanted[0].islower()):
        return False
    before = text[: match.start()]
    line_start = text.rfind("\n", 0, match.start()) + 1
    return bool(
        _LINE_START_RE.search(before)
        or _SENTENCE_START_RE.search(before)
        or _HEADING_RE.match(text, line_start)
    )


def _prose(draft: Path) -> str:
    """The draft with code blanked and the References section cut."""
    text = draft.read_text(encoding="utf-8")
    text = citation_gate._blank_code(text, latex=citation_gate.is_latex(draft))
    heading = acronyms._REFERENCES_HEADING.search(text)
    return text[: heading.start()] if heading else text


def findings(draft: Path) -> list[dict]:
    """One finding per distinct (acronym, phrase), at its first line."""
    text = _prose(draft)
    found: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for acronym, expansion in acronyms.load_vocabulary().items():
        for match in _pattern(expansion, acronym).finditer(text):
            written = " ".join(match.group(1).split())
            if written == " ".join(expansion.split()) or (acronym, written) in seen:
                continue
            if _tolerated(text, match, expansion):
                continue
            seen.add((acronym, written))
            message = (
                f"'{written}' is written before ({acronym}), but the vocabulary spells "
                f"it '{expansion}'; case is authoritative: capitalised is a proper "
                "name, lower case a common noun (WRITING-STANDARDS.md §9)."
            )
            found.append(
                style_elements.finding(
                    RULES, "acronym-case", written, line_of(text, match.start()), message, "review"
                )
            )
    return sorted(found, key=lambda f: f["line"])
