"""The wording rules, `w1` to `w4`, read from a figure's source (#1055).

From the source because they are about the words as written, and
because TikZ never keeps a label's tokens: by the time the probe sees a
node, its text is a typeset box.

- **`w1-case`** (advisory): a `\\cglab` name is in sentence case. It
  reports a name that starts lower-case, and one in Title Case, where
  every later word of four letters or more is capitalised, so a proper
  noun in a mixed name (`Extended Kalman filter`) passes. An acronym
  (two capitals or more: `RAG`, `PDFs`) is never read as a capitalised
  word, and a name may start with a word that is lower-case by
  convention (`_LOWER_BY_CONVENTION`).
- **`w2-tag`** (advisory): an edge tag is lower-case and at most three
  words. A tag is a `node` inside a `\\draw` or `\\path` statement that
  joins two points; a note placed beside a line by its own `\\node` is
  not one.
- **`w3-gloss`** (advisory): a `\\cglab` gloss is at most six words. It
  supersedes the eight #1016's `gloss-too-long` proposed.
- **`w4-pictograph`** (objective): no emoji or pictographic character
  in a label. The render prints one through a fallback font that
  matches nothing else in the figure (Unifont's bitmap glyphs, for an
  emoji), and a thesis that `\\input`s the figure without that font
  chain drops it with only a log warning. The house figure draws a
  shape as a `pic`, never an icon font. Arrows, `©`, `™` and math
  symbols are typography and pass; an icon command (`\\ding`, `\\fa...`)
  prints where its package is loaded, and is not read.

Only `\\cglab` is read for names and glosses (*user*): there the two are
certain, while a label broken by hand with `\\\\` may be one phrase
wrapped. A `$...$` formula counts as one word, and `\\texttt{}` text is
left as written.
"""

import re
from dataclasses import dataclass

from chitragupta._tex_comments import strip_comments
from chitragupta.figure._focal import declaration
from chitragupta.figure._rules import Finding
from chitragupta.review.figure_layout._source import _PATH_STATEMENT_RE

TAG_WORDS = 3
GLOSS_WORDS = 6
_TITLE_LETTERS = 4

# First words that are lower-case by convention: program names.
_LOWER_BY_CONVENTION = frozenset(
    {"tikz", "pgf", "pdflatex", "lualatex", "xelatex", "latexmk", "git", "pip", "npm", "make"}
)

# The emoji blocks, the miscellaneous symbols and dingbats (where `✓`
# and `★` sit), the miscellaneous symbols and arrows block's pictographs,
# and the variation selector that asks for emoji presentation.
_PICTOGRAPHS = ((0x1F000, 0x1FAFF), (0x2600, 0x27BF), (0x2B00, 0x2BFF), (0xFE0F, 0xFE0F))

_CGLAB_RE = re.compile(r"\\cglab\s*(?=\{)")
# `node` as TikZ's keyword: the `\node` command or the path operation,
# not `node distance=` or any other key that starts with the word.
_NODE_RE = re.compile(r"(?:\\|(?<![\w\\]))node\b(?![\w\s]*=)")
# A path that joins two points: `--`, `-|`, `|-`, `to`, `edge`, `..`.
_JOINS_RE = re.compile(r"--|-\||\|-|\bto\b|\bedge\b|\.\.")
# A command's arguments that are not text a reader sees: a colour, a
# length, a key. Dropped before a label is read (`\textcolor{cgAccent}`
# is not the word `cgAccent`).
_NOT_TEXT_RE = re.compile(
    r"\\fontsize\s*\{[^{}]*\}\s*\{[^{}]*\}"
    r"|\\(?:textcolor|color|colorbox|hspace|vspace|cite[pt]?|ref|label)\*?"
    r"\s*(?:\[[^\]]*\])?\s*\{[^{}]*\}"
)
# A brace group or a parenthesised point, blanked before asking whether
# a path joins two points, so `to` in a label or `|-` in a coordinate
# does not count.
_GROUP_RE = re.compile(r"\{[^{}]*\}|\([^()]*\)")
# One piece of a label: a formula, `\texttt{}`, a line break with its
# optional skip, any other control sequence, a brace or space, or text.
_TOKEN_RE = re.compile(
    r"(?P<math>\$[^$]*\$)|\\texttt\s*\{(?P<tt>[^{}]*)\}|\\\\(?:\[[^\]]*\])?"
    r"|\\[a-zA-Z@]+\*?|\\.|[{}~\s]+|(?P<text>[^\\{}~\s$]+)"
)


@dataclass(frozen=True)
class _Word:
    text: str
    verbatim: bool = False  # a formula, or `\texttt{}`: never case-read

    @property
    def letters(self) -> str:
        return "" if self.verbatim else "".join(c for c in self.text if c.isalpha())

    @property
    def capitalised(self) -> bool:
        """Starts with a capital and is neither an acronym nor a single
        letter, which is a symbol or a unit (`12 V`, `A+`)."""
        letters = self.letters
        return len(letters) > 1 and letters[0].isupper() and sum(map(str.isupper, letters)) < 2


def wording_rules(source: str) -> tuple[list[Finding], list[Finding]]:
    """`(objective findings, advisory reports)`: w4, then w1 to w3."""
    text = strip_comments(source)
    advisory: list[Finding] = []
    for name, gloss in _cglabs(text):
        advisory += _case(name) + _gloss(name, gloss)
    advisory += [finding for tag in _tags(text) for finding in _tag(tag)]
    return _pictographs(text), sorted(advisory, key=lambda f: f.rule)


def words(label: str) -> list[_Word]:
    """What a reader sees in `label`, one entry per word.

    Not `review/figure_layout/_source._label_words`, which only counts:
    the case rules need each word, and which ones are a formula or
    `\\texttt{}` that is never case-read. It also counts `$x + 1$` as
    three words and a line break's `[-1pt]` as one, which a fifteen-word
    ceiling absorbs and a six-word one does not."""
    found = []
    for match in _TOKEN_RE.finditer(_NOT_TEXT_RE.sub(" ", label)):
        if match.group("math"):
            found.append(_Word(match.group("math"), verbatim=True))
        elif match.group("tt") is not None:
            found += [_Word(part, verbatim=True) for part in match.group("tt").split()]
        elif match.group("text") and any(c.isalnum() for c in match.group("text")):
            found.append(_Word(match.group("text")))
    return found


def _shown(label: str) -> str:
    return '"' + " ".join(word.text for word in words(label)) + '"'


def _case(name: str) -> list[Finding]:
    """w1: lower-case at the start, or Title Case after it."""
    found = words(name)
    if not found:
        return []
    first = found[0]
    lower = len(first.letters) > 1 and first.letters[0].islower()
    if lower and first.text.lower() not in _LOWER_BY_CONVENTION:
        return [Finding("w1-case", _shown(name), "starts lower-case; sentence case capitalises it")]
    later = [
        word for word in found[1:] if len(word.letters) >= _TITLE_LETTERS and not _acronym(word)
    ]
    if later and all(word.capitalised for word in later):
        return [
            Finding(
                "w1-case", _shown(name), "Title Case; sentence case capitalises only the first word"
            )
        ]
    return []


def _acronym(word: _Word) -> bool:
    return sum(map(str.isupper, word.letters)) >= 2


def _gloss(name: str, gloss: str) -> list[Finding]:
    """w3: a gloss of more than `GLOSS_WORDS` words."""
    count = len(words(gloss))
    if count <= GLOSS_WORDS:
        return []
    return [
        Finding("w3-gloss", _shown(name), f"{_shown(gloss)}: {count} words, over {GLOSS_WORDS}")
    ]


def _tag(tag: str) -> list[Finding]:
    """w2: a tag over `TAG_WORDS` words, or with a capitalised word."""
    found = words(tag)
    why = []
    if len(found) > TAG_WORDS:
        why.append(f"{len(found)} words, over {TAG_WORDS}")
    if any(word.capitalised for word in found):
        why.append("capitalised; a tag is lower-case")
    return [Finding("w2-tag", f"tag {_shown(tag)}", "; ".join(why))] if why else []


def _pictographs(text: str) -> list[Finding]:
    """w4, per node whose label holds one, then the rest of the figure."""
    found, seen = [], set()
    for name, label, span in _labels(text):
        hits = _hits(label)
        if hits:
            seen.update(range(*span))
            found.append(Finding("w4-pictograph", name or _shown(label), f"{hits} in the label"))
    outside = "".join(char for i, char in enumerate(text) if i not in seen)
    hits = _hits(outside)
    if hits:
        found.append(Finding("w4-pictograph", "figure", f"{hits} outside any node's label"))
    return found


def _hits(text: str) -> str:
    """Each distinct pictograph in `text`, shown with its code point."""
    chars = dict.fromkeys(
        char for char in text if any(low <= ord(char) <= high for low, high in _PICTOGRAPHS)
    )
    return ", ".join(f'"{char}" (U+{ord(char):04X})' for char in chars)


def _cglabs(text: str) -> list[tuple[str, str]]:
    """`(name, gloss)` of every `\\cglab` call, none from a definition
    (a body holding `#1`)."""
    found = []
    for match in _CGLAB_RE.finditer(text):
        name, end = _group(text, match.end())
        gloss, _ = _group(text, end)
        if "#" not in name + gloss:
            found.append((name, gloss))
    return found


def _tags(text: str) -> list[str]:
    """The label of every node placed on a path that joins two points."""
    tags = []
    for statement in _PATH_STATEMENT_RE.finditer(text):
        body = statement.group("body")
        if _JOINS_RE.search(_blanked(body)):
            tags += [label for _, label, _ in _labels(body) if not label.startswith("\\cglab")]
    return tags


def _blanked(body: str) -> str:
    """`body` with every brace group and parenthesised point emptied,
    innermost first, so only the path's own operations are left."""
    while True:
        emptied = _GROUP_RE.sub(" ", body)
        if emptied == body:
            return body
        body = emptied


def _labels(text: str) -> list[tuple[str, str, tuple[int, int]]]:
    """`(name, label, (start, end))` of every node in `text`. The word
    `node` inside a label already read is text, not a node."""
    found, close = [], 0
    for match in _NODE_RE.finditer(text):
        if match.start() < close:
            continue
        _, name, end = declaration(text, match.end())
        if end < len(text) and text[end] == "{":
            label, close = _group(text, end)
            found.append((name, label.strip(), (end, close)))
    return found


def _group(text: str, start: int) -> tuple[str, int]:
    """The brace group opening at `start` (after any space), and the
    index just past its close; `("", start)` where none opens there."""
    i = start
    while i < len(text) and text[i].isspace():
        i += 1
    if i >= len(text) or text[i] != "{":
        return "", start
    depth = 0
    for j in range(i, len(text)):
        depth += {"{": 1, "}": -1}.get(text[j], 0)
        if depth == 0:
            return text[i + 1 : j], j + 1
    return text[i + 1 :], len(text)
