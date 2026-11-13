"""The redline: latexdiff over two deferred renders, compiled to a PDF.

Both sides are standalone articles whose citations are still
`\\citep{key}` (`render(..., defer_citations=True)`), so latexdiff marks
a citation only where one was added or dropped. Its output is patched
here rather than configured: latexdiff's default markup loads `ulem`,
which TeX Live's `texlive-luatex` does not carry, and `--preamble`
needs a Perl module the bare script lacks (plans/draft-diff.md, "Spike
findings"). So the markup is redefined with `lua-ul`, which does ship
there, after latexdiff's own preamble and before `\\begin{document}`.

A redrawn figure behind `\\input` gives latexdiff nothing to mark, and a
moved section reads to it as one deletion and one insertion; the change
report knows both, so they are flagged in the margin from it.
"""

import re
import shutil
from pathlib import Path

# `_run` is this module's one patch point for its launches, as in
# `review/figure_layout/_probe.py`: a test fakes it here and nowhere else.
from subprocess import run as _run

from chitragupta import config, programs
from chitragupta.draft_diff._compare import ChangeReport, SectionChange
from chitragupta.draft_diff._report import header
from chitragupta.render_output._errors import MissingBinary

# The spike's settings, measured: a 1 in margin wraps a note a word per line.
_HOUSE_MARKUP = r"""%DIF chitragupta house markup: lua-ul
\usepackage{lua-ul}
\usepackage{marginnote}
\geometry{right=2.2in,marginparwidth=1.8in}
\definecolor{DIFaddcolor}{rgb}{0,0.30,0.75}
\definecolor{DIFdelcolor}{rgb}{0.75,0,0}
\RenewDocumentCommand{\DIFadd}{m}{{\color{DIFaddcolor}\underLine{#1}}}
\RenewDocumentCommand{\DIFdel}{m}{{\color{DIFdelcolor}\strikeThrough{#1}}}
\RenewDocumentCommand{\DIFaddFL}{m}{{\color{DIFaddcolor}\underLine{#1}}}
\RenewDocumentCommand{\DIFdelFL}{m}{{\color{DIFdelcolor}\strikeThrough{#1}}}
\newcommand{\cgchangenote}[1]{\marginnote{\footnotesize\sffamily #1}}
"""

_BEGIN_DOCUMENT = "\\begin{document}"

# latexdiff's UNDERLINE preamble: the `ulem` load, and the AMSMATHULEM
# block that wraps ulem's `\sout` for math (it ends where the next
# `%DIF <NAME> PREAMBLE` section starts). Its listings style names
# `\sout` and `\uwave` too; those keep their colour and lose the rule.
_ULEM_LOAD = re.compile(r"^\\RequirePackage\[[^]\n]*\]\{ulem\}.*\n", re.MULTILINE)
_AMSMATHULEM = re.compile(
    r"^%DIF AMSMATHULEM PREAMBLE.*\n(?:(?!%DIF [A-Z_]+ PREAMBLE).*\n)*", re.MULTILINE
)
_LISTINGS_ULEM = re.compile(r"\\(?:sout|uwave)\]")

# What bibtex prints last when it met an error, and only then: an error
# count, or the line a fatal error stops it with.
_BIBTEX_ERRORS = re.compile(
    r"^\((There (?:was|were) \d+ error messages?|That was a fatal error)\)", re.MULTILINE
)
_BIBLIOGRAPHY = re.compile(r"\\bibliography\{[^}]*\}")
_HEADING = re.compile(r"\\(?:sub){0,2}section\*?\{")

_TEX_SPECIALS = {
    "\\": r"\textbackslash{}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
    **{char: "\\" + char for char in "#%&_${}"},
}
_TEX_SPECIAL_RE = re.compile("[" + re.escape("".join(_TEX_SPECIALS)) + "]")

_LATEXDIFF_HINT = (
    "'latexdiff' is not on PATH; the redline needs it. On Debian/Ubuntu it "
    "ships in texlive-extra-utils (with the Perl modules it needs); "
    "`python -m chitragupta doctor` checks it. The Markdown report does not need it."
)


class RedlineFailed(RuntimeError):
    """The redline did not compile, even with `--math-markup=whole`."""


def _escape(text: str) -> str:
    return _TEX_SPECIAL_RE.sub(lambda m: _TEX_SPECIALS[m.group()], text)


def _group_end(text: str, opened: int) -> int:
    """The offset just past the `}` closing the group whose `{` is at `opened`."""
    depth, at = 0, opened
    while at < len(text):
        char = text[at]
        if char == "\\":
            at += 2
            continue
        depth += char == "{"
        depth -= char == "}"
        at += 1
        if depth == 0:
            return at
    return len(text)


def _without_groups(text: str, command: re.Pattern) -> str:
    """`text` with every `command{...}`, argument and all, taken out."""
    while match := command.search(text):
        text = text[: match.start()] + text[_group_end(text, match.end() - 1) :]
    return text


_DELETED = re.compile(r"\\(?:DIFdel|DIFdelFL|label)\{")
_COMMENT = re.compile(r"(?<!\\)%.*")
_ESCAPED = re.compile(r"\\([^A-Za-z])")
_CONTROL_WORD = re.compile(r"\\[A-Za-z@]+\*?")


def _plain_title(argument: str) -> str:
    """A heading's argument as the change report titles it: deleted text,
    labels, comments and markup gone, whitespace normalised."""
    text = _COMMENT.sub("", _without_groups(argument, _DELETED))
    text = _CONTROL_WORD.sub("", text)
    text = _ESCAPED.sub(r"\1", text).replace("~", " ")
    return " ".join(text.replace("{", "").replace("}", "").split())


def _heading_ends(tex: str) -> dict[str, list[int]]:
    """Each plain heading title, with the offset just past each heading."""
    ends: dict[str, list[int]] = {}
    for match in _HEADING.finditer(tex):
        end = _group_end(tex, match.end() - 1)
        title = _plain_title(tex[match.end() : end - 1])
        if title:
            ends.setdefault(title, []).append(end)
    return ends


def _section_note(change: SectionChange) -> str:
    notes = (["moved"] if change.kind == "moved" else []) + [f"log: {e}" for e in change.log]
    # One note per heading: two `\marginnote`s at one place print over each other.
    return "\\newline ".join(_escape(note) for note in notes)


def _section_inserts(tex: str, report: ChangeReport) -> list[tuple[int, str]]:
    ends, seen = _heading_ends(tex), {}
    inserts = []
    for change in report.sections:
        if change.kind == "removed":
            continue
        title = " ".join(change.title.split())
        occurrence = seen[title] = seen.get(title, -1) + 1
        note = _section_note(change)
        anchors = ends.get(title, [])
        if note and occurrence < len(anchors):
            inserts.append((anchors[occurrence], f"\\cgchangenote{{{note}}}"))
    return inserts


def _figure_inserts(tex: str, report: ChangeReport) -> list[tuple[int, str]]:
    note = f"\\cgchangenote{{figure redrawn since {_escape(report.old.ref)}}}"
    return [
        (match.start(), note)
        for figure in report.figures or []
        if figure.kind == "redrawn"
        for match in re.finditer(re.escape(f"\\input{{{figure.name}.tex}}"), tex)
    ]


def _banner(report: ChangeReport) -> str:
    return (
        "\\noindent\\fbox{\\parbox{\\dimexpr\\linewidth-2\\fboxsep-2\\fboxrule\\relax}"
        f"{{\\sffamily\\small {_escape(header(report))}\\quad "
        "\\DIFadd{added} \\DIFdel{removed}}}\\par\\medskip\n"
    )


def patch(diff_tex: str, report: ChangeReport) -> str:
    """latexdiff's output with the house markup, the header and legend,
    the project's bibliography and the change report's margin notes."""
    tex = _ULEM_LOAD.sub("", diff_tex)
    tex = _AMSMATHULEM.sub("", tex)
    tex = _LISTINGS_ULEM.sub("]", tex)
    tex = _BIBLIOGRAPHY.sub(lambda _: "\\bibliography{bibliography}", tex)
    inserts = _section_inserts(tex, report) + _figure_inserts(tex, report)
    for at, text in sorted(inserts, reverse=True):
        tex = tex[:at] + text + tex[at:]
    before, begin, after = tex.partition(_BEGIN_DOCUMENT)
    return f"{before}{_HOUSE_MARKUP}{begin}\n{_banner(report)}{after}"


def _refuse_missing(**found: "str | None") -> None:
    if found["latexdiff"] is None:
        raise MissingBinary(_LATEXDIFF_HINT)
    for name, path in found.items():
        if path is None:
            raise MissingBinary(
                f"'{name}' is not on PATH; the redline compiles with LuaLaTeX and bibtexu."
            )


def _write_diff(latexdiff: str, math: str, old: Path, new: Path, target: Path, report) -> None:
    result = _run(
        [latexdiff, f"--math-markup={math}", str(old), str(new)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:
        raise RedlineFailed(f"latexdiff failed on {old} and {new}:\n{result.stderr.strip()}")
    target.write_text(patch(result.stdout, report), encoding="utf-8")


def _lualatex(lualatex: str, work: Path, name: str) -> bool:
    argv = [lualatex, "-interaction=nonstopmode", name]
    return _run(argv, cwd=work, capture_output=True, check=False).returncode == 0


def _compile(lualatex: str, bibtexu: str, work: Path, name: str) -> bool:
    """lualatex, bibtexu, lualatex twice; False on a LuaLaTeX failure.

    `bibtexu` exits 1 on warnings alone (an empty `booktitle`), so its
    `.blg` is read for an error instead, as book-assembler's build does.
    Only its closing error count is read: the word "error" elsewhere in
    the log can be the aux file's name or a warned citekey.
    """
    for leftover in (".aux", ".bbl", ".blg"):
        (work / f"{name}{leftover}").unlink(missing_ok=True)
    if not _lualatex(lualatex, work, f"{name}.tex"):
        return False
    _run([bibtexu, name], cwd=work, capture_output=True, check=False)
    blg = work / f"{name}.blg"
    if not blg.is_file():
        raise RedlineFailed(f"bibtexu wrote no {blg.name} in {work}; it did not run.")
    summary = _BIBTEX_ERRORS.search(blg.read_text(encoding="utf-8", errors="replace"))
    if summary:
        raise RedlineFailed(f"bibtexu failed ({summary.group(1)}); see {blg}.")
    return all(_lualatex(lualatex, work, f"{name}.tex") for _ in range(2))


def redline(old_tex: Path, new_tex: Path, report: ChangeReport, out_dir: Path, stem: str) -> Path:
    """Compiles `<stem>.diff.pdf` from two deferred renders; returns its path in `out_dir`.

    Works in `new_tex`'s directory, which holds the new side's
    `figures/` and `bibliography.bib`. A LuaLaTeX failure is retried
    once with `--math-markup=whole`, which replaces a changed formula
    whole rather than marking inside it; a second failure raises
    `RedlineFailed` naming the `.diff.tex` and `.log` it leaves behind.
    """
    latexdiff = programs.resolve_program("latexdiff")
    lualatex = programs.resolve_program("lualatex")
    bibtexu = programs.resolve_program("bibtexu")
    _refuse_missing(latexdiff=latexdiff, lualatex=lualatex, bibtexu=bibtexu)
    work, name = Path(new_tex).parent, f"{stem}.diff"
    diff_tex, diff_pdf = work / f"{name}.tex", work / f"{name}.pdf"
    # The stem is the caller's; a `..` in it would write beside the work
    # directory rather than in it.
    if not config.resolves_inside(diff_tex, work):
        raise ValueError(f"{stem!r} is not a file name: it would write {diff_tex.resolve()}")
    for math in ("coarse", "whole"):
        _write_diff(latexdiff, math, Path(old_tex), Path(new_tex), diff_tex, report)
        if _compile(lualatex, bibtexu, work, name):
            break
    else:
        raise RedlineFailed(
            "The redline did not compile, with --math-markup=coarse or whole. "
            f"Kept: {diff_tex} and {work / f'{name}.log'}."
        )
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for built in (diff_tex, diff_pdf):
        if built.parent.resolve() != out_dir.resolve():
            shutil.copy2(built, out_dir / built.name)
    return out_dir / diff_pdf.name
