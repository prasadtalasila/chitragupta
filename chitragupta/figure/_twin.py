"""Twin agreement (#1056): whether a figure's ASCII twin names what its
TikZ names.

The twin, `<name>.txt`, is the only figure a reader of the `md`, `docx`
or `html` render sees. It is written by hand beside the TikZ, so the two
drift: a box renamed in one, a tag added to the TikZ and never to the
ASCII. Four rules, read from source alone, so they hold on a host
without TeX and whether or not the figure compiles:

- `twin-missing`: there is no `<name>.txt` beside the figure. Not
  allowable: a figure without a twin is fixed, never excused. The three
  comparisons are then listed as not measured rather than reported
  three times over.
- `t1-labels`: every **name** appears in the twin. A name is a node
  label's first line (`\\cglab`'s first argument), a zone title or a
  legend entry. A gloss is not compared: it is where a twin rewords to
  fit a 20-column box, legitimately.
- `t2-tags`: every line of every node placed on a `\\draw` or `\\path`
  appears in the twin. By position, not by style, because the drafts tag
  their edges with `cgtag`, `lbl` and a bare `node[midway]` alike.
- `t3-panels`: the `(a)`, `(b)`, ... letters opening a label line are
  the set of letter tokens in the twin.

"Appears" is every word of it, as a whole word, case-insensitively and
in any order. Not a substring: an ASCII box wraps a label over lines
and interleaves its neighbour's, and on the reference book's 49 figures
substring matching missed 140 of 651 lines on reflow alone, where word
matching missed 11 names, nearly all real. Maths is dropped before the
comparison, because ASCII cannot spell `\\hat{x}`.

Edge topology stays an eyeball check (the issue), and so does a gloss.
"""

import re
from dataclasses import dataclass

from chitragupta._tex_comments import strip_comments
from chitragupta.figure._block import _END_RE
from chitragupta.figure._rules import Finding
from chitragupta.review.figure_layout._source import _NODE_KEYWORD

# The reason the three comparisons give when there is nothing to compare.
NO_TWIN = "no twin"
COMPARISONS = ("t1-labels", "t2-tags", "t3-panels")

# `_source.py`'s node keyword, plus the `edge node {tag}` form its
# lookbehind leaves out (an `edge` is not a path operator character).
_NODE_START_RE = re.compile(_NODE_KEYWORD + r"|\bedge\b\s*(?:\[[^\]]*\]\s*)?node\b")
_PATH_RE = re.compile(r"\\(?:draw|path)\b")
_AT_RE = re.compile(r"at\b")
# A `\foreach` variable, `\x` or each of `\n/\x`, as `\foreach` declares it.
_LOOP_VAR_RE = re.compile(r"(?:\\foreach\s*|/\s*)(\\[a-zA-Z]+)(?=[\s/]|in\b)")

_MATH_RE = re.compile(r"(?<!\\)\$.*?(?<!\\)\$|\\\(.*?\\\)", re.DOTALL)
_BREAK_RE = re.compile(r"\\\\\s*(?:\[[^\]]*\])?")
_SPACE_RE = re.compile(r"\\[,;:! ]|~")
_ESCAPED_RE = re.compile(r"\\([&%_#$])")
# A command whose first argument is not text: a colour or a length.
_NOT_TEXT_RE = re.compile(r"\\(?:textcolor|color|hspace|vspace)\*?\s*\{[^}]*\}")
_CGLAB_RE = re.compile(r"\\cglab(?![a-zA-Z])")
_COMMAND_RE = re.compile(r"\\[a-zA-Z]+\*?")
_WORD_RE = re.compile(r"[a-z0-9]+")
_PANEL_LINE_RE = re.compile(r"^\(([a-z])\)")
_PANEL_TOKEN_RE = re.compile(r"(?<![\w(])\(([a-z])\)(?![\w)])")
# A name in a path: `(a)`, `(a.south)`, `([xshift=2mm]a.south)`. Not a
# coordinate, which has a comma, and not a calc `($...$)`.
_END_TOKEN_RE = re.compile(r"\(\s*(?:\[[^\]]*\]\s*)?([A-Za-z][\w-]*)(?:\.[\w ]+)?\s*\)")


@dataclass(frozen=True)
class Text:
    """One string the twin must carry, and what a finding names it by:
    the node's name, an edge by its ends (`a->b`), or the text itself
    where there is neither."""

    target: str
    text: str


def plain(label: str) -> list[str]:
    """A label's lines as a reader sees them: markup stripped, maths
    dropped, whitespace collapsed, empty lines left out."""
    # Breaks first: in `\\\\$x$` the `$` follows a backslash and would
    # read as an escaped dollar.
    text = _MATH_RE.sub(" ", _BREAK_RE.sub("\n", _two_tier(label)))
    text = _SPACE_RE.sub(" ", text)
    text = _NOT_TEXT_RE.sub("", text)
    text = _ESCAPED_RE.sub(r"\1", text)
    text = _COMMAND_RE.sub("", text)
    text = text.replace("{", "").replace("}", "")
    lines = (re.sub(r"\s+", " ", line).strip() for line in text.split("\n"))
    return [line for line in lines if line]


def _two_tier(text: str) -> str:
    """Each `\\cglab{name}{gloss}` as the two lines it sets."""
    call = _CGLAB_RE.search(text)
    if call is None:
        return text
    args, end = _arguments(text, call.end(), 2)
    return text[: call.start()] + "\n".join(args) + _two_tier(text[end:])


def words(text: str) -> set[str]:
    """The whole words of `text`, lower-cased: runs of letters and digits."""
    return set(_WORD_RE.findall(text.lower()))


def names(source: str) -> list[Text]:
    """What `t1-labels` compares, in source order."""
    body = _drawing(source)
    found = []
    for node in _nodes(body):
        lines = plain(node.label)
        if lines and not node.on_path:
            found.append(Text(node.name or lines[0], lines[0]))
    for name, text in _macro(body, "cgzonelabel", 3, 0, 2) + _macro(body, "cglegenditem", 4, 0, 3):
        found += [Text(name, line) for line in plain(text)[:1]]
    return found


def tags(source: str) -> list[Text]:
    """What `t2-tags` compares: every line of every node on a path."""
    found = []
    for node in _nodes(_drawing(source)):
        if node.on_path:
            found += [Text(node.ends or line, line) for line in plain(node.label)]
    return found


def panels_tex(source: str) -> set[str]:
    """The panel letters opening a label line in the TikZ."""
    lines = [line for node in _nodes(_drawing(source)) for line in plain(node.label)]
    return {match.group(1) for line in lines if (match := _PANEL_LINE_RE.match(line))}


def panels_twin(twin: str) -> set[str]:
    """The standalone `(<letter>)` tokens in the twin."""
    return set(_PANEL_TOKEN_RE.findall(twin))


def agree(
    source: str, twin: str | None, twin_name: str
) -> tuple[list[Finding], list[tuple[str, str]]]:
    """`(findings, not_measured)` for the four twin rules. `twin` is the
    twin's text, `None` where there is no file; `twin_name` is what the
    `twin-missing` finding calls it."""
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
        lacking = [word for word in _WORD_RE.findall(said) if word not in present]
        if lacking:
            found.append(
                Finding(rule, text.target, f'missing "{" ".join(dict.fromkeys(lacking))}"')
            )
    return found


def _letters(letters: set[str]) -> str:
    return ", ".join(f"({letter})" for letter in sorted(letters)) or "none"


def _drawing(source: str) -> str:
    """The figure's own drawing, comments stripped: everything after the
    house block, whose `\\node` lines define macros rather than draw."""
    ends = list(_END_RE.finditer(source))
    return strip_comments(source[ends[-1].end() :] if ends else source)


@dataclass(frozen=True)
class _Node:
    name: str
    label: str
    on_path: bool
    ends: str  # `a->b` for a node on a path between two names, else ""


def _nodes(text: str) -> list[_Node]:
    paths = _path_spans(text)
    variables = "|".join(map(re.escape, _LOOP_VAR_RE.findall(text)))
    loop = re.compile(rf"(?:{variables})(?![a-zA-Z])" if variables else r"(?!)")
    found = []
    for match in _NODE_START_RE.finditer(text):
        declared = _declaration(text, match.end())
        # A macro parameter, or a loop variable whose every pass sets a
        # different label: the source text is none of them.
        if declared is None or "#" in declared[1] or loop.search(declared[1]):
            continue
        name, label = declared
        span = next((s for s in paths if s[0] < match.start() < s[1]), None)
        child = text[: match.start()].rstrip().endswith("{")
        on_path = span is not None and not child and not match.group(0).startswith("\\node")
        ends = _ends(text[span[0] : span[1]]) if on_path else ""
        found.append(_Node(name, label, on_path, ends))
    return found


def _declaration(text: str, start: int) -> tuple[str, str] | None:
    """`(name, label)` of the node declared from `start`, or `None` where
    its label never opens. The scan is `_focal._declaration`'s: options
    nest, and a parenthesised group after `at` is a position."""
    name, depth, after_at, i = "", 0, False, start
    while i < len(text):
        char = text[i]
        if depth:
            depth += {"[": 1, "]": -1}.get(char, 0)
        elif char == "[":
            depth = 1
        elif char == "(":
            end = text.find(")", i)
            if end < 0:
                return None
            name = name or ("" if after_at else text[i + 1 : end].strip())
            after_at, i = False, end
        elif _AT_RE.match(text, i):
            after_at = True
        elif char == "{":
            return name, _braced(text, i)[0]
        elif char == ";":
            return None
        i += 1
    return None


def _braced(text: str, start: int) -> tuple[str, int]:
    """The content of the `{...}` opening at `start`, and the offset past
    it. A group left open runs to the end of the text."""
    depth, i = 0, start
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        if not depth:
            return text[start + 1 : i], i + 1
        i += 1
    return text[start + 1 :], len(text)


def _path_spans(text: str) -> list[tuple[int, int]]:
    """Each `\\draw`/`\\path` statement's offsets, to its `;`. A `;` in a
    braced label does not end it."""
    spans = []
    for match in _PATH_RE.finditer(text):
        i = match.end()
        while i < len(text) and text[i] != ";":
            i = _braced(text, i)[1] if text[i] == "{" else i + 1
        spans.append((match.start(), i))
    return spans


def _ends(statement: str) -> str:
    """`first->last` named end of a path statement, or `""`. Labels and
    the names of nodes placed on it are not ends."""
    bare, i = [], 0
    while i < len(statement):
        if statement[i] == "{":
            i = _braced(statement, i)[1]
            bare.append("{}")
            continue
        bare.append(statement[i])
        i += 1
    text = re.sub(r"\bnode\b\s*(?:\[[^\]]*\]\s*)?\([^)]*\)", "node", "".join(bare))
    ends = _END_TOKEN_RE.findall(text)
    return f"{ends[0]}->{ends[-1]}" if len(ends) > 1 else ""


def _macro(text: str, macro: str, arity: int, name: int, label: int) -> list[tuple[str, str]]:
    """`(name, label)` from each full call of `\\<macro>` with `arity`
    braced arguments."""
    found = []
    for match in re.finditer(rf"\\{macro}(?![a-zA-Z])", text):
        args, _ = _arguments(text, match.end(), arity)
        if len(args) == arity and "#" not in args[label]:
            found.append((args[name].strip(), args[label]))
    return found


def _arguments(text: str, start: int, count: int) -> tuple[list[str], int]:
    """Up to `count` braced arguments from `start`, and the offset past
    the last; fewer where the next thing is not a brace."""
    args, i = [], start
    while len(args) < count:
        while i < len(text) and text[i].isspace():
            i += 1
        if text[i : i + 1] != "{":
            break
        arg, i = _braced(text, i)
        args.append(arg)
    return args, i
