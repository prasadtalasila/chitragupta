"""Tests for chitragupta/draft_diff's redline: latexdiff's output patched
with the house markup and margin notes, and the compile around it.

`patch` is tested on a stored, trimmed latexdiff output of two deferred
renders of the spike scenario (a moved section, a new citation, a
changed fraction, a redrawn figure), so what it is handed is what
latexdiff really writes. `redline`'s launches are faked at the module's
one patch point, `_redline._run`; no TeX or latexdiff runs here.
"""

import subprocess
from pathlib import Path

import pytest

from chitragupta import config, programs
from chitragupta.draft_diff import _redline
from chitragupta.draft_diff._compare import ChangeReport, FigureChange, SectionChange
from chitragupta.draft_diff._views import VersionView
from chitragupta.render_output import MissingBinary
from tests.conftest import REPO_ROOT

FIXTURE = Path(__file__).parent / "fixtures" / "draft_diff" / "latexdiff-output.tex"


def _view(ref, label="", date=""):
    return VersionView(ref=ref, label=label, date=date, text="", suffix=".md", figures={})


def _report(**fields):
    defaults = dict(
        old=_view("003", "sent to supervisor", "2026-11-10"),
        new=_view("current draft"),
        sections=[
            SectionChange("(before the first heading)", "unchanged", 0),
            SectionChange("1. Introduction", "changed", 6, ["2026-11-12 tighten intro"]),
            SectionChange("4. Integrating with everything else", "moved", 0),
            SectionChange("3. Using the state stream", "unchanged", 0),
            SectionChange("5a. A worked estimate", "changed", 1),
        ],
        citekeys_added=[],
        citekeys_dropped=[],
        figures=[FigureChange("figures/estimator-loop", "redrawn", "both")],
    )
    defaults.update(fields)
    return ChangeReport(**defaults)


@pytest.fixture
def diff_tex():
    return FIXTURE.read_text(encoding="utf-8")


def test_patch_inserts_house_markup_before_document(diff_tex):
    out = _redline.patch(diff_tex, _report())
    preamble, _, _ = out.partition("\\begin{document}")
    for line in (
        "\\usepackage{lua-ul}",
        "\\usepackage{marginnote}",
        "\\geometry{right=2.2in,marginparwidth=1.8in}",
        "\\definecolor{DIFaddcolor}{rgb}{0,0.30,0.75}",
        "\\definecolor{DIFdelcolor}{rgb}{0.75,0,0}",
        "\\RenewDocumentCommand{\\DIFadd}{m}{{\\color{DIFaddcolor}\\underLine{#1}}}",
        "\\RenewDocumentCommand{\\DIFdel}{m}{{\\color{DIFdelcolor}\\strikeThrough{#1}}}",
        "\\RenewDocumentCommand{\\DIFaddFL}{m}",
        "\\RenewDocumentCommand{\\DIFdelFL}{m}",
        "\\newcommand{\\cgchangenote}[1]{\\marginnote{\\footnotesize\\sffamily #1}}",
    ):
        assert line in preamble
    # After latexdiff's own definitions, which `\RenewDocumentCommand` needs.
    assert preamble.index("\\providecommand{\\DIFadd}") < preamble.index("\\usepackage{lua-ul}")
    assert out.count("\\begin{document}") == 1


def test_patch_header_and_legend_after_begin_document(diff_tex):
    out = _redline.patch(diff_tex, _report())
    _, _, body = out.partition("\\begin{document}")
    banner = body.lstrip().splitlines()[0]
    assert banner.startswith("\\noindent\\fbox{\\parbox{")
    assert "Changes since 003 · sent to supervisor · 2026-11-10 — review copy" in banner
    assert "\\DIFadd{added} \\DIFdel{removed}" in banner


def test_patch_escapes_tex_specials_in_the_header(diff_tex):
    old = _view("draft_v2#final.md", "50% & {more} ~$x^2$ \\o/")
    out = _redline.patch(diff_tex, _report(old=old, figures=None))
    assert (
        "Changes since draft\\_v2\\#final.md · 50\\% \\& \\{more\\} "
        "\\textasciitilde{}\\$x\\textasciicircum{}2\\$ \\textbackslash{}o/ — review copy"
    ) in out


def test_patch_rewrites_bibliography_path(diff_tex):
    out = _redline.patch(diff_tex, _report())
    assert "\\bibliography{bibliography}" in out
    assert "references.bib" not in out


def test_patch_flags_redrawn_figure_moved_and_logged_sections(diff_tex):
    out = _redline.patch(diff_tex, _report())
    assert (
        "{\\centering\\cgchangenote{figure redrawn since 003}\\input{figures/estimator-loop.tex}"
        in out
    )
    assert (
        "\\subsection{1. Introduction}\\cgchangenote{log: 2026-11-12 tighten intro}"
        "\\label{introduction}"
    ) in out
    # On the inserted heading, never on the struck-out one it moved from.
    assert "else}}\\cgchangenote{moved}\\label{integrating-with-everything-else}" in out
    assert out.count("\\cgchangenote{moved}") == 1
    # Changed but unlogged: no note.
    assert "\\subsection{5a. A worked estimate}\\label" in out


def test_patch_joins_a_moved_and_logged_sections_notes(diff_tex):
    moved = SectionChange("4. Integrating with everything else", "moved", 0, ["2026-11-12 move it"])
    out = _redline.patch(diff_tex, _report(sections=[moved]))
    assert "\\cgchangenote{moved\\newline log: 2026-11-12 move it}" in out


def test_patch_skips_notes_without_an_anchor(diff_tex):
    report = _report(
        sections=[
            SectionChange("9. Not here", "moved", 0),
            SectionChange("4. Integrating with everything else", "removed", 30),
            # The second section of this title has no heading of its own.
            SectionChange("1. Introduction", "unchanged", 0),
            SectionChange("1. Introduction", "moved", 0),
        ],
        figures=[
            FigureChange("figures/ghost", "redrawn", "both"),
            FigureChange("figures/estimator-loop", "added", "both"),
        ],
    )
    out = _redline.patch(diff_tex, report)
    assert "\\cgchangenote{" not in out


def test_patch_leaves_no_ulem_dependency(diff_tex):
    assert "ulem" in diff_tex
    out = _redline.patch(diff_tex, _report())
    assert "ulem" not in out
    assert "ULEM" not in out
    assert "\\sout@orig" not in out
    assert "\\color{red}]" in out and "\\color{blue}]" in out


def test_plain_title_drops_markup_labels_and_deleted_text():
    assert _redline._plain_title("\\DIFadd{3. Using}~the \\DIFdel{old} \\emph{state} \\& x") == (
        "3. Using the state & x"
    )
    assert _redline._plain_title("A % comment\n\\label{a}B") == "A B"
    # An unclosed group reaches the end rather than looping.
    assert _redline._group_end("{abc", 0) == 4


# --- redline ---------------------------------------------------------------


@pytest.fixture
def on_path(monkeypatch):
    def install(*names):
        monkeypatch.setattr(
            programs, "resolve_program", lambda name: f"/bin/{name}" if name in names else None
        )

    return install


class _Launches:
    """A fake `_run`: records each argv; lualatex succeeds or fails on cue."""

    def __init__(
        self, diff_tex, lualatex_ok=lambda attempt: True, blg="Done.\n", aux="\\citation{k}\n"
    ):
        self.argvs, self.attempt = [], 0
        self.diff_tex, self.lualatex_ok, self.blg, self.aux = diff_tex, lualatex_ok, blg, aux

    def __call__(self, argv, cwd=None, **_):
        self.argvs.append(argv)
        name = Path(argv[0]).name
        if name == "latexdiff":
            self.attempt += 1
            return subprocess.CompletedProcess(argv, 0, stdout=self.diff_tex, stderr="")
        work = Path(cwd)
        if name == "bibtexu":
            if self.blg is not None:
                (work / f"{argv[1]}.blg").write_text(self.blg)
            return subprocess.CompletedProcess(argv, 1)
        ok = self.lualatex_ok(self.attempt)
        (work / argv[-1].replace(".tex", ".aux")).write_text(self.aux)
        if ok:
            (work / argv[-1].replace(".tex", ".pdf")).write_bytes(b"%PDF-1.5")
        return subprocess.CompletedProcess(argv, 0 if ok else 1)


def _sides(tmp_path):
    old, new = tmp_path / "old" / "survey.tex", tmp_path / "new" / "survey.tex"
    for side in (old, new):
        side.parent.mkdir(parents=True)
        side.write_text("\\documentclass{article}\n")
    return old, new


def test_redline_requires_latexdiff(on_path, tmp_path):
    on_path("lualatex", "bibtexu")
    old, new = _sides(tmp_path)
    with pytest.raises(MissingBinary) as raised:
        _redline.redline(old, new, _report(), tmp_path / "out", "survey")
    assert "apt install latexdiff" in str(raised.value)
    assert "python -m chitragupta doctor" in str(raised.value)


def test_os_deps_installs_the_latexdiff_the_hint_names():
    """The hint sends the reader to os-deps, so its apt line must name the
    `latexdiff` package itself: texlive-extra-utils only Suggests it."""
    script = (REPO_ROOT / "scripts" / "install_full_pipeline.sh").read_text(encoding="utf-8")
    install = script[script.index("install_os_deps() {") :]
    apt = install[install.index("apt-get install") : install.index("libgl1")]
    assert "latexdiff" in apt.split()


def test_redline_requires_lualatex(on_path, tmp_path):
    on_path("latexdiff", "bibtexu")
    old, new = _sides(tmp_path)
    with pytest.raises(MissingBinary, match="lualatex"):
        _redline.redline(old, new, _report(), tmp_path / "out", "survey")


def test_redline_command_lines(monkeypatch, on_path, tmp_path, diff_tex):
    on_path("latexdiff", "lualatex", "bibtexu")
    old, new = _sides(tmp_path)
    launches = _Launches(diff_tex, blg="Warning--empty booktitle in x\n")
    monkeypatch.setattr(_redline, "_run", launches)

    pdf = _redline.redline(old, new, _report(), tmp_path / "out", "survey")

    assert pdf == tmp_path / "out" / "survey.diff.pdf" and pdf.is_file()
    assert "\\cgchangenote{moved}" in (tmp_path / "out" / "survey.diff.tex").read_text()
    assert (new.parent / "survey.diff.tex").is_file()
    latexdiff, *compile_steps = launches.argvs
    assert latexdiff == ["/bin/latexdiff", "--math-markup=coarse", str(old), str(new)]
    assert not any(flag.startswith(("--flatten", "--preamble", "--type")) for flag in latexdiff)
    lualatex = ["/bin/lualatex", "-interaction=nonstopmode", "survey.diff.tex"]
    assert compile_steps == [lualatex, ["/bin/bibtexu", "survey.diff"], lualatex, lualatex]


def test_redline_into_its_own_work_directory(monkeypatch, on_path, tmp_path, diff_tex):
    on_path("latexdiff", "lualatex", "bibtexu")
    old, new = _sides(tmp_path)
    monkeypatch.setattr(_redline, "_run", _Launches(diff_tex))
    assert _redline.redline(old, new, _report(), new.parent, "survey").is_file()


def test_redline_retries_with_whole_math_then_fails(monkeypatch, on_path, tmp_path, diff_tex):
    on_path("latexdiff", "lualatex", "bibtexu")
    old, new = _sides(tmp_path)
    launches = _Launches(diff_tex, lualatex_ok=lambda attempt: False)
    monkeypatch.setattr(_redline, "_run", launches)

    with pytest.raises(_redline.RedlineFailed) as raised:
        _redline.redline(old, new, _report(), tmp_path / "out", "survey")

    message = str(raised.value)
    assert str(new.parent / "survey.diff.tex") in message
    assert str(new.parent / "survey.diff.log") in message
    diffs = [argv for argv in launches.argvs if argv[0].endswith("latexdiff")]
    assert [argv[1] for argv in diffs] == ["--math-markup=coarse", "--math-markup=whole"]
    assert not (tmp_path / "out").exists()


def test_redline_retry_succeeds(monkeypatch, on_path, tmp_path, diff_tex):
    on_path("latexdiff", "lualatex", "bibtexu")
    old, new = _sides(tmp_path)
    launches = _Launches(diff_tex, lualatex_ok=lambda attempt: attempt == 2)
    monkeypatch.setattr(_redline, "_run", launches)
    assert _redline.redline(old, new, _report(), tmp_path / "out", "survey").is_file()


def test_redline_fails_on_a_bibtexu_error(monkeypatch, on_path, tmp_path, diff_tex):
    on_path("latexdiff", "lualatex", "bibtexu")
    old, new = _sides(tmp_path)
    blg = (
        "I couldn't open database file bibliography.bib\n"
        "(There were 2 warnings)\n(There was 1 error message)\n"
    )
    monkeypatch.setattr(_redline, "_run", _Launches(diff_tex, blg=blg))
    with pytest.raises(_redline.RedlineFailed, match="1 error message") as raised:
        _redline.redline(old, new, _report(), tmp_path / "out", "survey")
    # What the spec's failure row promises: the artefacts kept, by path.
    message = str(raised.value)
    for kept in ("survey.diff.blg", "survey.diff.tex", "survey.diff.log"):
        assert str(new.parent / kept) in message


def test_redline_skips_bibtexu_without_citations(monkeypatch, on_path, tmp_path, diff_tex):
    """bibtexu errors on an aux with no `\\citation` ("I found no
    \\citation commands"), so a citation-free draft must not run it."""
    on_path("latexdiff", "lualatex", "bibtexu")
    old, new = _sides(tmp_path)
    # A leftover log from an earlier, cited run must not be read either.
    (new.parent / "survey.diff.blg").write_text("(There was 1 error message)\n")
    launches = _Launches(diff_tex, blg="(There was 1 error message)\n", aux="\\relax\n")
    monkeypatch.setattr(_redline, "_run", launches)

    assert _redline.redline(old, new, _report(), tmp_path / "out", "survey").is_file()

    lualatex = ["/bin/lualatex", "-interaction=nonstopmode", "survey.diff.tex"]
    assert launches.argvs[1:] == [lualatex] * 3


def test_redline_reads_a_bibliography_of_any_name(monkeypatch, on_path, tmp_path, diff_tex):
    """The render copies the project's `.bib` under its own name, which
    bibtex cannot open when it has a space; the redline reads it as
    `bibliography.bib`, the name `patch` writes."""
    on_path("latexdiff", "lualatex", "bibtexu")
    monkeypatch.setattr(config, "BIB_FILE_PATH", tmp_path / "papers" / "My Library.bib")
    old, new = _sides(tmp_path)
    (new.parent / "My Library.bib").write_text("@article{k, title={T}}\n")
    monkeypatch.setattr(_redline, "_run", _Launches(diff_tex))

    _redline.redline(old, new, _report(), tmp_path / "out", "survey")

    assert (new.parent / "bibliography.bib").read_text() == "@article{k, title={T}}\n"


def test_redline_fails_when_latexdiff_does(monkeypatch, on_path, tmp_path):
    on_path("latexdiff", "lualatex", "bibtexu")
    old, new = _sides(tmp_path)

    def broken(argv, **_):
        return subprocess.CompletedProcess(argv, 2, stdout="", stderr="Can't locate Foo.pm")

    monkeypatch.setattr(_redline, "_run", broken)
    with pytest.raises(_redline.RedlineFailed, match="Can't locate Foo.pm"):
        _redline.redline(old, new, _report(), tmp_path / "out", "survey")


def test_redline_refuses_a_stem_that_escapes_its_work_directory(on_path, tmp_path):
    on_path("latexdiff", "lualatex", "bibtexu")
    old, new = _sides(tmp_path)
    with pytest.raises(ValueError, match="not a file name"):
        _redline.redline(old, new, _report(), tmp_path / "out", "../survey")


def test_redline_passes_a_blg_whose_names_say_error(monkeypatch, on_path, tmp_path, diff_tex):
    on_path("latexdiff", "lualatex", "bibtexu")
    old, new = _sides(tmp_path)
    blg = (
        "The top-level auxiliary file: error-handling.diff.aux\n"
        "Warning--empty booktitle in hammingErrorDetecting1950\n"
        "(There was 1 warning)\n"
    )
    monkeypatch.setattr(_redline, "_run", _Launches(diff_tex, blg=blg))
    assert _redline.redline(old, new, _report(), tmp_path / "out", "error-handling").is_file()


def test_redline_fails_when_bibtexu_leaves_no_blg(monkeypatch, on_path, tmp_path, diff_tex):
    on_path("latexdiff", "lualatex", "bibtexu")
    old, new = _sides(tmp_path)
    # A clean log from an earlier run must not stand in for this one's.
    (new.parent / "survey.diff.blg").write_text("Done.\n")
    monkeypatch.setattr(_redline, "_run", _Launches(diff_tex, blg=None))
    with pytest.raises(_redline.RedlineFailed, match="bibtexu wrote no survey.diff.blg"):
        _redline.redline(old, new, _report(), tmp_path / "out", "survey")


def test_redline_fails_on_a_fatal_bibtexu_run(monkeypatch, on_path, tmp_path, diff_tex):
    on_path("latexdiff", "lualatex", "bibtexu")
    old, new = _sides(tmp_path)
    blg = "I couldn't open style file nosuch.bst\n(That was a fatal error)\n"
    monkeypatch.setattr(_redline, "_run", _Launches(diff_tex, blg=blg))
    with pytest.raises(_redline.RedlineFailed, match=r"bibtexu failed \(That was a fatal error\)"):
        _redline.redline(old, new, _report(), tmp_path / "out", "survey")
