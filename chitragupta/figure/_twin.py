"""Twin agreement (#1056): whether a figure's ASCII twin names what its
TikZ names.

The hand-written `<name>.txt` is the only figure md/docx/html readers see, and
it drifts. Four rules, read from source alone (`_labels.py`):

- `twin-missing`: not allowable; the three comparisons are then not measured.
- `t1-labels`: every name (a label's first line, zone title, legend entry)
  appears; glosses are not compared, as twins reword them to fit.
- `t2-tags`: every line of every node placed on a path, by position, since
  drafts tag edges with several styles.
- `t3-panels`: the `(a)`, `(b)` letters match the twin's letter tokens.

"Appears" means every word, whole-word, case-insensitive, any order: ASCII
boxes wrap and interleave, and substring matching missed 140 of 651 lines on
the reference book versus 11 (mostly real) for words. Maths is dropped.
Edge topology and glosses stay eyeball checks.
"""

import re
from dataclasses import dataclass

from chitragupta.figure._labels import arguments, drawing, macro_calls, nodes
from chitragupta.figure._rules import Finding

NO_TWIN = "no twin"
COMPARISONS = ("t1-labels", "t2-tags", "t3-panels")

_MATH_RE = re.compile(r"(?<!\\)\$.*?(?<!\\)\$|\\\(.*?\\\)", re.DOTALL)
_BREAK_RE = re.compile(r"\\\\\s*(?:\[[^\]]*\])?")
_ACCENT_RE = re.compile(r"\\['`^\"~=.](?=\{?[a-zA-Z])")
_SPACE_RE = re.compile(r"\\[,;:! ]|~")
_ESCAPED_RE = re.compile(r"\\([&%_#$])")
# A command whose first argument is not text (colour, length, angle, scale),
# with any optional argument before it.
_NOT_TEXT_RE = re.compile(
    r"\\(?:textcolor|color|hspace|vspace|rotatebox|scalebox)\*?\s*(?:\[[^\]]*\]\s*)?\{[^}]*\}"
)
_CGLAB_RE = re.compile(r"\\cglab(?![a-zA-Z])")
_COMMAND_RE = re.compile(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?")
_WORD_RE = re.compile(r"[^\W_]+")
_PANEL_LINE_RE = re.compile(r"^\(([a-z])\)")
_PANEL_TOKEN_RE = re.compile(r"(?<![\w(])\(([a-z])\)(?![\w)])")


@dataclass(frozen=True)
class Text:
    """One string the twin must carry, and what a finding names it by: the
    node's name, an edge's ends (`a->b`), or the text itself."""

    target: str
    text: str


def plain(label: str) -> list[str]:
    """A label's lines as a reader sees them: markup stripped, maths
    dropped, whitespace collapsed, empty lines left out."""
    return [line for line in _lines(label) if line]


def _first(label: str) -> str:
    """A label's first line, `""` where it is maths or markup alone (so the
    gloss is not promoted to a name)."""
    return _lines(label)[0]


def _lines(label: str) -> list[str]:
    # A newline in the source is a space to TeX; only `\\\\` breaks a line.
    # Breaks before maths: in `\\\\$x$` the `$` would read as escaped.
    text = _MATH_RE.sub(" ", _BREAK_RE.sub("\n", _two_tier(label.replace("\n", " "))))
    text = _SPACE_RE.sub(" ", _ACCENT_RE.sub("", text))
    text = _NOT_TEXT_RE.sub("", text)
    text = _ESCAPED_RE.sub(r"\1", text)
    text = _COMMAND_RE.sub("", text)
    text = text.replace("{", "").replace("}", "")
    return [re.sub(r"\s+", " ", line).strip() for line in text.split("\n")]


def _two_tier(text: str) -> str:
    """Each `\\cglab{name}{gloss}` as the two lines it sets."""
    call = _CGLAB_RE.search(text)
    if call is None:
        return text
    args, end = arguments(text, call.end(), 2)
    return text[: call.start()] + "\\\\".join(args) + _two_tier(text[end:])


def words(text: str) -> set[str]:
    return set(_words(text))


def _words(text: str) -> list[str]:
    """`text`'s words in order, minus any with non-ASCII letters (`µs`): §10
    holds the twin to 7-bit, so no twin could carry them."""
    return [word for word in _WORD_RE.findall(text.lower()) if word.isascii()]


def names(source: str) -> list[Text]:
    body = drawing(source)
    found = []
    for node in nodes(body):
        first = _first(node.label)
        if first and not node.on_path:
            found.append(Text(node.name or first, first))
    for name, text in macro_calls(body, "cgzonelabel", 3, 0, 2) + macro_calls(
        body, "cglegenditem", 4, 0, 3
    ):
        found += [Text(name, _first(text))] if _first(text) else []
    return found


def tags(source: str) -> list[Text]:
    found = []
    for node in nodes(drawing(source)):
        if node.on_path:
            found += [Text(node.ends or line, line) for line in plain(node.label)]
    return found


def panels_tex(source: str) -> set[str]:
    lines = [line for node in nodes(drawing(source)) for line in plain(node.label)]
    return {match.group(1) for line in lines if (match := _PANEL_LINE_RE.match(line))}


def panels_twin(twin: str) -> set[str]:
    return set(_PANEL_TOKEN_RE.findall(twin))


def agree(
    source: str, twin: str | None, twin_name: str
) -> tuple[list[Finding], list[tuple[str, str]]]:
    """`(findings, not_measured)` for the four twin rules; `twin` is `None`
    where there is no file."""
    if twin is None:
        missing = Finding("twin-missing", "figure", f"no {twin_name} beside the figure")
        return [missing], [(rule, NO_TWIN) for rule in COMPARISONS]
    present = words(twin)
    findings = _absent("t1-labels", names(source), present)
    findings += _absent("t2-tags", tags(source), present)
    tex, ascii_ = panels_tex(source), panels_twin(twin)
    if tex != ascii_:
        findings.append(
            Finding("t3-panels", "figure", f"tex {_letters(tex)}; twin {_letters(ascii_)}")
        )
    return findings, []


def _absent(rule: str, texts: list[Text], present: set[str]) -> list[Finding]:
    found = []
    for text in texts:
        # A panel letter is `t3-panels`' to compare, not a word of the name.
        said = _PANEL_LINE_RE.sub("", text.text.lower())
        lacking = [word for word in _words(said) if word not in present]
        if lacking:
            found.append(
                Finding(rule, text.target, f'missing "{" ".join(dict.fromkeys(lacking))}"')
            )
    return found


def _letters(letters: set[str]) -> str:
    return ", ".join(f"({letter})" for letter in sorted(letters)) or "none"
