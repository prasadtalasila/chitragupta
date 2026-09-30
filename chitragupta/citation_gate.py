"""Citation verification gate.

Every genre skill (survey/thesis-chapter/textbook-chapter/tutorial) MUST run this
against its own output before presenting a draft as finished. It is a
hard gate, not advisory: a citekey that doesn't resolve to something
`sync` actually pulled from the bib file is treated as fabricated and
blocks the draft.

This is not a hypothetical concern -- papers/DT-Simulation-Patterns/main.bib
in this same environment already contains entries a prior review marked
"WARNING: UNVERIFIABLE" (fabricated placeholders). A generative writer
must never be allowed to invent a citekey; it may only cite what is in
the ledger.

Usage:
    python -m chitragupta.draft gate <file> [<file> ...]

Recognizes any LaTeX/biblatex/natbib command whose name contains "cite"
(\\cite, \\citep, \\citealp, \\footcite, \\nocite, capitalized biblatex
forms, ..., with optional * and [] options) and Pandoc/Markdown ([@key],
[@key1; @key2], bare @key, suppressed-author -@key) citation syntax. Code
fences, inline code spans, and -- in LaTeX -- verbatim/lstlisting/
minted environments, `%` comments and \\verb are excluded from
scanning first (see _blank_code).

Known gaps, investigated and left as over-reporting (#834): a brace
group adjacent to a citation's own reads as a multicite group, so
`\\citep{k}{\\bfseries x}` offers `\\bfseries x` as a key; a macro
*defining* a citation, `\\newcommand{\\mc}[1]{\\citep{#1}}`, offers
`#1`. Both fail a sound draft rather than passing a fabricated key, so
the fix is to write the citation differently.
"""

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from chitragupta import _code_regions, config, gate_liveness, ledger

# Matches the command name by substring ("contains cite/Cite") rather than
# an explicit list of the standard cite/citep/citet/... names -- an earlier,
# enumerated version of this regex silently missed \citealp, \citealt,
# \footcite, \smartcite, \fullcite, \nocite, \citenum, \citeyearpar, and
# every capitalized biblatex form (\Citep, \Textcite, ...): ordered
# alternation tries "cite" first, matches as a prefix of "citealp", then
# fails to find the "{" that must immediately follow and never backs off to
# try the longer alternatives. That's a false negative on the invariant
# this gate exists to enforce (a fabricated key in an unrecognized command
# reads as "0 citations" instead of "unresolved"), so err toward matching
# too much (a stray "\path{cite-me}"-shaped command) over too little.
# _WS (not bare \s*) before the star, each [...] option group, and the
# final {...}: TeX itself skips whitespace between a control word and its
# arguments, so `\citep {key}` and `\citep\n{key}` are both valid and
# equivalent to `\citep{key}` -- without this, either would silently miss
# a real (or fabricated) citekey, the same false-negative class the rest
# of this regex already exists to close. Capped at a single optional
# newline rather than bare \s* for two independent reasons that both land
# on the same fix: (1) a blank line is \par in TeX, which is NOT
# skippable whitespace when scanning for a macro's argument, so
# `\citep\n\n{key}` isn't valid LaTeX either; (2) _blank_code (below)
# replaces a fenced/verbatim block with spaces but preserves its
# newlines, and a fenced block is always >=2 lines -- so bare \s* could
# bridge clean across a blanked-out code block and merge two unrelated
# pieces of text into one fake "citation" (e.g. `\nocite` before a
# verbatim block plus an unrelated `{...}` group after it), a false
# positive that would push the PostToolUse hook to block on invented
# grounds. A single optional newline can never span a whole blanked
# block, so the bridge is closed while `\citep\n{key}` keeps working.
#
# The *shape* of _WS is load-bearing too (#635): the earlier
# `[ \t]*\n?[ \t]*` was ambiguous -- a run of spaces could split between
# its two `[ \t]*` atoms every possible way -- and with _WS chained
# before the star, each option group and the key group, a `\cite`
# followed by N whitespace-separated `[...]` groups and no `{...}` made
# the engine explore ~2^N partitions before failing: ~160 bytes of text
# hung the gate past the hook's 30 s timeout, and a timed-out
# PostToolUse hook does not block, so a fabricated citekey elsewhere in
# the same file would have landed ungated. This form matches the same
# language (any [ \t] run with at most one newline inside) but admits
# exactly one parse of any input, so failure is linear.
_WS = r"[ \t]*(?:\n[ \t]*)?"
# Group 1 is the whole run of {key} groups, not one group's content:
# biblatex's multicite commands (\cites, \parencites, \footcites, ...)
# take one {keys} group *per citation*, optionally preceded by its own
# [pre][post] notes, and capturing only the first group let every key
# after it read as "0 citations" instead of unresolved -- the exact
# false-negative class this regex's whitespace tolerance was built to
# close. Trailing groups are consumed only when directly adjacent to the
# previous one (no _WS between groups, unlike before the first): that is
# how multicites are actually written, while `\citep{a} {\bfseries x}`
# is a citation followed by an ordinary prose brace group, and
# swallowing it would invent a citekey and block a sound draft.
# _CITE_KEYS_RE then walks the captured run group by group.
#
# Each _WS below sits between mandatory characters (command letters, `*`,
# `[`, `]`, `{`) and the star's _WS is inside its own optional group, so
# no two _WS atoms are ever adjacent: together with _WS's own
# single-parse shape that is what keeps matching linear (#635). It also
# makes the documented single-newline cap real -- the old chain of three
# adjacent _WS atoms accidentally accepted `\citep\n\n\n{key}`, which is
# a TeX paragraph break and not a citation.
_LATEX_CITE_RE = re.compile(
    r"\\[A-Za-z]*[Cc]ite[A-Za-z]*"
    rf"(?:{_WS}\*)?(?:{_WS}\[[^\]]*\])*{_WS}"
    r"(\{[^}]+\}(?:(?:\[[^\]]*\]){0,2}\{[^}]+\})*)"
)
# The bracket alternative matches first, so a note between two groups
# that itself contains braces ([\emph{cf}]) is consumed whole rather
# than its {cf} read as a key group -- an invented citekey would block a
# sound draft. Only alternation matches with group(1) set are keys.
_CITE_KEYS_RE = re.compile(r"\[[^\]]*\]|\{([^}]+)\}")
# Pandoc only treats @ as a citation marker when it isn't part of a larger
# token -- otherwise `\href{mailto:name@example.com}` (this project's own
# papers/ directory has author emails) would be misread as a citation.
# Citekey body includes '-' because bibtexparser-generated keys do (e.g.
# `jacoby_open-source_2023`, or a reference manager's own `-1`/`-2`
# disambiguation suffixes on duplicate entries) -- roughly a quarter of
# this project's synced citekeys contain one, so excluding it silently
# truncated matches. Backslash is excluded too: LaTeX's internal
# @-as-letter idiom (\makeatletter ... \@ifundefined{...}{}{} ...
# \makeatother, pandoc's own rendered .tex templates use this) would
# otherwise misread as a citation on `\@ifundefined` -- found via a
# retro-sweep over rendered .tex output, and load-bearing now that
# thesis-chapter-writer's content/drafts/<slug>.tex is hook-gated too.
# The first character admits digits and '_' as well as letters because
# Pandoc's own grammar does: requiring a letter made `[@3dprinting_2020]`
# invisible to the gate (0 citations) while pandoc still rendered it as a
# citation -- the false-negative direction, which always wins here.
# Pandoc's own citekey grammar, and the one definition of it in this
# package: an alphanumeric (or `_`) start, then alphanumerics, with
# `:.#$%&-+?<>~/` allowed only *between* them. The lookahead is what
# stops a sentence-final `.` or a closing `>` being eaten -- pandoc
# resolves `key` in "shown by @key.", not `key.`. Restricting the body to
# `[A-Za-z0-9_-]` truncated the key at the first of those characters, so
# the gate verified a *prefix* of what pandoc would look up: a draft
# citing `[@smith:2020]` passed on a ledger holding `smith`, and pandoc
# then rendered `[?]` -- the one thing this gate exists to catch. In the
# other direction a legitimate Better-BibTeX key (`doe.2020`) was refused
# as unknown, pushing an author to "fix" a correct citation.
#
# A hyphen *run* is matched whole, deliberately unlike pandoc, which
# stops at `--` (verified against `pandoc -t json` on this host). Keys
# with a doubled hyphen are real here -- bibtexparser collapses
# "as-a-service" into `zech_digital-twins-as--service_2024` -- and
# render_output/_citeproc.py already repairs that for pandoc by aliasing
# the run away in a temp copy. That repair is driven by this pattern, so
# matching pandoc's truncation here would both refuse the key at the gate
# and leave the alias unbuilt, silently dropping the citation instead.
PANDOC_KEY = r"[A-Za-z0-9_](?:[A-Za-z0-9_]|-+(?=[A-Za-z0-9_])|[:.#$%&+?<>~/](?=[A-Za-z0-9_]))*"
_PANDOC_CITE_RE = re.compile(rf"(?<![A-Za-z0-9._%+\-\\])-?@({PANDOC_KEY})")

# The teaching genres' whole job is worked code examples, and code routinely
# contains @-tokens that look like a Pandoc citation (Python's @dataclass,
# @property) or a LaTeX-command-shaped string that isn't one -- these are
# false positives, not the false negatives above, but with a PostToolUse
# hook (.claude/hooks/citation_gate_hook.py) now treating a FAIL as
# blocking, a false positive here actively pushes the agent to delete
# valid teaching code instead of a real fabricated citation. Blank out
# (not delete -- must preserve every other character's offset, since line
# numbers are computed from position in the original text) fenced code,
# inline code spans, and LaTeX verbatim-style environments before
# extraction. The verbatim environments are paired by
# `_code_regions.blank_latex_verbatim`, a linear scan: the DOTALL regex it
# replaced was O(N x L) on N unclosed openers, enough to get the gate hook
# killed before it could block (#824).
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
# LaTeX's other two ways of saying "this is not prose", scanned in one
# left-to-right alternation so whichever construct opens first wins, as
# in TeX itself: `\verb|50%|` keeps the following citation live, while
# `% \verb|x| \cite{k}` is commented out whole (#834).
#
# `\verb` first, or the escape-pair alternative below eats the `\v`. The
# delimiter is any non-letter, non-space character, which is what TeX
# allows -- the issue's proposed `(\S)` would read the `a` of
# `\verbatiminput` as a delimiter and blank up to the next `a`, hiding a
# real citation from the gate, and would read the `*` of `\verb*` as the
# delimiter and then never close.
#
# `\url`/`\href` take their argument with `%` catcode-other, so a `%`
# in one is a literal character and blanking to end of line there would
# *hide* a following citation from the gate -- the one direction this
# module must never fail in. They join the unchanged-return group for
# that reason, ahead of the escape pair so the whole argument is
# consumed, and only the first (URL) argument of `\href`.
#
# The escape-pair alternative is what makes `%` correct: a `%` starts a
# comment when an *even* number of backslashes precedes it, so `\%` is a
# literal percent but `\\%` (a line break, then a comment) is not. A
# one-character lookbehind, as the issue proposed, gets the second case
# wrong and lets a commented-out citekey through. Consuming each `\x`
# pair and leaving it unchanged tracks that parity exactly, the way
# TeX's own left-to-right scan does.
_LATEX_INERT_RE = re.compile(
    r"\\verb\*?([^A-Za-z\s])[^\n]*?\1"  # \verb<d>...<d>, \verb*<d>...<d>
    r"|(?P<esc>\\(?:url|href)\{[^}\n]*\}"  # a URL argument: `%` is ordinary there
    r"|\\[\s\S])"  # an escaped character: not a comment start
    r"|%[^\n]*"  # a comment, to the end of the line
)


def _blank_fenced(text: str) -> str:
    """Blank fenced code blocks, pairing fences the way CommonMark does.

    A fence is a line-start construct (up to three spaces of indent, then
    ``` or ~~~) -- an earlier version paired every ``` token in document
    order regardless of position, so one prose mention of ``` shifted the
    pairing for the rest of the file: the prose after it (real citations
    included) was blanked, and the next code block's interior exposed.
    An unclosed fence runs to the end of the document, as CommonMark
    reads it. Two deliberate approximations, both blanking-safe: the
    closing fence is matched on its first three characters (a longer
    close still closes), and a same-character fence line inside the
    block closes it even where CommonMark would want it longer.
    CommonMark's no-backtick-in-a-backtick-info-string rule is applied,
    and matters here: without it a line-start ``` code ``` span would
    open a phantom fence and blank every later citation in the file. A
    tab indents by four columns, so a tab-indented marker is indented
    code, not a fence.
    """
    out: list[str] = []
    fence: str | None = None
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip(" ")
        marker = stripped[:3] if stripped[:3] in ("```", "~~~") else None
        if len(line) - len(stripped) > 3:
            marker = None
        if fence is None and marker == "```" and "`" in stripped.lstrip("`"):
            marker = None
        if fence is None and marker is None:
            out.append(line)
            continue
        out.append(re.sub(r"[^\n]", " ", line))
        if fence is None:
            fence = marker
        elif marker == fence:
            fence = None
    return "".join(out)


def _blank_code(text: str, *, latex: bool = False) -> str:
    """Blank code-like regions to spaces, preserving every offset.

    `latex=True` blanks LaTeX's own inert regions -- verbatim-style
    environments, `%` comments and `\\verb` -- and none of Markdown's: in
    LaTeX a backtick is an open-quote character, not code markup, so
    applying the Markdown rules there blanked the span *between* two
    quoted phrases as "inline code" -- and any \\citep{...} inside it
    vanished, letting a fabricated citekey pass the gate as 0 citations.
    """

    def _blank_match(m: re.Match) -> str:
        return re.sub(r"[^\n]", " ", m.group(0))

    def _blank_unless_escaped(m: re.Match) -> str:
        return m.group(0) if m.group("esc") else _blank_match(m)

    text = _code_regions.blank_latex_verbatim(text)
    if latex:
        return _LATEX_INERT_RE.sub(_blank_unless_escaped, text)
    text = _blank_fenced(text)
    text = _INLINE_CODE_RE.sub(_blank_match, text)
    return text


@dataclass
class GateResult:
    path: Path
    unknown: list[tuple[int, str]] = field(default_factory=list)  # (line_no, citekey)
    total_citations: int = 0

    @property
    def ok(self) -> bool:
        return not self.unknown


def extract_citekeys_from_line(line: str) -> list[str]:
    """The keys extract_citekeys() finds in `line`, without their line numbers.

    It scans whatever string it is handed, newlines included, so the
    whole-document guarantees below hold for a caller that passes a whole
    document. The name records the one caller that does not:
    chitragupta/review/citation_coverage.py hands this one line at a time.
    The others -- review/_claim_sentence.py (a sentence's parts) and
    review/verbatim_check/_corpus.py (a passage) -- want only the keys.
    review/_claims.py, which holds whole blocks, calls extract_citekeys()
    directly since #854.

    A caller that splits a document into lines first loses two things,
    both from the same cause -- its newlines were cut out by something
    like str.splitlines() before this ever saw them:
    - False positive: a fenced code block spanning multiple lines needs
      both its opening and closing ``` in the same string for _blank_code
      to recognize it, so an in-code @token on its own line can still read
      as a citation.
    - False negative: TeX allows whitespace -- including a newline --
      between a control word and its argument (\\citep\n{key} is valid,
      equivalent to \\citep{key}), but a command on one line and its
      {key} argument on the next arrive as two separate,
      independently-unmatchable calls; neither one contains the whole
      pattern. extract_citekeys(text) run on the whole document catches
      this (see test_whitespace_including_newline_between_command_and_brace)
      because the newline between them is still present in its input.
    citation_coverage.py is informational-only, never a gate, so both
    gaps are known and low-stakes rather than worth complicating its
    per-line loop to close. Prefer extract_citekeys() for any new caller
    that has the whole document available.
    """
    return [key for _, key in extract_citekeys(line)]


def extract_citekeys(text: str, *, latex: bool = False) -> list[tuple[int, str]]:
    """Every citekey in `text` as (1-based line number, key).

    Scans the whole document rather than line-by-line so a `\\citep{...}`
    argument wrapped across lines (common once a document has more than a
    couple of citekeys in one call) is still caught -- a per-line scan
    would match on neither line and silently drop every key inside it.

    `latex=True` selects LaTeX-aware code blanking (see `_blank_code`):
    pass it for `.tex` input, where a backtick is a quote character and
    Markdown's inline-code rule would blank real citations.
    """
    text = _blank_code(text, latex=latex)

    # (start_offset, key) from both regexes, sorted into true document
    # order first -- LaTeX and Pandoc matches were previously collected in
    # two separate passes and concatenated, so a FAIL report could list a
    # later-in-file LaTeX citation before an earlier Pandoc one, making it
    # harder to locate by reading top-to-bottom.
    matches: list[tuple[int, str]] = []
    for match in _LATEX_CITE_RE.finditer(text):
        # group(1) is the full run of {key} groups (multicites carry one
        # per citation). The first group keeps the command's own offset --
        # the pinned contract for \citep\n{key} reports the command's
        # line -- and later groups take their own, which adjacency keeps
        # on the same line as the group before them.
        for group in _CITE_KEYS_RE.finditer(match.group(1)):
            if group.group(1) is None:  # a between-group bracket note, not keys
                continue
            start = match.start() if group.start() == 0 else match.start(1) + group.start()
            matches.extend((start, k.strip()) for k in group.group(1).split(",") if k.strip())
    for match in _PANDOC_CITE_RE.finditer(text):
        matches.append((match.start(), match.group(1)))
    matches.sort(key=lambda m: m[0])

    # One forward sweep instead of a fresh text.count("\n", 0, ...) per
    # match (previously O(text length) per citation, so O(N*M) overall) --
    # each match only needs the newlines since the previous match's start.
    keys: list[tuple[int, str]] = []
    line_no = 1
    pos = 0
    for start, key in matches:
        line_no += text.count("\n", pos, start)
        pos = start
        keys.append((line_no, key))
    return keys


def check_text(path: Path, text: str, known_citekeys: set[str]) -> GateResult:
    """Gate `text`, attributed to `path` for reporting.

    Split from `check_document` so a caller that must gate and then *act
    on* the same bytes can hold them: `unit accept` gated the file and
    then re-read it to hash and record its citekeys, so a write landing
    between the two calls got a permanent acceptance record for prose the
    gate never saw (#506/m-69). `path` is still needed -- the LaTeX rule
    below is chosen by suffix -- but it is not read here.
    """
    result = GateResult(path=path)
    # .tex drafts get LaTeX-aware blanking: a backtick there is a quote,
    # and the Markdown inline-code rule blanked real citations between
    # two quoted phrases (see _blank_code).
    latex = path.suffix.lower() == ".tex"
    for line_no, key in extract_citekeys(text, latex=latex):
        result.total_citations += 1
        if key not in known_citekeys:
            result.unknown.append((line_no, key))
    return result


def check_document(path: Path, known_citekeys: set[str]) -> GateResult:
    return check_text(path, path.read_text(encoding="utf-8"), known_citekeys)


def report(label: str, result: GateResult) -> None:
    """Print one document's verdict in the gate's own PASS/FAIL shape.

    One printer, so a caller gating a document it already holds in memory
    reports it identically to `run()` rather than paraphrasing it.
    """
    if result.ok:
        print(
            f"OK    {label}: {result.total_citations} citation(s), all verified against the ledger."
        )
        return
    print(f"FAIL  {label}: {len(result.unknown)} unresolved citekey(s):")
    for line_no, key in result.unknown:
        print(f"        {label}:{line_no}: @{key} not found in ledger -- not sourced from bib sync")


def run(paths: list[str]) -> int:
    # Said here because here is the only place it can be said: whether the
    # automatic gate is running at all -- a dead launcher, or a hook that
    # never fired on a draft (gate_liveness.py). When a hook is what
    # invoked this, it records instead, and nothing is printed.
    gate_liveness.observe(paths)

    # No ledger is not a reason to stop: it fails closed exactly as an
    # empty one does, since every citekey is then unknown, and a
    # citation-free draft still passes -- which the session-start hook's
    # gate probe relies on before a first sync. Read-only (#843), so the
    # gate never creates the ledger it is checking against.
    try:
        with ledger.reading() as con:
            known = ledger.known_citekeys(con)
        problem = "ledger is empty -- run `python -m chitragupta.corpus sync` first."
    except ledger.NoLedger as exc:
        known = set()
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
            # Reported per document and the loop continues, like a FAIL:
            # this tool's contract is that you hand it several files and
            # get a result for each, so one unusable path must not hide
            # the verdict on the rest. Exit 1 rather than the usage code
            # 2 for the same reason -- it is a document that did not
            # pass, alongside the others.
            all_ok = False
            print(f"FAIL  {p}: {exc}")
            continue
        result = check_document(checked, known)
        all_ok = all_ok and result.ok
        report(p, result)

    return 0 if all_ok else 1


USAGE = """usage: python -m chitragupta.draft gate <file> [<file> ...]

Fail if a draft cites a citekey the ledger doesn't hold. Exit 0 = every
citation verified, 1 = at least one unresolved citekey, 2 = bad usage.

Takes no options: every argument is a file to check. Reads only
content/ledger.sqlite via stdlib sqlite3, so it runs under a bare
python3 with no venv."""


def main(argv: list[str] | None = None) -> int:
    # Deliberately not argparse: this takes no options, and the whole
    # tool is a stdlib-only gate that several callers invoke on a list of
    # paths. But -h/--help still has to be answered, because a tool this
    # central is the first thing someone tries it on -- without this it
    # treated "--help" as a filename and died with a FileNotFoundError
    # traceback.
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 1:
        print(USAGE, file=sys.stderr)
        return 2
    if argv[0] in ("-h", "--help"):
        print(USAGE)
        return 0
    return run(argv)
