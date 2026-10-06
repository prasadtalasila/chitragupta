"""The one TeX comment stripper every figure-source reader shares."""

from chitragupta import _tex_comments
from chitragupta.render_output import _tikz_libraries


class TestStripComments:
    def test_a_comment_goes_and_the_line_break_stays(self):
        assert _tex_comments.strip_comments("a % note\nb\n") == "a \nb\n"

    def test_an_escaped_percent_is_text(self):
        assert _tex_comments.strip_comments(r"50\% done") == r"50\% done"

    def test_the_renderer_still_exports_the_same_function(self):
        assert _tikz_libraries.strip_comments is _tex_comments.strip_comments
