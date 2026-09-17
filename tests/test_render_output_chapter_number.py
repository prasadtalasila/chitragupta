"""A chapter number an authored heading states for itself (#804).

The symptom these reproduce is a book that prints the number twice --
`Chapter 1` from the `book` class, then `Chapter 1: Why Anyone Pays` from
the unit's own heading, with the table of contents reading `1 Chapter 1:
...` to match. Neither half is a defect on its own, which is why the
repair is at composition: `--fragment` converts the authored heading
faithfully and the class numbers chapters, exactly as both document.

Written against the copy the writer sees rather than against a built pdf,
because that is where the fix lives -- `_substituted` is the one answer
to "what does the writer actually see", and the assembled pdf's table of
contents is the end-to-end check, run by hand against the real book.
"""

from chitragupta import render_output
from chitragupta.render_output import _chapter_number


class TestUnnumbered:
    """The pure text rewrite, both spellings of a chapter heading."""

    def test_a_markdown_heading_loses_the_prefix_it_states_itself(self):
        text = "# Chapter 1: Why Anyone Pays\n\nBody.\n"

        assert _chapter_number.unnumbered(text) == "# Why Anyone Pays\n\nBody.\n"

    def test_the_outlines_own_dash_spelling_is_dropped_too(self):
        """`spec init`'s skeleton writes `### Chapter 1 -- Title`, so an
        author copying the outline's own shape into a unit heading hits
        this spelling rather than the colon one."""
        text = "# Chapter 2 -- First Meeting\n\nBody.\n"

        assert _chapter_number.unnumbered(text) == "# First Meeting\n\nBody.\n"

    def test_a_latex_fragments_chapter_loses_it_as_well(self):
        """A `.tex` draft reaches `render(fragment=True)` the same way a
        Markdown one does, and pandoc passes `\\chapter{}` through
        unchanged, so a Markdown-only rewrite would leave the duplication
        standing on exactly the drafts nothing else can repair."""
        text = "\\chapter{Chapter 1. Why Anyone Pays}\n\nBody.\n"

        assert _chapter_number.unnumbered(text) == "\\chapter{Why Anyone Pays}\n\nBody.\n"

    def test_a_title_that_merely_begins_with_the_word_is_untouched(self):
        """The pattern fires on a heading that *already states a number*,
        which is the whole of the duplicating case. A title beginning with
        the word and nothing else is an ordinary title."""
        text = "# Chapters and Verses\n\n\\chapter{Chapters and Verses}\n"

        assert _chapter_number.unnumbered(text) == text

    def test_a_heading_inside_a_fenced_block_is_a_code_sample(self):
        """A fenced block holding a line that looks like a heading is a
        sample being shown to the reader -- a shell comment, or a
        Markdown example in a book about writing books. Rewriting one
        would corrupt the sample, silently, in the rendered book."""
        text = "# Chapter 1: Real\n\n```markdown\n# Chapter 1: Shown\n```\n"

        assert _chapter_number.unnumbered(text) == (
            "# Real\n\n```markdown\n# Chapter 1: Shown\n```\n"
        )

    def test_a_latex_verbatim_is_left_alone_too(self):
        """`latex=True` is the `.tex` draft's blanking: in LaTeX a
        backtick is an open-quote character rather than code markup, so
        the Markdown rules would blank the span between two quoted
        phrases and hide a real heading inside it."""
        text = "\\chapter{Chapter 1: Real}\n\\begin{verbatim}\n\\chapter{Chapter 9: Shown}\n"
        text += "\\end{verbatim}\n"

        out = _chapter_number.unnumbered(text, True)

        assert "\\chapter{Real}" in out
        assert "\\chapter{Chapter 9: Shown}" in out

    def test_a_section_heading_keeps_its_own_numbering(self):
        """Self-numbered *sections* are the other, older clash, and its
        remedy is `\\setcounter{secnumdepth}{-2}` in the book's authored
        preamble -- a document-level decision this must not pre-empt by
        rewriting a `##` heading behind the author's back."""
        text = "## 1.0 Before you start\n\n### Chapter 3: Not a chapter here\n"

        assert _chapter_number.unnumbered(text) == text


class TestSubstituted:
    """Where the rewrite rides, and the render that must not get it."""

    def test_a_fragment_render_drops_the_prefix(self, tmp_path):
        draft = tmp_path / "unit.md"
        text = "# Chapter 1: Why Anyone Pays\n\nBody.\n"
        draft.write_text(text, encoding="utf-8")

        assert "# Why Anyone Pays" in render_output._substituted(text, draft, "tex", {}, True)

    def test_a_standalone_render_keeps_it(self, tmp_path):
        """The prefix is load-bearing in the standalone render: nothing
        there supplies a chapter number, so the heading is the whole of
        the chapter's identity. Both artefacts ship, and they want
        opposite things from one authored line."""
        draft = tmp_path / "unit.md"
        text = "# Chapter 1: Why Anyone Pays\n\nBody.\n"
        draft.write_text(text, encoding="utf-8")

        assert "# Chapter 1: Why Anyone Pays" in render_output._substituted(text, draft, "tex", {})
