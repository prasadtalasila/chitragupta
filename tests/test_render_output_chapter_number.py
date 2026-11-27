from chitragupta import render_output
from chitragupta.render_output import _chapter_number


class TestUnnumbered:
    def test_a_markdown_heading_loses_the_prefix_it_states_itself(self):
        text = "# Chapter 1: Why Anyone Pays\n\nBody.\n"

        assert _chapter_number.unnumbered(text) == "# Why Anyone Pays\n\nBody.\n"

    def test_the_outlines_own_dash_spelling_is_dropped_too(self):
        text = "# Chapter 2 -- First Meeting\n\nBody.\n"

        assert _chapter_number.unnumbered(text) == "# First Meeting\n\nBody.\n"

    def test_a_latex_fragments_chapter_loses_it_as_well(self):
        text = "\\chapter{Chapter 1. Why Anyone Pays}\n\nBody.\n"

        assert _chapter_number.unnumbered(text) == "\\chapter{Why Anyone Pays}\n\nBody.\n"

    def test_an_appendix_loses_the_letter_it_states_itself(self):
        text = "# Appendix A: The Mathematics You Need\n\nBody.\n"

        assert _chapter_number.unnumbered(text) == "# The Mathematics You Need\n\nBody.\n"
        assert _chapter_number.unnumbered("\\chapter{Appendix B -- Proofs}\n", latex=True) == (
            "\\chapter{Proofs}\n"
        )
        untouched = "# Appendix Alpha: Notes\n\n# Appendices and Errata\n"
        assert _chapter_number.unnumbered(untouched) == untouched

    def test_a_title_that_merely_begins_with_the_word_is_untouched(self):
        text = "# Chapters and Verses\n\n\\chapter{Chapters and Verses}\n"

        assert _chapter_number.unnumbered(text) == text

    def test_a_heading_inside_a_fenced_block_is_a_code_sample(self):
        text = "# Chapter 1: Real\n\n```markdown\n# Chapter 1: Shown\n```\n"

        assert _chapter_number.unnumbered(text) == (
            "# Real\n\n```markdown\n# Chapter 1: Shown\n```\n"
        )

    def test_a_latex_verbatim_is_left_alone_too(self):
        text = "\\chapter{Chapter 1: Real}\n\\begin{verbatim}\n\\chapter{Chapter 9: Shown}\n"
        text += "\\end{verbatim}\n"

        out = _chapter_number.unnumbered(text, True)

        assert "\\chapter{Real}" in out
        assert "\\chapter{Chapter 9: Shown}" in out

    def test_a_section_heading_keeps_its_own_numbering(self):
        text = "## 1.0 Before you start\n\n### Chapter 3: Not a chapter here\n"

        assert _chapter_number.unnumbered(text) == text


class TestSubstituted:
    def test_a_fragment_render_drops_the_prefix(self, tmp_path):
        draft = tmp_path / "unit.md"
        text = "# Chapter 1: Why Anyone Pays\n\nBody.\n"
        draft.write_text(text, encoding="utf-8")

        assert "# Why Anyone Pays" in render_output._substituted(text, draft, "tex", {}, True)

    def test_a_standalone_render_keeps_it(self, tmp_path):
        draft = tmp_path / "unit.md"
        text = "# Chapter 1: Why Anyone Pays\n\nBody.\n"
        draft.write_text(text, encoding="utf-8")

        assert "# Chapter 1: Why Anyone Pays" in render_output._substituted(text, draft, "tex", {})
