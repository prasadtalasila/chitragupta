"""Collecting the TikZ libraries a draft's figures ask for (#781).

Every test here reads figure *source* and compiles nothing, which is what
keeps them running on a host with no TeX Live -- the real-compile side of
the same fix is `tests/test_tikz_library_scope.py`, which skips there.
"""

from chitragupta.render_output import _tikz_libraries as tl


class TestLibrariesIn:
    def test_one_name(self):
        assert tl.libraries_in(r"\usetikzlibrary{positioning}") == ["positioning"]

    def test_a_comma_list_with_spaces(self):
        assert tl.libraries_in(r"\usetikzlibrary{positioning, fit}") == [
            "positioning",
            "fit",
        ]

    def test_a_dotted_name(self):
        assert tl.libraries_in(r"\usetikzlibrary{arrows.meta}") == ["arrows.meta"]

    def test_several_lines(self):
        source = "\\usetikzlibrary{positioning}\n\\usetikzlibrary{fit}\n"
        assert tl.libraries_in(source) == ["positioning", "fit"]

    def test_a_repeat_is_named_once(self):
        source = "\\usetikzlibrary{fit}\n\\usetikzlibrary{fit}\n"
        assert tl.libraries_in(source) == ["fit"]

    def test_a_commented_out_load_is_not_collected(self):
        # A commented load is inert in TeX, so collecting it would put a
        # library in the preamble the figure does not use -- and, if it
        # is misspelled, fail the whole render over a comment.
        assert tl.libraries_in("% \\usetikzlibrary{positioning}") == []

    def test_an_escaped_percent_does_not_start_a_comment(self):
        source = r"\draw (0,0) node {50\%}; \usetikzlibrary{fit}"
        assert tl.libraries_in(source) == ["fit"]

    def test_an_empty_call_yields_nothing(self):
        # `\usetikzlibrary{}` is fatal in TeX; it must not become an
        # empty name that we then re-emit.
        assert tl.libraries_in(r"\usetikzlibrary{}") == []

    def test_a_figure_with_no_load(self):
        assert tl.libraries_in(r"\begin{tikzpicture}\end{tikzpicture}") == []


class TestLibraryUnion:
    def _figure(self, tmp_path, name, body):
        path = tmp_path / "figures" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        return path

    def test_union_over_two_figures(self, tmp_path):
        self._figure(tmp_path, "a.tex", r"\usetikzlibrary{positioning}")
        self._figure(tmp_path, "b.tex", r"\usetikzlibrary{fit,positioning}")
        assert tl.library_union(["figures/a.tex", "figures/b.tex"], tmp_path) == [
            "fit",
            "positioning",
        ]

    def test_the_result_is_sorted(self, tmp_path):
        # Sorted rather than first-seen: a set iterates in hash order,
        # Python randomises string hashing per process, and this string
        # lands in the preamble of every render.
        self._figure(tmp_path, "a.tex", r"\usetikzlibrary{positioning,arrows.meta,fit}")
        assert tl.library_union(["figures/a.tex"], tmp_path) == [
            "arrows.meta",
            "fit",
            "positioning",
        ]

    def test_a_missing_figure_is_skipped(self, tmp_path):
        # `_figure_warnings` is what tells the user about a missing
        # figure; this must not be a second, fatal report of the same
        # thing.
        assert tl.library_union(["figures/absent.tex"], tmp_path) == []

    def test_an_escaping_reference_is_not_read(self, tmp_path):
        # `_resolve_sibling`'s rule: a draft's own text is never a reason
        # to read outside its directory.
        assert tl.library_union(["../secrets.tex"], tmp_path) == []

    def test_no_figures_at_all(self, tmp_path):
        assert tl.library_union([], tmp_path) == []

    def test_unreadable_bytes_do_not_stop_the_render(self, tmp_path):
        path = tmp_path / "figures" / "bad.tex"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"\\usetikzlibrary{fit}\n\xff\xfe")
        assert tl.library_union(["figures/bad.tex"], tmp_path) == ["fit"]


class TestHeaderInclude:
    def test_no_library_loads_tikz_alone(self):
        # `\usetikzlibrary{}` fails fatally on the comma list rather than
        # skipping, so an empty union must emit no call at all.
        assert tl.header_include([]) == r"\usepackage{tikz}"

    def test_libraries_follow_the_package(self):
        # Order is load-bearing: \usetikzlibrary needs tikz loaded.
        assert tl.header_include(["fit", "positioning"]) == (
            r"\usepackage{tikz}\usetikzlibrary{fit,positioning}"
        )


class TestStripComments:
    """Moved here from `review/figure_layout/_source.py`, which now
    imports it -- the dependency runs review -> render_output and never
    back, and the preamble collector needs the same stripper."""

    def test_a_comment_goes(self):
        assert tl.strip_comments("\\node (a) {A}; % a note\n") == "\\node (a) {A}; \n"

    def test_an_escaped_percent_stays(self):
        assert tl.strip_comments(r"{50\% done}") == r"{50\% done}"

    def test_the_review_layer_still_exports_it(self):
        from chitragupta.review.figure_layout import _source

        assert _source.strip_comments is tl.strip_comments
