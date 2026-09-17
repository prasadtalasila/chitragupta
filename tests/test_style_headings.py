"""`chitragupta.ChapterSelfNumbered`, the one heading finding (#804).

The check exists for the residue the render-time repair cannot reach. A
unit already drafted as `.tex` needs no conversion to be assembled, so
`book-assembler` `\\input`s it as written -- no `--fragment` render runs
over it, and a `\\chapter{Chapter 1: ...}` in that file is numbered twice
by the enclosing document with nothing in between to drop the prefix.

Markdown drafts are deliberately silent, the same asymmetry
`style_typeset.findings` documents from the other side: there the fix is
the author's because the pipeline cannot reach the fragment's preamble,
and here it is the pipeline's because composition already drops it.
"""

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
        """One pattern, shared with the render-time repair, so a heading
        this reports is a heading that repair would have dropped -- a
        finding whose named fix does not fire is worse than no finding."""
        draft = tex_with(
            "\\chapter{Chapter 2 -- First Meeting}\n\\chapter{Chapter 3. Second Meeting}\n",
            tmp_path,
        )

        assert rules(style_headings.findings(draft)) == [
            "chitragupta.ChapterSelfNumbered",
            "chitragupta.ChapterSelfNumbered",
        ]

    def test_a_title_that_merely_begins_with_the_word_is_not_reported(self, tmp_path):
        draft = tex_with("\\chapter{Chapters and Verses}\n", tmp_path)

        assert style_headings.findings(draft) == []

    def test_a_starred_chapter_with_a_short_title_is_read_too(self, tmp_path):
        """`\\chapter*{}` and `\\chapter[short]{}` are the two spellings a
        hand-written `.tex` unit uses that pandoc never emits, and both
        collide with the enclosing document exactly as the plain one
        does -- the starred one against a hand-added contents line."""
        draft = tex_with("\\chapter[Pays]{Chapter 1: Why Anyone Pays}\n", tmp_path)

        assert rules(style_headings.findings(draft)) == ["chitragupta.ChapterSelfNumbered"]

    def test_a_title_wrapped_across_lines_is_quoted_as_one_line(self, tmp_path):
        """Measured on a real book's `.tex` unit, whose `\\chapter{}` title
        wraps over three lines. `style_report.py` prints a finding as one
        column of a fixed-width line, so a raw title breaks the report it
        is meant to be read in -- and the review agenda's summary, built
        from the same string."""
        draft = tex_with("\\chapter{Chapter 4 -- Just Enough\nModelling: Models}\n", tmp_path)

        found = style_headings.findings(draft)

        assert found[0]["match"] == "Chapter 4 -- Just Enough Modelling: Models"
        assert "\n" not in found[0]["message"]

    def test_a_chapter_shown_inside_a_verbatim_is_not_a_heading(self, tmp_path):
        """The same blanking the render-time repair does, for the same
        reason: a `\\chapter{}` in a `verbatim` is a sample shown to the
        reader, and a finding about one names a heading the document does
        not have."""
        draft = tex_with(
            "\\begin{verbatim}\n\\chapter{Chapter 9: Shown}\n\\end{verbatim}\n", tmp_path
        )

        assert style_headings.findings(draft) == []

    def test_a_markdown_draft_is_not_read_at_all(self, tmp_path):
        """Composition drops the prefix for a Markdown unit, so there is
        nothing left to repair -- and a `prose` finding is unattended by
        class, so reporting one would authorise `agenda-reviser` to edit
        an authored heading that is doing its job in the standalone
        render."""
        draft = tmp_path / "unit.md"
        draft.write_text("# Chapter 1: Why Anyone Pays\n\nBody.\n", encoding="utf-8")

        assert style_headings.findings(draft) == []
