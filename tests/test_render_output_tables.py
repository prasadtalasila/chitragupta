"""chitragupta/render_output/_tables.py: captions, numbers and the per-format swap.

Split per module the way `tests/test_render_output_figures.py` and
`tests/test_render_output_math.py` are, mirroring
`chitragupta/render_output/`'s own split.

The discriminating tests here are `TestSubstituteLatexBound` and
`TestSubstituteMarkdown`: the same draft has to reach pandoc carrying a
`\\label` it will number itself, and reach the Markdown path -- which
never goes near pandoc -- carrying a number this module counted. Those
are two different answers to one question, and getting either wrong
produces a rendered table with no number at all, which is the defect
issue 395 is about.
"""

from chitragupta import render_output
from chitragupta.render_output import _tables


DRAFT = """\
# Platforms

The platforms in <!-- tableref: start-here --> differ in what they ask
you to bring.

| Starting point | Core idea |
|---|---|
| DTaaS | One tenant-facing platform |

: Where to start when building a first twin.
<!-- table: start-here -->

A second table follows, and <!-- tableref: costs --> prices it.

| Tier | Cost |
|---|---|
| Hot | High |

: What each retention tier costs.
<!-- table: costs -->
"""


class TestTables:
    def test_reads_id_caption_and_number_in_document_order(self):
        found = _tables.tables(DRAFT)
        assert [(t.id, t.number) for t in found] == [("start-here", 1), ("costs", 2)]
        assert found[0].caption == "Where to start when building a first twin."

    def test_a_draft_with_no_table_marker_declares_nothing(self):
        assert _tables.tables("Just prose, and a `: colon` span.\n") == []

    def test_a_caption_line_without_a_marker_declares_nothing(self):
        # The caption alone cannot be referred to, so it is not a table
        # this module knows about -- `warnings` is what says so.
        assert _tables.tables("| A |\n|---|\n| 1 |\n\n: Uncaptured.\n") == []


class TestSubstituteLatexBound:
    def test_caption_carries_a_label_and_the_marker_goes(self):
        out = _tables.substitute(DRAFT, "pdf")
        assert ": Where to start when building a first twin.\\label{tab:start-here}" in out
        assert "<!-- table:" not in out

    def test_a_reference_becomes_a_latex_ref_not_a_number(self):
        # The number is LaTeX's to assign: the same unit numbers "3" in an
        # article and "1.3" inside an assembled book, so writing one here
        # would be wrong in one of the two.
        #
        # Raw-attribute span, not a bare command: pandoc's Markdown reader
        # escapes `~` to `\textasciitilde{}`, which sets a literal tilde
        # between the word and the number. Caught by rendering a real
        # draft, not by reading the code.
        out = _tables.substitute(DRAFT, "tex")
        assert "The platforms in `Table~\\ref{tab:start-here}`{=latex} differ" in out
        assert "<!-- tableref:" not in out

    def test_latex_and_tex_and_pdf_agree(self):
        assert _tables.substitute(DRAFT, "latex") == _tables.substitute(DRAFT, "pdf")


class TestSubstituteMarkdown:
    def test_the_caption_becomes_a_numbered_paragraph(self):
        # `--format md` never reaches pandoc (docs/RENDERING-FLOW.md), so a
        # pandoc caption line would land verbatim in content/rendered/ as
        # a stray colon. A bold paragraph is what reads as a caption
        # everywhere Markdown is read.
        out = _tables.substitute(DRAFT, "md")
        assert "**Table 1:** Where to start when building a first twin." in out
        assert "**Table 2:** What each retention tier costs." in out
        assert ": Where to start" not in out
        assert "<!-- table:" not in out

    def test_references_carry_the_literal_number(self):
        out = _tables.substitute(DRAFT, "md")
        assert "The platforms in Table 1 differ" in out
        assert "and Table 2 prices it" in out


class TestADraftThatReusesAnId:
    """A collision `warnings` reports and `substitute` still has to render.

    Numbering by id rather than by position would give the *first* table
    the second one's number, so a draft with a duplicate id would carry
    two "Table 2"s and no "Table 1".
    """

    def test_captions_are_still_numbered_by_position(self):
        out = _tables.substitute(DRAFT + DRAFT, "md")
        assert out.count("**Table 1:**") == 1
        assert [line for line in out.splitlines() if line.startswith("**Table")][:3] == [
            "**Table 1:** Where to start when building a first twin.",
            "**Table 2:** What each retention tier costs.",
            "**Table 3:** Where to start when building a first twin.",
        ]


class TestSubstituteOtherPandocFormats:
    def test_docx_keeps_a_caption_and_gets_a_literal_number(self):
        # Verified against pandoc 3.1.11.1: the docx writer emits the
        # caption text and numbers nothing, so the number has to be in the
        # text handed to it.
        out = _tables.substitute(DRAFT, "docx")
        assert ": Table 1: Where to start when building a first twin." in out
        assert "The platforms in Table 1 differ" in out

    def test_html_is_treated_the_same_way_as_docx(self):
        assert _tables.substitute(DRAFT, "html") == _tables.substitute(DRAFT, "docx")


class TestSubstituteLeavesAlone:
    def test_a_latex_fragment_is_untouched(self):
        # thesis-chapter-writer writes a real \\begin{table} with its own
        # \\caption and \\label -- WRITING-STANDARDS.md §13's carve-out.
        fragment = (
            "See Table~\\ref{tab:start}.\n\n"
            "\\begin{table}\n\\caption{Where to start.}\\label{tab:start}\n"
            "\\begin{tabular}{ll}A & B\\\\\\end{tabular}\n\\end{table}\n"
        )
        assert _tables.substitute(fragment, "pdf") == fragment

    def test_an_unknown_reference_is_left_in_place(self):
        # Substituting nothing for it would delete a noun phrase from the
        # sentence; leaving the marker keeps the defect visible, and
        # `warnings` reports it.
        text = "As <!-- tableref: nowhere --> shows.\n"
        assert _tables.substitute(text, "md") == text


class TestWarnings:
    def test_a_table_with_no_caption_above_its_marker(self):
        text = "| A |\n|---|\n| 1 |\n\n<!-- table: bare -->\n"
        assert _tables.warnings(text) == [
            "`bare` has no caption line above its marker, so nothing numbers it"
        ]

    def test_a_reference_to_an_id_no_table_declares(self):
        assert _tables.warnings(DRAFT + "\nAlso <!-- tableref: ghost -->.\n") == [
            "`ghost` is referred to but no table declares it"
        ]

    def test_two_tables_claiming_one_id(self):
        found = _tables.warnings(DRAFT + DRAFT)
        assert "`costs` is declared by more than one table" in found
        assert "`start-here` is declared by more than one table" in found

    def test_a_clean_draft_warns_about_nothing(self):
        assert _tables.warnings(DRAFT) == []


class TestRenderIntegration:
    def test_the_markdown_path_numbers_the_caption(self, tmp_path, monkeypatch):
        # The one path that never reaches pandoc still has to produce a
        # numbered table, which is half of what issue 395 asks for.
        from chitragupta import config

        content = tmp_path / "content"
        drafts = content / "drafts"
        drafts.mkdir(parents=True)
        monkeypatch.setattr(config, "CONTENT_DIR", content)
        monkeypatch.setattr(config, "DRAFTS_DIR", drafts)
        monkeypatch.setattr(config, "RENDERED_DIR", content / "rendered")
        draft = drafts / "survey.md"
        draft.write_text(DRAFT, encoding="utf-8")

        out = render_output.render(str(draft), output_format="md")

        rendered = out.read_text(encoding="utf-8")
        assert "**Table 1:** Where to start when building a first twin." in rendered
        assert "The platforms in Table 1 differ" in rendered

    def test_a_marker_problem_is_reported_on_the_markdown_path(self, tmp_path, monkeypatch, capsys):
        from chitragupta import config

        content = tmp_path / "content"
        drafts = content / "drafts"
        drafts.mkdir(parents=True)
        monkeypatch.setattr(config, "CONTENT_DIR", content)
        monkeypatch.setattr(config, "DRAFTS_DIR", drafts)
        monkeypatch.setattr(config, "RENDERED_DIR", content / "rendered")
        draft = drafts / "survey.md"
        draft.write_text("| A |\n|---|\n| 1 |\n\n<!-- table: bare -->\n", encoding="utf-8")

        render_output.render(str(draft), output_format="md")

        assert "[table] `bare` has no caption line" in capsys.readouterr().err
