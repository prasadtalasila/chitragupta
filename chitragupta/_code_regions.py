"""Where a draft's code regions are, found in time linear in its length.

Three DOTALL regexes used to find these -- `citation_gate`'s verbatim
blanking, and `style_typeset`'s fenced-block and verbatim-body scans --
and each paired an opener with its closer through a lazy `.*?`. An
opener with *no* closer ran that `.*?` to the end of the file before the
search moved on, so N unclosed openers cost O(N x L): a 20k-line draft
of bare `\\begin{verbatim}` lines, the kind of thing a paste of a
corrupted PDF's parsed text produces, took the citation gate hook past
the harness's 30 s kill, and a killed hook prints no block (#824).

What did not change is the pairing. Each function below reproduces its
regex's matches exactly, on malformed input too: an opener with no
closer is skipped rather than run to the end of the file, so a later
opener can still pair, and a fence whose own length has no closer
shortens to one that does, the way the regex backtracked. The cost is
the only difference -- closers are indexed once, and every opener then
finds its closer by lookup rather than by re-scanning the document.
`tests/test_code_regions.py` keeps the three regexes as oracles.

Standard library only, like `citation_gate` itself.
"""

import bisect
import re

# The environments whose body is not prose -- the one list both callers
# use, so what the gate blanks and what typesetting measures agree.
_ENVS = r"(verbatim|lstlisting|minted)"
_BEGIN_RE = re.compile(rf"\\begin\{{{_ENVS}\*?\}}")
# The gate's closer may sit anywhere; typesetting's must start a line.
_END_RE = re.compile(rf"\\end\{{{_ENVS}\*?\}}")
_LINE_END_RE = re.compile(rf"^[ \t]*\\end\{{{_ENVS}\*?\}}", re.MULTILINE)


def _closers(pattern: "re.Pattern", text: str) -> dict:
    """`{env: (starts, ends)}` for every closer `pattern` finds, in order."""
    found: dict = {}
    for match in pattern.finditer(text):
        starts, ends = found.setdefault(match.group(1), ([], []))
        starts.append(match.start())
        ends.append(match.end())
    return found


def _next_closer(closers: dict, env: str, after: int) -> "tuple[int, int] | None":
    """The first of `env`'s closers starting at or after `after`."""
    starts, ends = closers.get(env, ((), ()))
    index = bisect.bisect_left(starts, after)
    return (starts[index], ends[index]) if index < len(starts) else None


def _pairs(text: str, closers: dict) -> list:
    """Each `(begin match, (closer start, closer end))` a lazy
    `\\begin{env}...closer` regex would match, scanning left to right.

    A begin inside a pair already found is consumed by it, and one with
    no closer after it is skipped -- the two things a regex search does
    that decide which later begins get a turn."""
    pairs = []
    resume = 0
    for begin in _BEGIN_RE.finditer(text):
        if begin.start() < resume:
            continue
        closer = _next_closer(closers, begin.group(1), begin.end())
        if closer is not None:
            pairs.append((begin, closer))
            resume = closer[1]
    return pairs


def blank_latex_verbatim(text: str) -> str:
    """`text` with each verbatim-style environment blanked to spaces,
    `\\begin` through `\\end`, newlines kept so no offset moves.

    Mid-line on both ends, as the gate's regex was: a citation sharing a
    line with `\\end{verbatim}` stays visible to the gate."""
    out = []
    last = 0
    for begin, (_, end) in _pairs(text, _closers(_END_RE, text)):
        out.append(text[last : begin.start()])
        out.append(re.sub(r"[^\n]", " ", text[begin.start() : end]))
        last = end
    out.append(text[last:])
    return "".join(out)


def latex_verbatim_bodies(text: str) -> "list[tuple[int, str]]":
    """`(first line number, body)` of each verbatim-style environment.

    The body runs from the line after `\\begin{...}` to the start of the
    first later line that opens with `\\end{...}` of the same name; the
    delimiter lines are not part of it."""
    line_starts = [0] + [match.end() for match in re.finditer("\n", text)]
    bodies = []
    for begin, (close_start, _) in _pairs(text, _closers(_LINE_END_RE, text)):
        line = bisect.bisect_right(line_starts, begin.start())
        bodies.append((line + 1, text[line_starts[line] : close_start]))
    return bodies


def _fence(line: str) -> "tuple[str, int] | None":
    """`(character, run length)` of the fence a line opens with, after
    any spaces and tabs, or None when it opens with no fence at all."""
    body = line.lstrip(" \t")
    char = body[:1]
    if char not in ("`", "~"):
        return None
    run = len(body) - len(body.lstrip(char))
    return (char, run) if run >= 3 else None


def _closes(mark: "tuple[str, int] | None", char: str, length: int) -> bool:
    """Would a line marked `mark` close a fence of `length` `char`s?"""
    return mark is not None and mark[0] == char and mark[1] >= length


def _longest_after(marks: list) -> dict:
    """`{char: runs}`, where `runs[i]` is the longest fence of that
    character on any line from `i` on -- what a closer there can match."""
    longest = {"`": [0] * (len(marks) + 1), "~": [0] * (len(marks) + 1)}
    for index in range(len(marks) - 1, -1, -1):
        for runs in longest.values():
            runs[index] = runs[index + 1]
        mark = marks[index]
        if mark is not None and mark[1] > longest[mark[0]][index]:
            longest[mark[0]][index] = mark[1]
    return longest


def fenced_bodies(text: str) -> "list[tuple[int, str]]":
    """`(first line number, body)` of each fenced block, delimiters excluded.

    A fence may be indented by any spaces and tabs, and is closed by the
    first later line opening with at least as many of the same character.
    An opener's length is the longest that some later line can close, as
    when the regex backtracked: ````` closed only by ``` pairs as ```.
    The last line cannot open a fence, having no newline after it."""
    lines = text.split("\n")
    marks = [_fence(line) for line in lines]
    longest = _longest_after(marks)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line) + 1)
    bodies = []
    index = 0
    while index < len(lines) - 1:
        mark = marks[index]
        length = min(mark[1], longest[mark[0]][index + 1]) if mark else 0
        if length < 3:
            index += 1
            continue
        close = index + 1
        while not _closes(marks[close], mark[0], length):
            close += 1
        bodies.append((index + 2, text[offsets[index + 1] : offsets[close]]))
        index = close + 1
    return bodies
