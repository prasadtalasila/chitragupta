"""The two sides a redline compares, written out where `render()` reads them.

Each side is a version's text and both forms of each figure it names,
written to `<work>/old/` or `<work>/new/`. The old side is rewritten in
one way only (plans/1194-draft-diff.md, decision 11): a citation whose key is
not citable now becomes the plain words `(citation withdrawn)`, so the
gate, which runs unchanged on both sides, passes a baseline that cited a
paper since dropped from the corpus. The new side is the draft as it
stands; if it cites such a key, the gate refuses it as it would refuse
the draft itself.

Citations are found by the gate's own grammar -- `_pandoc_cites` for
Pandoc's `[@key]` and `@key`, `citation_gate`'s LaTeX patterns for
`\\cite*{...}` -- over the gate's own blanking of code and other
non-prose, so the rewrite removes exactly what the gate would read.
Blanking keeps every offset, so a span found in the blanked text is the
same span in the original.
"""

import shutil
from collections.abc import Callable
from pathlib import Path

from chitragupta import _pandoc_cites, citation_gate, config, ledger_citable
from chitragupta.dossier._versions import _FIGURE_FORMS
from chitragupta.draft_diff._views import VersionView

WITHDRAWN = "(citation withdrawn)"

# What may follow a closing `]` for the brackets to be a link, a
# reference link or a span rather than a citation group: a citation
# inside one is narrative, and replacing the whole bracket would break
# the link.
_NOT_A_GROUP_AFTER = ("(", "[", "{")


def key_status(con) -> Callable[[str], str]:
    """Each key's standing in the ledger now, as the change report words it."""
    citable = ledger_citable.citable_citekeys(con)
    in_ledger = ledger_citable.unparsed_citekeys(con)

    def status(key: str) -> str:
        if key in citable:
            return "still citable"
        if key in in_ledger:
            return "no longer parsed"
        return "no longer in the corpus"

    return status


def _bracket_pairs(prose: str, source: str) -> list[tuple[int, int]]:
    """(open, close) offsets of every matched `[...]`, by `_pandoc_cites`'s
    own bracket rule: escapes skipped, a blank line closing all."""
    pairs, stack = [], []
    for match in _pandoc_cites._BRACKET_RE.finditer(prose):
        token = match.group()
        if token == "[":
            stack.append(match.start())
        elif token == "]" and stack:
            pairs.append((stack.pop(), match.start()))
        elif token.startswith("\n") and not source[match.start() : match.end()].strip(" \t>\n"):
            stack.clear()
    return pairs


def _group_of(
    cite_start: int, pairs: list[tuple[int, int]], source: str
) -> "tuple[int, int] | None":
    """The bracketed citation group a citation sits in, or None if it is
    narrative: outside every bracket, or inside a link's text."""
    inside = [(o, c) for o, c in pairs if o < cite_start < c]
    if not inside:
        return None
    opened, closed = max(inside)
    if source[closed + 1 : closed + 2] in _NOT_A_GROUP_AFTER:
        return None
    return opened, closed


def _items(prose: str, opened: int, closed: int) -> list[tuple[int, int]]:
    """The `;`-separated items of the group `[opened ... closed]`, as spans."""
    items, start, depth = [], opened + 1, 0
    for at in range(opened + 1, closed):
        char = prose[at]
        depth += char == "["
        depth -= char == "]"
        if char == ";" and depth == 0:
            items.append((start, at))
            start = at + 1
    items.append((start, closed))
    return items


def _joined(pieces: list[str], separator: str) -> str:
    """`pieces` joined back, the first without the space its separator left."""
    return separator.join([pieces[0].lstrip(), *pieces[1:]])


def _latex_keys(prose: str) -> "list[tuple[int, str]]":
    """(command offset, key) for every key of every `\\cite*{...}`: what a
    group item cites in raw LaTeX, beside its Pandoc citations."""
    return [
        (match.start(), key.strip())
        for match in citation_gate._LATEX_CITE_RE.finditer(prose)
        for token in citation_gate._CITE_KEYS_RE.finditer(match.group(1))
        if token.group(1) is not None
        for key in token.group(1).split(",")
        if key.strip()
    ]


def _group_edits(
    prose: str,
    source: str,
    group: "tuple[int, int]",
    cites: list,
    raw: "list[tuple[int, str]]",
    gone: Callable[[str], bool],
) -> "list[tuple[int, int, str]]":
    """The edits that take the withdrawn keys out of one bracketed group."""
    opened, closed = group
    edits, kept, dropped = [], [], False
    for item_start, item_end in _items(prose, opened, closed):
        here = [cite for cite in cites if item_start <= cite[0] < item_end]
        # A raw `\\citep{}` in the item cites too: an item whose only
        # kept key is one is not citation-free, and must stay.
        keys = [key for _, _, key in here] + [
            key for start, key in raw if item_start <= start < item_end
        ]
        if keys and all(gone(key) for key in keys):
            dropped = True
            continue
        kept.append((source[item_start:item_end], bool(keys)))
        # One item citing a kept key and a withdrawn one has no
        # separator to drop at; the withdrawn one is replaced in place
        # (a withdrawn raw key, by `_latex_edits`).
        edits += [(start, end, WITHDRAWN) for start, end, key in here if gone(key)]
    if not any(cites_here for _, cites_here in kept):
        return [(opened, closed + 1, WITHDRAWN)]
    if dropped:
        edits.append((opened + 1, closed, _joined([text for text, _ in kept], ";")))
    return edits


def _pandoc_edits(
    prose: str, labels: "set[str]", source: str, latex: bool, gone: Callable[[str], bool]
) -> "list[tuple[int, int, str]]":
    cites = _pandoc_cites.citations(prose, labels, latex=latex, source=source)
    withdrawn = [cite for cite in cites if gone(cite[2])]
    if not withdrawn:
        return []
    pairs = _bracket_pairs(prose, source)
    raw = _latex_keys(prose)
    edits, groups = [], set()
    for start, end, _ in withdrawn:
        group = _group_of(start, pairs, source)
        if group is None:
            edits.append((start, end, WITHDRAWN))
        else:
            groups.add(group)
    for opened, closed in groups:
        edits += _group_edits(prose, source, (opened, closed), cites, raw, gone)
    return edits


def _latex_edits(
    prose: str, source: str, gone: Callable[[str], bool]
) -> "list[tuple[int, int, str]]":
    edits = []
    for match in citation_gate._LATEX_CITE_RE.finditer(prose):
        tokens = list(citation_gate._CITE_KEYS_RE.finditer(match.group(1)))
        keys = [
            key.strip()
            for token in tokens
            if token.group(1) is not None
            for key in token.group(1).split(",")
            if key.strip()
        ]
        if not any(gone(key) for key in keys):
            continue
        if all(gone(key) for key in keys):
            # The whole command, its optional arguments with it.
            edits.append((match.start(), match.end(), WITHDRAWN))
            continue
        offset = match.start(1)
        run, notes = [], []
        for token in tokens:
            text = source[offset + token.start() : offset + token.end()]
            if token.group(1) is None:
                notes.append(text)  # a multicite's note, belonging to the next group
                continue
            pieces = text[1:-1].split(",")
            kept = [piece for piece in pieces if not (piece.strip() and gone(piece.strip()))]
            if any(piece.strip() for piece in kept):
                run += [*notes, "{" + _joined(kept, ",") + "}"]
            notes = []
        edits.append((match.start(1), match.end(1), "".join(run)))
    return edits


def _withdraw_once(text: str, latex: bool, gone: Callable[[str], bool]) -> str:
    if latex:
        prose, labels = citation_gate._blank_code(text, latex=True, prose_only=True), set()
    else:
        prose, labels = citation_gate.markdown_prose(text)
    edits = _latex_edits(prose, text, gone) + _pandoc_edits(prose, labels, text, latex, gone)
    # From the end backwards, so each edit's offsets are still the
    # original's; an edit overlapping one already made waits for the next
    # pass, which reads the text afresh.
    floor = len(text) + 1
    for start, end, replacement in sorted(edits, reverse=True):
        if end <= floor:
            text = text[:start] + replacement + text[end:]
            floor = start
    return text


def withdraw(text: str, suffix: str, citable: Callable[[str], bool]) -> str:
    """`text` with every citation of a key `citable` rejects taken out.

    A bracketed group whose keys are all withdrawn, a narrative `@key`,
    and a `\\cite*{...}` (optional arguments included) whose keys are all
    withdrawn each become `WITHDRAWN`. A group or command that also cites
    a key still citable keeps it, losing only the withdrawn keys with
    their separators and, in Markdown, their own prefix and locator. A
    multicite's leading optional arguments stay with the command when its
    first group goes; they cannot be told apart from the command's own.

    Repeated until nothing changes, so a citation that one pass could not
    reach (its edit overlapped another) is reached by the next. Each pass
    removes text and inserts only `WITHDRAWN`, which holds no `@` or
    backslash, so the passes end. Text citing no withdrawn key is
    returned unchanged.
    """
    latex = citation_gate.is_latex(f"x{suffix}")

    def gone(key: str) -> bool:
        return not citable(key)

    while True:
        rewritten = _withdraw_once(text, latex, gone)
        if rewritten == text:
            return text
        text = rewritten


def _write_side(side_dir: Path, view: VersionView, text: str, draft_stem: str) -> Path:
    # Afresh each time: a figure an earlier run wrote would otherwise
    # survive into a side that no longer draws it.
    if side_dir.exists():
        shutil.rmtree(side_dir)
    side_dir.mkdir(parents=True)
    # Held to the side directory like the figures below: the stem is the
    # caller's, and a `..` in it would write elsewhere under content/.
    source = side_dir / f"{draft_stem}{view.suffix}"
    if not config.resolves_inside(source, side_dir):
        raise ValueError(f"{draft_stem!r} is not a file name: it would write {source.resolve()}")
    source.write_text(text, encoding="utf-8")
    for name, forms in (view.figures or {}).items():
        for form, body in zip(_FIGURE_FORMS, (forms.tikz, forms.ascii)):
            target = side_dir / f"{name}{form}"
            # The view read its figures with the renderer's sibling rule,
            # which refuses a name escaping the draft's directory; a view
            # built any other way is held to the same here.
            if body is None or not config.resolves_inside(target, side_dir):
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body, encoding="utf-8")
    return source


def prepare(
    old: VersionView,
    new: VersionView,
    work: Path,
    citable: Callable[[str], bool],
    stem: str,
) -> tuple[Path, Path]:
    """Writes `work/old/<stem><suffix>` and `work/new/<stem><suffix>`, each
    with its `figures/`, the old side with its withdrawn citations taken
    out; returns the two source paths.

    `work` must be under `content/`, which `render()` would refuse
    otherwise; the caller passes the diff's own directory under
    `content/review/`.
    """
    work = config.require_inside_content(Path(work), "diff's work directory")
    old_text = withdraw(old.text, old.suffix, citable)
    return (
        _write_side(work / "old", old, old_text, stem),
        _write_side(work / "new", new, new.text, stem),
    )
