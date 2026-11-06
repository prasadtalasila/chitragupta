"""`book-assembler` must run the consistency check and surface it.

This file is where #138's "blocking global check" actually lives, and it
is worth saying why a text scan is the right enforcement rather than a
weak substitute for one.

`python -m chitragupta.draft registry check` exits 0 whatever it finds, because
docs/ARCHITECTURE.md's "Layer 4" says a check measured against a
machine's reading of prose "reports and never blocks, whichever layer it
lives in", and that what may be enforced is *invocation* rather than
conformance: "a harness may guarantee that it runs and that its findings
are seen, never that they were obeyed." The assembly skill is that
harness. So the guarantee is exactly this: the skill file tells the
assembling agent to run the check and to report every finding before
composing anything, and a hand edit that dropped either half would be
the bug.

Same shape and same reasoning as tests/test_skill_verbatim_scan_step.py
and tests/test_skill_style_check_step.py -- what the commands do has its
own tests (tests/test_registry.py, tests/test_unit.py, tests/test_spec.py);
this pins only that the skill still tells anyone to run them.
"""

from pathlib import Path

from tests.skill_text import collapsed, skill_text

SKILL = (
    Path(__file__).resolve().parent.parent / ".claude" / "skills" / "book-assembler" / "SKILL.md"
)


CONVENTIONS = SKILL.parent / "references" / "latex-conventions.md"
SKELETON = SKILL.parent / "assets" / "book-skeleton.tex"


def _body() -> str:
    """The skill, whitespace collapsed -- these files are hand-wrapped, so
    a command can sit across a line break without being a different
    command -- with its references spliced in where it names them (#997):
    the LaTeX conventions live in `references/latex-conventions.md`, and
    the document skeleton that reference copies from is
    `assets/book-skeleton.tex` (#1067), appended here the way a model
    reads it, one file further on."""
    return skill_text(SKILL) + " " + collapsed(SKELETON.read_text(encoding="utf-8"))


def test_the_skeleton_is_an_asset_the_conventions_name():
    """The skeleton is a template file, not a code block inside prose, so
    it is copied rather than retyped (#1067). The reference names it and
    no longer carries a second copy."""
    conventions = CONVENTIONS.read_text(encoding="utf-8")
    assert "`.claude/skills/book-assembler/assets/book-skeleton.tex`" in conventions
    assert r"\documentclass" not in conventions
    skeleton = SKELETON.read_text(encoding="utf-8")
    assert skeleton.startswith("%"), "it opens by saying it is a template"
    assert r"\documentclass[11pt,a4paper]{book}" in skeleton
    assert r"\end{document}" in skeleton


def test_the_skeleton_keeps_its_placeholders_for_the_model_to_fill():
    skeleton = SKELETON.read_text(encoding="utf-8")
    assert "<the outline's own title>" in skeleton
    assert "<the outline's - author: line; else ask the user, never invent one>" in skeleton


def test_the_author_comes_from_the_outline_and_is_never_invented():
    """#1137: the title page's author is the outline's `- author:` line,
    so it is written once rather than asked for on every assembly."""
    body = _body()
    assert "The author is the outline's `- author:` line" in body
    assert "ask the user only if it has none, never invent one" in body


def test_the_skeleton_has_a_slot_for_each_kind_of_matter():
    """#1137: front matter after the contents, appendices lettered by
    `\\appendix`, back matter in outline order before the bibliography,
    and the author's copyright page right after the title page."""
    skeleton = SKELETON.read_text(encoding="utf-8")
    order = [
        r"\maketitle",
        r"\input{copyright}",
        r"\tableofcontents",
        "{#front}'s entries",
        r"\mainmatter",
        r"\appendix",
        r"\backmatter",
        "{#back}'s entries",
        r"\bibliography{bibliography}",
    ]
    document = skeleton[skeleton.index(r"\begin{document}") :]
    positions = [document.index(marker) for marker in order]
    assert positions == sorted(positions)
    for macro in (
        r"\newcommand{\BookTitle}",
        r"\newcommand{\BookAuthor}",
        r"\newcommand{\BuildLine}",
    ):
        assert macro in skeleton


def test_the_conventions_place_every_reserved_id_and_keep_old_books_working():
    body = _body()
    for entry in (
        "{#front}",
        "{#appendices}",
        "{#back}",
        "{#glossary}",
        "{#symbols}",
        "{#figures}",
        "{#tables}",
    ):
        assert entry in body
    assert "**An outline with none of the three reserved parts** is one" in body
    assert "Never edit it: its wording, licence and year are the author's." in body
    assert "only if it has something to show" in body


def test_the_assembler_runs_the_consistency_check():
    assert "-m chitragupta.draft registry check" in _body()


def test_the_assembler_reports_every_finding_rather_than_summarising():
    """The half that matters. A check that ran and was paraphrased into
    "a few small issues" has not been surfaced."""
    body = _body()
    assert "print every finding to the user, in full, before composing" in body


def test_the_assembler_says_the_check_cannot_block():
    """So nobody later "fixes" the exit code to make the skill's refusal
    automatic -- which is the change DEVELOPER-AGENTS.md bars outright."""
    assert "exits 0 whatever it finds" in _body()


def test_the_assembler_confirms_both_human_gates():
    body = _body()
    assert "-m chitragupta.draft spec status" in body, "the outline sign-off is the first gate"
    assert "-m chitragupta.draft unit status" in body, "assembling unaccepted prose is the failure"
    assert "Do not say the book is finished" in body, "the second gate is a person's"


def test_the_assembler_runs_the_gate_on_what_it_composed():
    """Every unit passed the gate already; the assembled document is a
    new file, and this layer has one exit whatever produced the file."""
    assert "-m chitragupta.draft gate content/rendered/<book>/book.tex" in _body()


def test_the_assembler_writes_no_prose_and_says_where_that_line_is():
    body = _body()
    assert "It writes no prose." in body
    assert "draft-reviser" in body, "a wording change belongs to the reviser, not here"


def test_a_unit_is_converted_by_render_with_the_fragment_flag():
    """A plain `render --format tex` emits a standalone `article` with its
    own `\\begin{document}`, which cannot be `\\input` into a book -- this
    file said to use one until the first real assembly. `--fragment` is
    the flag that exists for it, and going through `render` rather than a
    restated pandoc invocation is what keeps the citeproc, IEEE-style and
    citekey-aliasing behaviour identical to every other rendered draft.

    No `--output-dir`: a draft's renders already mirror its own path, so
    `content/drafts/<book>/<id>.md` lands in `content/rendered/<book>/`,
    which is where `book.tex` is composed. Naming the directory again was
    what put assembly output in the authored one."""
    body = _body()
    assert "--format tex --fragment" in body
    assert "--fragment --output-dir" not in body, "the default already mirrors there"


def test_the_book_carries_one_bibliography_built_by_bibtex():
    """Citeproc numbers in the pass that builds the list, so resolving per
    unit and collecting the lists would leave chapter 1's `[2]` and
    chapter 2's `[2]` as different papers under one back-of-book entry.
    Deferring the resolution is what makes the numbers right."""
    body = _body()
    assert r"\bibliographystyle{IEEEtran}" in body
    assert r"\usepackage[numbers,sort&compress]{natbib}" in body
    assert r"\addcontentsline{toc}{chapter}{Bibliography}" in body, "it is a chapter*"


def test_the_build_runs_bibtexu_between_the_lualatex_passes():
    """Skip it and every citation renders `[?]` while lualatex exits 0.
    LuaLaTeX, the pdf render's engine, and `bibtexu`, because classic
    bibtex abbreviates `Ö.` by its first byte (#1037)."""
    body = _body()
    assert "lualatex -interaction=nonstopmode book.tex" in body
    assert "pdflatex -interaction" not in body
    assert "bibtexu book" in body
    assert "Four passes" in body


def test_the_assembler_writes_a_markdown_twin_of_the_book():
    body = _body()
    assert "write `book.md`" in body
    assert "hyperlinking the chapter files" in body


def test_the_assembler_checks_the_build_log_before_believing_the_pdf():
    """TeX exits 0 on a book that is missing something: a dropped
    citation is a warning, not an error."""
    assert "Read `book.log` before believing the PDF" in _body()


def test_the_citeproc_macro_file_is_gone_and_says_so():
    """A deferred fragment emits no `CSLReferences`, so there is nothing
    left for `citeproc-defs.def` to define. The skill still names the file
    -- an older `book.tex` on disk will still `\\input` it, and dropping
    both is part of re-assembling."""
    body = _body()
    assert "No `citeproc-defs.def`" in body
    assert "drop both the line and the file" in body


def test_the_assembly_is_composed_into_rendered_not_beside_its_units():
    """`content/drafts/<book>/` holds authored chapters only. Everything
    assembly produces is output, and output mirrors to `content/rendered/`
    like every other render -- which is also why step 4 needs no
    `--output-dir` to put the fragments beside `book.tex`."""
    body = _body()
    assert "content/rendered/<book>/book.tex" in body
    assert "content/rendered/<book>/book.md" in body
    assert "cd content/rendered/<book>" in body, "the build runs where the \\input paths resolve"


def test_the_skeleton_states_its_numbering_and_stops_the_toc_at_sections():
    """`secnumdepth{2}` restates the `book` class default so the book says
    what its numbering is; `tocdepth{1}` is the real departure (the class
    lists subsections). An outline's section titles carry no numbers, so
    there is nothing to be numbered twice."""
    body = _body()
    assert r"\setcounter{secnumdepth}{2}" in body
    assert r"\setcounter{tocdepth}{1}" in body
    assert r"\setcounter{secnumdepth}{-2}" in body, "still the documented override"


def test_an_authored_preamble_is_optional_copied_and_input_last():
    """`content/specs/<book>/preamble.tex` is where a book overrides the
    skeleton -- including the `-2` a self-numbering book needs. Absent is
    the ordinary case and must produce no `\\input` and no remark."""
    body = _body()
    assert "content/specs/<book>/preamble.tex" in body
    assert r"\input{preamble}" in body
    assert "last line of the preamble" in body, "an override after \\begin{document} is too late"
    assert "write no `\\input` and say nothing about it" in body


def test_the_brace_protection_requirement_is_documented():
    """Two IEEE implementations now format a book's references -- ieee.csl
    for a standalone render, IEEEtran.bst for the assembled book -- and
    they agree only where acronyms are brace-protected in the `.bib`.
    Unbraced, bibtex lowercases them ("iot", "ai") while citeproc does
    not, so the same entry is right in one artefact and wrong in the
    other. The pipeline deliberately does not rewrite a human's titles to
    fix it, which makes saying so the whole mitigation."""
    book_doc = (Path(__file__).resolve().parent.parent / "docs" / "book" / "ASSEMBLE.md").read_text(
        encoding="utf-8"
    )
    assert "Brace-protect acronyms" in book_doc
    assert "{IoT}" in book_doc


def test_the_book_loads_the_float_settings_and_reports_a_lone_figure():
    """#1065: a fragment has no preamble, so the book carries the float
    fractions `draft render` gives a standalone draft, and the build step
    reads back the figures that still landed on a float-only page."""
    body = _body()
    assert r"\input{chitragupta-floats}" in body
    assert "chitragupta float page:" in body, "the line the shipped file writes to book.log"
    assert "not a failure of the build" in body, "a tall figure is the author's call"


def test_the_index_is_built_only_with_its_outline_entry_and_prints_last():
    """#1168: the term table and the filter only with `{#index}`, the
    index's preamble before hyperref, `\\printindex` after the
    bibliography, and `registry index` between the third and last pass."""
    body = _body()
    assert "--index content/rendered/<book>/index-terms.json # only with {#index}" in body
    assert "--index-terms content/rendered/<book>/index-terms.json" in body
    assert "registry index \\ content/drafts/<book> --idx content/rendered/<book>/book.idx" in body
    skeleton = SKELETON.read_text(encoding="utf-8")
    assert skeleton.index(r"\makeindex[noautomatic,intoc]") < skeleton.index("{hyperref}")
    assert skeleton.index(r"\bibliography{bibliography}") < skeleton.index(r"\printindex")
    conventions = CONVENTIONS.read_text(encoding="utf-8")
    assert "**The index** (#1168" in conventions
    assert "Front and back matter" in conventions
