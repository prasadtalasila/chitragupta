"""Four valid TikZ spellings `figure check` misread (#1112): a node's name
after `at`, nodes made in a `\\foreach`, and a `(` or `;` in a tag's
text. The source readers are tested on every host; the loop needs the
drawing hook, so its case compiles and self-skips where TeX is missing.
"""

import pytest

from chitragupta import page
from chitragupta.figure import _check
from chitragupta.review.figure_layout import edge_list
from chitragupta.review.figure_layout._probe import node_names
from chitragupta.review.figure_layout._source import (
    ambiguous_edges,
    overlong_nodes,
    stranded_arrowheads,
)
from chitragupta.review.figure_layout._check_one import _expand_loops
from tests.conftest import needs_tikz
from tests.figure_drawn_fixtures import drawn, node


class TestNameAfterAt:
    def test_both_orders_declare_a_name(self):
        source = (
            "\\node[draw] (a) at (0,0) {alpha};\n"
            "\\node[draw] at (0,-2) (b) {beta};\n"
            "\\node at (0,-4) (c) {gamma};\n"
        )

        assert node_names(source) == ["a", "b", "c"]

    def test_a_calc_position_is_not_the_name(self):
        source = "\\node[draw] at ($(a)!0.5!(b)$) (m) {mid};\n"

        assert node_names(source) == ["m"]

    def test_an_unnamed_node_at_a_position_declares_nothing(self):
        assert node_names("\\node[draw] at (a.east) {x};\n") == []

    def test_a_two_tier_labels_gloss_counts_toward_its_words(self):
        """The whole braced label is read, so `\\cglab`'s gloss counts:
        the regex this replaced stopped at the title's `}` (#1112)."""
        gloss = " ".join(["word"] * 14)

        assert overlong_nodes(f"\\node (a) {{\\cglab{{One two}}{{{gloss}}}}};\n") == [("a", 16)]

    def test_an_overlong_label_is_counted_after_at(self):
        words = " ".join(["word"] * 16)

        assert overlong_nodes(f"\\node at (0,0) (b) {{{words}}};\n") == [("b", 16)]


class TestTagText:
    def test_parentheses_in_a_tag_are_not_a_node(self):
        source = "\\draw[cgedge] (a) -- node[cgtag] {0.1 (repaired)} (b);\n"

        assert edge_list(source) == [("a", "b")]

    def test_a_semicolon_in_a_tag_does_not_end_the_path(self):
        source = (
            "\\draw[cgedge] (plant) -- node[cgtag, align=left]"
            " {physical events in;\\\\actions out} (twin);\n"
        )

        assert edge_list(source) == [("plant", "twin")]

    def test_a_named_node_on_the_path_is_still_ambiguous(self):
        source = "\\draw (a) -- node (l) {x (y); z} (b);\n"

        assert ambiguous_edges(source) == [("a", "l"), ("l", "b")]

    def test_an_escaped_brace_does_not_swallow_the_rest(self):
        source = "\\draw (a) -- node {x} (b) \\{ ;\n\\draw (c) -- (d);\n"

        assert edge_list(source) == [("a", "b"), ("c", "d")]

    def test_an_arrow_in_a_tag_is_not_a_head(self):
        source = "\\draw (0,0) -- node {a -> b} (1,0);\n\\draw[->] (1,0) -- (2,0);\n"

        assert stranded_arrowheads(source) == []


class TestExpandLoops:
    """A macro-spelled name, against what the hook logged (no TeX)."""

    LOGGED = drawn(
        [
            node("s1", (0, 0, 10, 10)),
            node("s2", (0, 20, 10, 30)),
            node("a", (20, 0, 30, 10)),
            node("cgu-1", (40, 0, 50, 10)),
            node("tikz@f@1", (60, 0, 70, 10)),
            node("sink", (80, 0, 80, 0), shape="coordinate"),
        ],
        [],
    )

    def test_a_loop_name_becomes_the_nodes_it_drew(self):
        boxes = {"a": (20.0, 0.0, 30.0, 10.0)}

        declared = _expand_loops(["s\\i", "a"], boxes, self.LOGGED)

        assert declared == ["s1", "s2", "a"]
        assert boxes["s2"] == (0.0, 20.0, 10.0, 30.0)

    def test_a_name_with_no_literal_part_is_left_as_declared(self):
        boxes = {}

        assert _expand_loops(["\\i", "a"], boxes, self.LOGGED) == ["\\i", "a"]
        assert boxes == {}

    def test_a_name_matching_nothing_drawn_is_left_as_declared(self):
        assert _expand_loops(["t\\i"], {}, self.LOGGED) == ["t\\i"]


@pytest.mark.slow
@needs_tikz
def test_loop_made_nodes_are_measured_from_what_tikz_drew(tmp_path):
    path = tmp_path / "fig.tex"
    path.write_text(
        "\\begin{tikzpicture}\n"
        "\\foreach \\i/\\t in {1/alpha,2/beta,3/gamma} {\n"
        "  \\node[draw] (s\\i) at (0,-2*\\i) {\\t};\n"
        "}\n"
        "\\draw[->] (s1) -- (s2);\n"
        "\\draw[->] (s2) -- (s3);\n"
        "\\end{tikzpicture}%\n",
        encoding="utf-8",
    )

    result = _check.check(path, page.ARTICLE.text_width_pt)

    assert "nothing-measurable" not in [f.rule for f in result.findings]
    [budget] = [f for f in result.advisory if f.rule == "budget-nodes"]
    assert budget.measurement.startswith("3 nodes")
    assert not [why for rule, why in result.not_measured if "no measured node" in why]


@pytest.mark.slow
@needs_tikz
def test_a_loop_name_with_no_literal_part_stays_unmeasured(tmp_path):
    path = tmp_path / "fig.tex"
    path.write_text(
        "\\begin{tikzpicture}\n"
        "\\node[draw] (a) at (3,0) {A};\n"
        "\\foreach \\i in {1,2} { \\node[draw] (\\i) at (0,-\\i) {\\i}; }\n"
        "\\end{tikzpicture}%\n",
        encoding="utf-8",
    )

    result = _check.check(path, page.ARTICLE.text_width_pt)

    [budget] = [f for f in result.advisory if f.rule == "budget-nodes"]
    assert budget.measurement.startswith("2 nodes")
