from pathlib import Path

from chitragupta import style_headings


def rules(found: "list[dict]") -> "list[str]":
    return [finding["rule"] for finding in found]


def tex_with(body: str, tmp_path: Path) -> Path:
    draft = tmp_path / "unit.tex"
    draft.write_text(body, encoding="utf-8")
    return draft


class TestChapterSelfNumbered:
    def test_a_chapter_stating_its_own_number_is_reported(self, tmp_path):
        draft = tex_with("\\chapter{Chapter 1: Why Anyone Pays}\n\nBody.\n", tmp_path)

        found = style_headings.findings(draft)

        assert rules(found) == ["chitragupta.ChapterSelfNumbered"]
        assert found[0]["line"] == 1
        assert found[0]["match"] == "Chapter 1: Why Anyone Pays"

    def test_the_dash_and_stop_spellings_are_reported_too(self, tmp_path):
        draft = tex_with(
            "\\chapter{Chapter 2 -- First Meeting}\n\\chapter{Chapter 3. Second Meeting}\n",
            tmp_path,
        )

        assert rules(style_headings.findings(draft)) == [
            "chitragupta.ChapterSelfNumbered",
            "chitragupta.ChapterSelfNumbered",
        ]

    def test_an_appendix_stating_its_own_letter_is_reported(self, tmp_path):
        draft = tex_with("\\chapter{Appendix A: The Mathematics You Need}\n", tmp_path)

        found = style_headings.findings(draft)

        assert rules(found) == ["chitragupta.ChapterSelfNumbered"]
        assert "appendix letter" in found[0]["message"]

    def test_a_title_that_merely_begins_with_the_word_is_not_reported(self, tmp_path):
        draft = tex_with("\\chapter{Chapters and Verses}\n", tmp_path)

        assert style_headings.findings(draft) == []

    def test_a_starred_chapter_with_a_short_title_is_read_too(self, tmp_path):
        draft = tex_with("\\chapter[Pays]{Chapter 1: Why Anyone Pays}\n", tmp_path)

        assert rules(style_headings.findings(draft)) == ["chitragupta.ChapterSelfNumbered"]

    def test_a_title_wrapped_across_lines_is_quoted_as_one_line(self, tmp_path):
        draft = tex_with("\\chapter{Chapter 4 -- Just Enough\nModelling: Models}\n", tmp_path)

        found = style_headings.findings(draft)

        assert found[0]["match"] == "Chapter 4 -- Just Enough Modelling: Models"
        assert "\n" not in found[0]["message"]

    def test_a_chapter_shown_inside_a_verbatim_is_not_a_heading(self, tmp_path):
        draft = tex_with(
            "\\begin{verbatim}\n\\chapter{Chapter 9: Shown}\n\\end{verbatim}\n", tmp_path
        )

        assert style_headings.findings(draft) == []

    def test_a_markdown_draft_is_not_read_at_all(self, tmp_path):
        draft = tmp_path / "unit.md"
        draft.write_text("# Chapter 1: Why Anyone Pays\n\nBody.\n", encoding="utf-8")

        assert style_headings.findings(draft) == []
