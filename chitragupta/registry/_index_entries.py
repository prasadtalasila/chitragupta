"""How the index prints a term (#1168): casing, article, symbols, sort key,
`upmendex` quoting, sub-entries and cross-references.

Everything here is presentation, decided once the whole book is typeset,
from the term table (`registry/_index_terms.py`) and the casing counts
each chapter's sidecar records. The filter never sees any of it: it puts
only an opaque id in `\\index{}`.

- **Casing** is the book's own: a word is lowercased or capitalised when
  most of its mid-sentence mentions are, because a glossary line always
  starts with a capital ("Decision") that the prose does not use. A tie,
  or no mid-sentence mention, lowercases a plainly capitalised first
  word and keeps the rest; the report names each such guess, and
  `[print]` overrides all of it.
- **A leading article** is inverted, Chicago-style: "four criteria, the".
- **Sort keys** are plain lowercase text: maths delimiters dropped, Greek
  spelled out, the article left out, so "ε-greedy" files under E.
- **Quoting**: `upmendex` reads `! @ | "` as syntax, so each is quoted
  with `"` in both the sort key and the printed form.
"""

import re
import unicodedata

from chitragupta.registry._index_terms import term_id
from chitragupta.registry._terms import term_key
from chitragupta.render_output._math import _GREEK_NAMES

ARTICLES = ("the", "a", "an")

_LATEX_NAME = re.compile(r"\\(?:var)?([a-z]+)")


# A word as the filter splits prose: spaces, hyphens and dashes separate.
_TOKEN = re.compile(r"[^\s\-\u2013\u2014]+")


def _votes(
    glossary: str, midsentence: "dict[str, int]"
) -> "tuple[list[re.Match], list[list[int]]]":
    """`glossary`'s words, and for each `[lowercase, capitalised]`
    mid-sentence counts. A mention of a different length (another
    spelling) casts no vote."""
    tokens = list(_TOKEN.finditer(glossary))
    votes = [[0, 0] for _ in tokens]
    for surface, count in midsentence.items():
        parts = surface.split()
        if len(parts) == len(tokens):
            for index, part in enumerate(parts):
                votes[index][part[:1].isupper()] += count
    return tokens, votes


def _plain(word: str) -> bool:
    """A capital and then lowercase: "Stage", not "MODBUS" or "I2C"."""
    return len(word) > 1 and word[0].isupper() and word[1:] == word[1:].lower()


def cased(glossary: str, midsentence: "dict[str, int]") -> str:
    """`glossary`, each word cased as most of its mid-sentence mentions
    are. With no evidence, or a tie, a plainly capitalised first word is
    the glossary line's sentence capital, and is lowercased."""
    tokens, votes = _votes(glossary, midsentence)
    chars = list(glossary)
    for index, (token, (lower, upper)) in enumerate(zip(tokens, votes)):
        first = token.start()
        if lower > upper:
            chars[first] = chars[first].lower()
        elif upper > lower:
            chars[first] = chars[first].upper()
        elif index == 0 and _plain(token.group()):
            chars[first] = chars[first].lower()
    return "".join(chars)


def guessed(glossary: str, midsentence: "dict[str, int]") -> bool:
    """Whether `cased` lowercased the first word on no evidence: right
    for "Ecological twin", wrong for a proper noun such as "Kalman
    filter", so the report names each one."""
    tokens, votes = _votes(glossary, midsentence)
    return bool(tokens) and votes[0][0] == votes[0][1] and _plain(tokens[0].group())


def inverted(text: str) -> str:
    """ "The four criteria" as "four criteria, the"."""
    words = text.split()
    if len(words) > 1 and words[0].lower() in ARTICLES:
        return f"{' '.join(words[1:])}, {words[0].lower()}"
    return text


def printed(term: dict, midsentence: "dict[str, int]") -> str:
    """A term's printed form, as Markdown: `[print]`, or its glossary form
    in the book's casing with any article inverted; then its symbols."""
    text = term["print"] or inverted(cased(term["glossary"], midsentence))
    if term["symbols"]:
        return f"{text} ({', '.join(term['symbols'])})"
    return text


def _greek(char: str) -> str:
    name = unicodedata.name(char, "")
    if name.startswith("GREEK") and " LETTER " in name:
        return name.split(" LETTER ")[1].split()[0].lower()
    return char


def sort_key(text: str) -> str:
    """Plain lowercase text to sort `text` by."""
    text = _LATEX_NAME.sub(
        lambda match: match.group(1) if match.group(1) in _GREEK_NAMES else match.group(0), text
    )
    text = re.sub(r"[`$\\{}]", "", "".join(_greek(char) for char in text))
    words = text.lower().split()
    if len(words) > 1 and words[0] in ARTICLES:
        words = words[1:]
    return " ".join(words)


def quote(text: str) -> str:
    """`text` with `upmendex`'s syntax characters quoted."""
    return re.sub(r'([!@|"])', r'"\1', text)


def child(text: str, parent: str) -> str:
    """A sub-entry's text under `parent`: the parent's own words dropped
    from its start or end ("Stage 0" under "stage" is "0"), unless that
    would leave nothing."""
    words, own = text.split(), parent.lower().split()
    if len(words) > len(own):
        if [word.lower() for word in words[: len(own)]] == own:
            return " ".join(words[len(own) :])
        if [word.lower() for word in words[-len(own) :]] == own:
            return " ".join(words[: -len(own)])
    return text


def _sort_of(term: dict) -> str:
    return sort_key(term["print"] or term["glossary"])


def keys(
    data: dict, midsentence: "dict[str, dict]", convert
) -> "tuple[dict[str, list[str]], dict[str, str]]":
    """Term id -> the `sort@printed` keys it is indexed under, and term id
    -> its printed form as LaTeX. The keys: its own,
    unless a parent is `[parent_only]`, then one per parent, each
    repeating the parent's whole key (otherwise `upmendex` prints the
    parent twice). `convert` is `markdown_to_latex`, called once."""
    terms = data["terms"]
    own = {tid: printed(term, midsentence.get(tid, {})) for tid, term in terms.items()}
    under = {
        (tid, parent): child(own[tid], parent)
        for tid, term in terms.items()
        for parent in term["parents"]
    }
    # A parent that is itself a term prints as that term does, or upmendex
    # would see two parents: the term's own line and the raw name.
    heads = {}
    for parent in sorted({parent for _, parent in under}):
        pid = term_id(term_key(parent))
        heads[parent] = (
            (own[pid], _sort_of(terms[pid])) if pid in terms else (parent, sort_key(parent))
        )
    texts = list(
        dict.fromkeys([*own.values(), *(text for text, _ in heads.values()), *under.values()])
    )
    plain = dict(zip(texts, convert(texts)))
    latex = {text: quote(out) for text, out in plain.items()}
    found = {}
    for tid, term in terms.items():
        lines = (
            []
            if set(term["parents"]) & set(data["parent_only"])
            else [f"{quote(_sort_of(term))}@{latex[own[tid]]}"]
        )
        lines += [
            f"{quote(heads[parent][1])}@{latex[heads[parent][0]]}!"
            f"{quote(sort_key(under[tid, parent]))}@{latex[under[tid, parent]]}"
            for parent in term["parents"]
        ]
        found[tid] = lines
    return found, {tid: plain[own[tid]] for tid in terms}


def cross_references(
    data: dict, printed_latex: "dict[str, str]", pages: "dict[str, str]", convert
) -> "tuple[list[str], list[str]]":
    """`.idx` lines for the see and see-also entries, and the name of every
    target dropped because it has no page in the book. `printed_latex` is
    each term's printed form as LaTeX, `pages` each indexed term's first
    page."""
    lines, dangling = [], []
    sources = sorted(data["see"])
    latex = dict(zip(sources, convert(sources)))
    for source in sources:
        target = data["see"][source]
        if target not in pages:
            dangling.append(source)
            continue
        lines.append(
            f"\\indexentry{{{quote(sort_key(source))}@{quote(latex[source])}"
            f"|see{{{quote(printed_latex[target])}}}}}{{{pages[target]}}}"
        )
    for tid, targets in sorted(data["see_also"].items()):
        live = [target for target in targets if target in pages]
        dangling += [printed_latex[target] for target in targets if target not in pages]
        if tid in pages and live:
            names = ", ".join(quote(printed_latex[target]) for target in live)
            term = data["terms"][tid]
            lines.append(
                f"\\indexentry{{{quote(_sort_of(term))}@{quote(printed_latex[tid])}"
                f"|seealso{{{names}}}}}{{{pages[tid]}}}"
            )
    return lines, dangling
