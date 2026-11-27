from pathlib import Path

from tests.skill_text import collapsed, skill_text

SKILL = (
    Path(__file__).resolve().parent.parent / ".claude" / "skills" / "book-assembler" / "SKILL.md"
)


CONVENTIONS = SKILL.parent / "references" / "latex-conventions.md"
SKELETON = SKILL.parent / "assets" / "book-skeleton.tex"


def _body() -> str:
    return skill_text(SKILL) + " " + collapsed(SKELETON.read_text(encoding="utf-8"))


def test_the_skeleton_is_an_asset_the_conventions_name():
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
    body = _body()
    assert "The author is the outline's `- author:` line" in body
    assert "ask the user only if it has none, never invent one" in body


def test_the_skeleton_has_a_slot_for_each_kind_of_matter():
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
    body = _body()
    assert "print every finding to the user, in full, before composing" in body


def test_the_assembler_says_the_check_cannot_block():
    assert "exits 0 whatever it finds" in _body()


def test_the_assembler_confirms_both_human_gates():
    body = _body()
    assert "-m chitragupta.draft spec status" in body, "the outline sign-off is the first gate"
    assert "-m chitragupta.draft unit status" in body, "assembling unaccepted prose is the failure"
    assert "Do not say the book is finished" in body, "the second gate is a person's"


def test_the_assembler_runs_the_gate_on_what_it_composed():
    assert "-m chitragupta.draft gate content/rendered/<book>/book.tex" in _body()


def test_the_assembler_writes_no_prose_and_says_where_that_line_is():
    body = _body()
    assert "It writes no prose." in body
    assert "draft-reviser" in body, "a wording change belongs to the reviser, not here"


def test_a_unit_is_converted_by_render_with_the_fragment_flag():
    body = _body()
    assert "--format tex --fragment" in body
    assert "--fragment --output-dir" not in body, "the default already mirrors there"


def test_the_book_carries_one_bibliography_built_by_bibtex():
    body = _body()
    assert r"\bibliographystyle{IEEEtran}" in body
    assert r"\usepackage[numbers,sort&compress]{natbib}" in body
    assert r"\addcontentsline{toc}{chapter}{Bibliography}" in body, "it is a chapter*"


def test_the_build_runs_bibtexu_between_the_lualatex_passes():
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
    assert "Read `book.log` before believing the PDF" in _body()


def test_the_citeproc_macro_file_is_gone_and_says_so():
    body = _body()
    assert "No `citeproc-defs.def`" in body
    assert "drop both the line and the file" in body


def test_the_assembly_is_composed_into_rendered_not_beside_its_units():
    body = _body()
    assert "content/rendered/<book>/book.tex" in body
    assert "content/rendered/<book>/book.md" in body
    assert "cd content/rendered/<book>" in body, "the build runs where the \\input paths resolve"


def test_the_skeleton_states_its_numbering_and_stops_the_toc_at_sections():
    body = _body()
    assert r"\setcounter{secnumdepth}{2}" in body
    assert r"\setcounter{tocdepth}{1}" in body
    assert r"\setcounter{secnumdepth}{-2}" in body, "still the documented override"


def test_an_authored_preamble_is_optional_copied_and_input_last():
    body = _body()
    assert "content/specs/<book>/preamble.tex" in body
    assert r"\input{preamble}" in body
    assert "last line of the preamble" in body, "an override after \\begin{document} is too late"
    assert "write no `\\input` and say nothing about it" in body


def test_the_brace_protection_requirement_is_documented():
    book_doc = (Path(__file__).resolve().parent.parent / "docs" / "book" / "ASSEMBLE.md").read_text(
        encoding="utf-8"
    )
    assert "Brace-protect acronyms" in book_doc
    assert "{IoT}" in book_doc


def test_the_book_loads_the_float_settings_and_reports_a_lone_figure():
    body = _body()
    assert r"\input{chitragupta-floats}" in body
    assert "chitragupta float page:" in body, "the line the shipped file writes to book.log"
    assert "not a failure of the build" in body, "a tall figure is the author's call"


def test_the_index_is_built_only_with_its_outline_entry_and_prints_last():
    body = _body()
    assert "--index content/rendered/<book>/index-terms.json # only with {#index}" in body
    assert "--index-terms content/rendered/<book>/index-terms.json" in body
    assert "registry index \\ content/drafts/<book> --idx content/rendered/<book>/book.idx" in body
    skeleton = SKELETON.read_text(encoding="utf-8")
    assert skeleton.index(r"\makeindex[noautomatic,intoc]") < skeleton.index("{hyperref}")
    assert skeleton.index(r"\bibliography{bibliography}") < skeleton.index(r"\printindex")
    conventions = CONVENTIONS.read_text(encoding="utf-8")
    assert "**The index** (docs/book/BOOK-INDEX.md)" in conventions
    assert "Front and back matter" in conventions
