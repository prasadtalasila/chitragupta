"""The wording rules `w1` to `w4` (#1055), read from a figure's source.

Must-not-fire cases are most of each class: a rule that fires on a
correct label teaches an author to stop reading it.
"""

from chitragupta.figure._wording import words, wording_rules


def _picture(*lines: str) -> str:
    return "\\begin{tikzpicture}[cg]\n" + "\n".join(lines) + "\n\\end{tikzpicture}%\n"


def _advisory(*lines: str) -> list[tuple[str, str, str]]:
    return [(f.rule, f.target, f.measurement) for f in wording_rules(_picture(*lines))[1]]


def _objective(*lines: str) -> list[tuple[str, str, str]]:
    return [(f.rule, f.target, f.measurement) for f in wording_rules(_picture(*lines))[0]]


def _named(name: str, gloss: str = "a gloss") -> str:
    return f"\\node[cgbox] (n) {{\\cglab{{{name}}}{{{gloss}}}}};"


class TestWords:
    def test_markup_is_not_a_word(self):
        assert [w.text for w in words("\\textbf{Feature}~store\\\\[-1pt]{\\small x}")] == [
            "Feature",
            "store",
            "x",
        ]

    def test_a_formula_is_one_word_and_never_case_read(self):
        found = words("state $x_k + 1$")

        assert [w.text for w in found] == ["state", "$x_k + 1$"]
        assert found[1].verbatim and not found[1].capitalised

    def test_texttt_is_kept_as_written(self):
        found = words("\\texttt{Pdf Run} now")

        assert [(w.text, w.verbatim) for w in found] == [
            ("Pdf", True),
            ("Run", True),
            ("now", False),
        ]

    def test_punctuation_alone_is_not_a_word(self):
        assert [w.text for w in words("in / out --- done")] == ["in", "out", "done"]


class TestW1Case:
    def test_sentence_case_passes(self):
        assert _advisory(_named("Feature store")) == []

    def test_a_proper_noun_in_a_mixed_name_passes(self):
        assert _advisory(_named("Extended Kalman filter")) == []

    def test_an_acronym_is_not_a_capitalised_word(self):
        assert _advisory(_named("RAG Pipeline")) == [
            (
                "w1-case",
                '"RAG Pipeline"',
                "Title Case; sentence case capitalises only the first word",
            )
        ]
        assert _advisory(_named("Query PDFs")) == []

    def test_a_short_word_does_not_make_title_case(self):
        assert _advisory(_named("Data and model")) == []

    def test_title_case_is_reported(self):
        assert [f[0] for f in _advisory(_named("Feature Store Index"))] == ["w1-case"]

    def test_a_lower_case_start_is_reported(self):
        assert _advisory(_named("feature store")) == [
            ("w1-case", '"feature store"', "starts lower-case; sentence case capitalises it")
        ]

    def test_a_program_name_may_start_lower_case(self):
        assert _advisory(_named("pdflatex run")) == []
        assert _advisory(_named("\\texttt{latexmk} pass")) == []

    def test_a_name_with_no_words_passes(self):
        assert _advisory(_named("$x$")) == []
        assert _advisory(_named("")) == []

    def test_only_cglab_names_are_read(self):
        """A box broken by hand may be one phrase wrapped (*user*)."""
        assert _advisory("\\node[draw] (n) {physical twin\\\\pot, pump};") == []

    def test_the_cglab_definition_is_not_a_name(self):
        assert _advisory("\\providecommand{\\cglab}[2]{x}\\newcommand{\\lab}{\\cglab{#1}{#2}}") == []


class TestW3Gloss:
    def test_six_words_pass(self):
        assert _advisory(_named("Store", "holds one vector per chunk here")) == []

    def test_seven_words_are_reported(self):
        assert _advisory(_named("Store", "holds every vector computed so far today")) == [
            (
                "w3-gloss",
                '"Store"',
                '"holds every vector computed so far today": 7 words, over 6',
            )
        ]

    def test_a_formula_counts_once(self):
        assert _advisory(_named("Step", "nudge the state by $K (z - Hx)$ now")) == []


class TestW2Tag:
    def test_a_short_lower_case_tag_passes(self):
        assert _advisory("\\draw[cgedge] (a) -- node[cgtag] {sends raw reading} (b);") == []

    def test_a_long_capitalised_tag_is_reported(self):
        assert _advisory("\\draw (a) -| node {Sends The Raw Reading} (b);") == [
            (
                "w2-tag",
                'tag "Sends The Raw Reading"',
                "4 words, over 3; capitalised; a tag is lower-case",
            )
        ]

    def test_an_acronym_in_a_tag_passes(self):
        assert _advisory("\\draw (a) to node {via HTTP} (b);") == []

    def test_an_edge_operation_tag_is_read(self):
        assert [f[0] for f in _advisory("\\path (a) edge node {Go} (b);")] == ["w2-tag"]

    def test_a_note_by_its_own_node_is_not_a_tag(self):
        assert _advisory("\\node[cgnote] at (1,1) {A Long Note Beside The Line};") == []

    def test_a_label_on_a_path_that_joins_nothing_is_not_a_tag(self):
        assert _advisory("\\draw (0,0) node {Origin Point Here Now};") == []

    def test_node_distance_is_not_a_node(self):
        assert _advisory("\\draw[node distance=6mm] (a) -- (b) {Not A Label At All};") == []


class TestW4Pictograph:
    def test_a_check_mark_in_a_label_is_reported(self):
        assert _objective("\\node (ok) {✓ pass};") == [
            ("w4-pictograph", "ok", '"✓" (U+2713) in the label')
        ]

    def test_an_emoji_with_its_selector_is_reported_once_each(self):
        """An unnamed node is shown by its words, which a pictograph is not."""
        found = _objective("\\node {go ❤️ ❤️};")

        assert found == [("w4-pictograph", '"go"', '"❤" (U+2764), "️" (U+FE0F) in the label')]

    def test_typography_and_icon_commands_pass(self):
        assert _objective("\\node (a) {in → out © ™ $\\leq$ \\ding{51}};") == []

    def test_one_outside_any_label_is_the_figures(self):
        found = _objective("\\cgzonelabel{z}{cgAlt}{🚀 launch}")

        assert found == [("w4-pictograph", "figure", '"🚀" (U+1F680) outside any node\'s label')]

    def test_one_in_a_comment_is_not_read(self):
        assert _objective("\\node (a) {x}; % ✓ done") == []
