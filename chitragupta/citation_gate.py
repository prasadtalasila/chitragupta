"""Citation verification gate.

Every genre skill MUST run this on its own output before presenting a
draft. It is a hard gate: a citekey that does not resolve to something
`sync` pulled from the bib file is treated as fabricated and blocks the
draft.

Usage:
    python -m chitragupta.draft gate <file> [<file> ...]

Recognizes any LaTeX command whose name contains "cite" and Pandoc
citation syntax ([@key], bare @key, -@key, @{key}). Everything pandoc
does not read as prose, and in LaTeX verbatim environments, `%` comments
and \\verb, is blanked before scanning (see _blank_code).
"""

# Known over-reporting (#834): a brace group adjacent to a citation reads
# as a multicite group, and `\newcommand{\mc}[1]{\citep{#1}}` offers `#1`.
# Both fail a sound draft rather than pass a fabricated key.

import re
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path

from chitragupta import _code_regions, _markdown_inert, _pandoc_cites, config, gate_liveness, ledger
from chitragupta.citation_gate_report import report
from chitragupta.ledger_citable import citable_citekeys, unparsed_citekeys

# Matched by substring ("contains cite"), not an enumerated list: ordered
# alternation silently missed \citealp, \footcite, \Textcite..., and a
# missed command reads a fabricated key as "0 citations". Err toward
# matching too much.
# _WS allows at most one newline between a command and its arguments, as
# TeX does: a blank line is \par, and unbounded \s* could bridge a
# blanked-out code block into a fake citation. Its shape admits exactly
# one parse, so a run of `[...]` groups cannot backtrack exponentially and
# time out the hook (#635).
_WS = r"[ \t]*(?:\n[ \t]*)?"
# Group 1 is the whole run of {key} groups: biblatex multicites take one
# group per citation. Trailing groups count only when directly adjacent,
# so `\citep{a} {\bfseries x}` does not invent a key.
#
# No two _WS atoms are ever adjacent, which keeps matching linear (#635)
# and the single-newline cap real.
_LATEX_CITE_RE = re.compile(
    r"\\[A-Za-z]*[Cc]ite[A-Za-z]*"
    rf"(?:{_WS}\*)?(?:{_WS}\[[^\]]*\])*{_WS}"
    r"(\{[^}]+\}(?:(?:\[[^\]]*\]){0,2}\{[^}]+\})*)"
)
# Bracket alternative first, so a note like [\emph{cf}] is not read as a
# key group. Only matches with group(1) set are keys.
_CITE_KEYS_RE = re.compile(r"\[[^\]]*\]|\{([^}]+)\}")
# The Pandoc grammar is `_pandoc_cites`'s, shared with every module that
# finds a Pandoc citation (#1021).

# Code in teaching genres holds @-tokens (@dataclass) that look like
# citations, and a FAIL blocks the PostToolUse hook, pushing the agent to
# delete valid code. So code is blanked (not deleted: offsets give line
# numbers) before extraction; verbatim environments are paired by a
# linear scan in _code_regions (#824).
# The regex below scans LaTeX's other inert regions left to right, so
# whichever opens first wins, as in TeX (#834):
# - `\verb` first, or the escape pair eats the `\v`; its delimiter is any
#   non-letter, non-space character (`(\S)` would misread
#   `\verbatiminput` and `\verb*`).
# - `\url`/`\href` arguments are returned unchanged: `%` is literal there,
#   and blanking to end of line would *hide* a following citation.
# - The escape pair tracks backslash parity, so `\%` is literal but `\\%`
#   starts a comment; a one-character lookbehind lets a commented-out
#   citekey through.
_LATEX_INERT_RE = re.compile(
    r"\\verb\*?([^A-Za-z\s])[^\n]*?\1"  # \verb<d>...<d>, \verb*<d>...<d>
    r"|(?P<esc>\\(?:url|href)\{[^}\n]*\}"  # a URL argument: `%` is ordinary there
    r"|\\[\s\S])"  # an escaped character: not a comment start
    r"|%[^\n]*"  # a comment, to the end of the line
)


def _blank_code(text: str, *, latex: bool = False, prose_only: bool = False) -> str:
    """Blank code to spaces, preserving every offset.

    `prose_only=True` also blanks what pandoc does not read as prose (HTML
    comments, link targets, reference definitions), which citation
    extraction needs; other callers read image paths or markers there.

    `latex=True` applies LaTeX's inert regions and none of Markdown's: a
    backtick is an open quote in LaTeX, and the inline-code rule blanked
    citations between two quoted phrases, passing a fabricated key.
    """

    def _blank_match(m: re.Match) -> str:
        return re.sub(r"[^\n]", " ", m.group(0))

    def _blank_unless_escaped(m: re.Match) -> str:
        return m.group(0) if m.group("esc") else _blank_match(m)

    text = _code_regions.blank_latex_verbatim(text)
    if latex:
        return _LATEX_INERT_RE.sub(_blank_unless_escaped, text)
    return _markdown_inert.blank(text, code_only=not prose_only)


def markdown_prose(text: str) -> tuple[str, set[str]]:
    """`_blank_code(text, prose_only=True)` for Markdown, plus the
    example-list labels the document defines.

    Labels are read after LaTeX verbatim blanking, so a `(@label)` inside
    one defines nothing and cannot hide `@label` citations from the gate.
    """
    return _markdown_inert.prose(_code_regions.blank_latex_verbatim(text))


@dataclass
class GateResult:
    path: Path
    unknown: list[tuple[int, str]] = field(default_factory=list)  # (line_no, citekey)
    total_citations: int = 0
    # unresolved key -> status, for keys with a ledger row but no parsed PDF (#1118)
    unparsed: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.unknown


def is_latex(path: "str | Path") -> bool:
    """Whether `path` is read with LaTeX's rules rather than Markdown's.

    The one place the suffix rule lives (#957);
    `tests/test_citation_gate_pandoc.py` fails a caller that derives it.
    """
    return Path(path).suffix.lower() == ".tex"


def extract_citekeys_for(path: "str | Path", text: str) -> list[tuple[int, str]]:
    """`extract_citekeys(text)` with the LaTeX flag taken from `path`."""
    return extract_citekeys(text, latex=is_latex(path))


def extract_citekeys_from_line(line: str, *, latex: bool = False) -> list[str]:
    """The keys extract_citekeys() finds in a fragment, without line numbers.

    Each line's leading whitespace is dropped first: a fragment has lost
    its list item, so an indented continuation would read as code.

    A caller that splits a document into lines loses multi-line fences
    (false positives) and `\\citep\n{key}` across lines (false negatives).
    Acceptable for informational callers; prefer extract_citekeys() when
    the whole document is available.
    """
    flush = "\n".join(part.lstrip() for part in line.split("\n"))
    return [key for _, key in extract_citekeys(flush, latex=latex)]


def extract_citekeys(text: str, *, latex: bool = False) -> list[tuple[int, str]]:
    """Every citekey in `text` as (1-based line number, key).

    Scans the whole document, not line by line, so a `\\citep{...}`
    wrapped across lines is still caught. Pass `latex=True` for `.tex`
    input (see `_blank_code`).
    """
    source = text
    if latex:
        text, labels = _blank_code(text, latex=True, prose_only=True), set()
    else:
        text, labels = markdown_prose(text)

    # Both regexes' matches, sorted into document order for the report.
    matches: list[tuple[int, str]] = []
    for match in _LATEX_CITE_RE.finditer(text):
        # The first group reports the command's own line (pinned for
        # \citep\n{key}); later groups take their own offset.
        for group in _CITE_KEYS_RE.finditer(match.group(1)):
            if group.group(1) is None:  # a between-group bracket note, not keys
                continue
            start = match.start() if group.start() == 0 else match.start(1) + group.start()
            matches.extend((start, k.strip()) for k in group.group(1).split(",") if k.strip())
    matches.extend(
        (start, key)
        for start, _, key in _pandoc_cites.citations(text, labels, latex=latex, source=source)
    )
    matches.sort(key=lambda m: m[0])

    # One forward sweep, not a count from 0 per match (O(N*M)).
    keys: list[tuple[int, str]] = []
    line_no = 1
    pos = 0
    for start, key in matches:
        line_no += text.count("\n", pos, start)
        pos = start
        keys.append((line_no, key))
    return keys


def check_text(
    path: Path, text: str, citable: set[str], unparsed: "dict[str, str] | None" = None
) -> GateResult:
    """Gate `text`, attributed to `path` for reporting.

    `citable` holds keys whose PDF parsed; `unparsed` only explains why a
    key with a ledger row failed. Split from `check_document` so a caller
    can gate and act on the same bytes: `unit accept` re-read the file and
    recorded prose the gate never saw (#506). `path` is not read here.
    """
    result = GateResult(path=path)
    for line_no, key in extract_citekeys_for(path, text):
        result.total_citations += 1
        if key not in citable:
            result.unknown.append((line_no, key))
            if unparsed and key in unparsed:
                result.unparsed[key] = unparsed[key]
    return result


def check_document(path: Path, citable: set[str], unparsed=None) -> GateResult:
    return check_text(path, path.read_text(encoding="utf-8"), citable, unparsed)


def run(paths: list[str]) -> int:
    # Here, and only here, can it be said whether the automatic gate runs
    # at all (gate_liveness.py).
    gate_liveness.observe(paths)

    # No ledger fails closed like an empty one; a citation-free draft
    # still passes, which the session-start probe relies on. Read-only
    # (#843). An unreadable or stale ledger exits 3 before any draft, so
    # "I could not check" never shares the verdict's code 1 (#1066).
    try:
        with ledger.reading() as con:
            known, unparsed = citable_citekeys(con), unparsed_citekeys(con)
        problem = "ledger is empty -- run `python -m chitragupta.corpus sync` first."
        if unparsed:
            problem = "the ledger holds no parsed source -- no PDF has been parsed yet."
    except (ledger.StaleLedger, ledger.UnreadableLedger, sqlite3.Error) as exc:
        return _could_not_read(exc)
    except ledger.NoLedger as exc:
        known, unparsed = set(), {}
        problem = " ".join(str(exc).split("\n"))

    if not known:
        print(
            f"WARNING: {problem} Every citekey will be reported as unknown.",
            file=sys.stderr,
        )

    all_ok = True
    for p in paths:
        try:
            checked = config.require_inside_content(Path(p))
        except config.OutsideContentDir as exc:
            # Per document, exit 1 not 2: one bad path must not hide the
            # verdict on the rest.
            all_ok = False
            print(f"FAIL  {p}: {exc}")
            continue
        result = check_document(checked, known, unparsed)
        all_ok = all_ok and result.ok
        report(p, result)

    return 0 if all_ok else 1


def _could_not_read(exc: Exception) -> int:
    # stderr only, so nothing on stdout reads as a verdict.
    if isinstance(exc, sqlite3.Error):
        exc = ledger.UnreadableLedger(config.LEDGER_PATH, exc)
    print(
        "ERROR: the citation gate could not read the ledger, so no citekey was checked.\n"
        f"This is not a verdict on any draft (exit {ledger.EXIT_UNREADABLE}).\n{exc}",
        file=sys.stderr,
    )
    return ledger.EXIT_UNREADABLE


# Laid out like argparse's --help (#1230), by hand: no non-stdlib imports.
USAGE = """Usage: python -m chitragupta.draft gate [OPTIONS] FILE...

  Fail if a draft cites a citekey the ledger doesn't hold as a parsed
  source: in the .bib, and its PDF parsed. Exit 0 = every citation
  verified, 1 = at least one unresolved citekey, 2 = bad usage,
  3 = the ledger could not be read, so nothing was checked.

  Every argument is a file to check. Reads only content/ledger.sqlite
  via stdlib sqlite3, so it runs under a bare python3 with no venv.

Options:
  -h, --help  Show this message and exit."""


def main(argv: list[str] | None = None) -> int:
    # Not argparse: a stdlib-only gate with no options. -h/--help must
    # still be answered rather than read as a filename.
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 1:
        print(USAGE, file=sys.stderr)
        return 2
    if argv[0] in ("-h", "--help"):
        print(USAGE)
        return 0
    return run(argv)
