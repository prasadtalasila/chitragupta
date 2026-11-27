import ast
from pathlib import Path

import pytest

from chitragupta import config, render_output
from chitragupta.render_output import _math, _math_findings, _math_shapes


MAPPING = """\
| ASCII in the draft | LaTeX |
| --- | --- |
| `W` | `W` |
| `tau` | `\\tau` |
| `tau = 48` | `\\tau = 48` |
| `W0 = 400` | `W_0 = 400` |
| `dW/dt = -W/tau` | `\\frac{dW}{dt} = -\\frac{W}{\\tau}` |
"""

ASCII_DRAFT = """\
# Draining the tank

Writing `W` for the water present and `tau` for that constant, the model is:

<!-- math -->
```
dW/dt = -W/tau
```

Fitted, `tau = 48` hours, from `W0 = 400` ml. The field `as_of` is code.
"""

DOLLAR_DRAFT = """\
# Draining the tank

Writing $W$ for the water present and $\\tau$ for that constant, the model is:

$$
\\frac{dW}{dt} = -\\frac{W}{\\tau}
$$

Fitted, $\\tau = 48$ hours, from $W_0 = 400$ ml. The field `as_of` is code.
"""


def _draft(mapping: "str | None" = MAPPING, text: str = ASCII_DRAFT) -> Path:
    draft = config.DRAFTS_DIR / "dt" / "tank.md"
    draft.parent.mkdir(parents=True, exist_ok=True)
    draft.write_text(text, encoding="utf-8")
    if mapping is not None:
        dossier = config.DOSSIERS_DIR / "dt" / "tank"
        dossier.mkdir(parents=True, exist_ok=True)
        (dossier / "math.md").write_text(mapping, encoding="utf-8")
    return draft


class TestMappingPath:
    def test_mirrors_the_drafts_path_into_dossiers(self, isolated_config):
        draft = config.DRAFTS_DIR / "dt" / "tank.md"
        assert _math.mapping_path(draft) == config.DOSSIERS_DIR / "dt" / "tank" / "math.md"

    def test_a_draft_outside_drafts_dir_can_have_no_mapping(self, isolated_config):
        assert _math.mapping_path(config.REVIEW_DIR / "report.md") is None

    def test_a_symlinked_topic_directory_out_of_the_tree_is_refused(
        self, isolated_config, tmp_path
    ):
        outside = tmp_path / "elsewhere"
        outside.mkdir()
        config.DOSSIERS_DIR.mkdir(parents=True, exist_ok=True)
        (config.DOSSIERS_DIR / "dt").symlink_to(outside, target_is_directory=True)
        assert _math.mapping_path(config.DRAFTS_DIR / "dt" / "tank.md") is None


class TestLoadMapping:
    def test_reads_every_row(self, isolated_config):
        mapping = _math.load_mapping(_draft())
        assert mapping["tau"] == "\\tau"
        assert mapping["dW/dt = -W/tau"] == "\\frac{dW}{dt} = -\\frac{W}{\\tau}"
        assert len(mapping) == 5

    def test_absent_file_is_an_empty_mapping_not_an_error(self, isolated_config):
        assert _math.load_mapping(_draft(mapping=None)) == {}

    def test_a_draft_with_no_possible_mapping_is_empty(self, isolated_config):
        assert _math.load_mapping(config.REVIEW_DIR / "report.md") == {}

    def test_the_header_row_is_not_a_mapping_row(self, isolated_config):
        assert "ASCII in the draft" not in _math.load_mapping(_draft())


class TestSubstitute:
    def test_a_mapped_span_becomes_inline_math(self, isolated_config):
        out = _math.substitute("the gain `tau` here", {"tau": "\\tau"})
        assert out == "the gain $\\tau$ here"

    def test_an_unmapped_span_is_left_alone(self, isolated_config):
        assert _math.substitute("field `as_of` here", {"tau": "\\tau"}) == "field `as_of` here"

    def test_a_marked_block_becomes_display_math(self, isolated_config):
        text = "<!-- math -->\n```\ndW/dt = -W/tau\n```\n"
        assert _math.substitute(text, {"dW/dt = -W/tau": "X"}) == "$$\nX\n$$\n"

    def test_an_unmarked_fence_is_never_touched(self, isolated_config):
        text = "```\ntau = 48\n```\n"
        assert _math.substitute(text, {"tau = 48": "\\tau = 48"}) == text

    def test_a_marked_block_with_no_row_is_left_alone(self, isolated_config):
        text = "<!-- math -->\n```\nunmapped\n```\n"
        assert _math.substitute(text, {}) == text

    def test_a_block_inside_a_blockquote_keeps_its_indent(self, isolated_config):
        text = "> <!-- math -->\n> ```\n> C x I > F\n> ```\n"
        out = _math.substitute(text, {"C x I > F": "C \\times I > F"})
        assert out == "> $$\n> C \\times I > F\n> $$\n"

    def test_blocks_substitute_before_spans(self, isolated_config):
        text = "<!-- math -->\n```\nW\n```\n"
        out = _math.substitute(text, {"W": "W_{\\text{tank}}", "\nW\n": "wrong"})
        assert out == "$$\nW_{\\text{tank}}\n$$\n"

    def test_a_double_backtick_span_is_not_a_span(self, isolated_config):
        assert _math.substitute("``tau``", {"tau": "\\tau"}) == "``tau``"

    def test_a_backtick_span_inside_an_ordinary_fence_is_not_touched(self, isolated_config):
        text = "```markdown\nThe gain is `tau` here.\n```\n"
        assert _math.substitute(text, {"tau": "\\tau"}) == text


class TestConvergesOnTheDollarConvention:
    def test_ascii_plus_mapping_equals_the_dollar_spelling(self, isolated_config):
        draft = _draft()
        substituted = _math.substitute(draft.read_text(encoding="utf-8"), _math.load_mapping(draft))
        assert substituted == DOLLAR_DRAFT


class TestWarnings:
    def test_a_math_shaped_span_with_no_row_is_a_gap(self, isolated_config):
        found = _math_findings.warnings("the value `h = 9` here", {}, False)
        assert found == ["`h = 9` looks like a quantity (relation) but has no row in math.md"]

    def test_a_bare_symbol_the_equations_use_is_a_gap(self, isolated_config):
        found = _math_findings.warnings("predicts `W` now", {"x": "W + 1"}, False)
        assert found == [
            "`W` is a symbol this draft's own equations use, but has no row in math.md"
        ]

    def test_a_greek_control_word_counts_as_a_symbol(self, isolated_config):
        found = _math_findings.warnings("the `tau` here", {"x": "\\tau + 1"}, False)
        assert "`tau` is a symbol" in found[0]

    def test_a_non_greek_control_word_is_not_a_symbol(self, isolated_config):
        assert _math_findings.warnings("the `frac` here", {"x": "\\frac{1}{2}"}, False) == []

    def test_a_plain_identifier_is_not_a_gap(self, isolated_config):
        assert _math_findings.warnings("field `as_of` here", {}, False) == []

    def test_a_citekey_is_never_a_gap(self, isolated_config):
        assert _math_findings.warnings("see `zech_digital-twins-as--service_2024`", {}, False) == []

    def test_a_mapped_span_is_not_a_gap(self, isolated_config):
        assert _math_findings.warnings("the `tau` here", {"tau": "\\tau"}, True) == []

    def test_a_row_matching_nothing_is_an_orphan(self, isolated_config):
        found = _math_findings.warnings("no maths here", {"tau": "\\tau"}, True)
        assert found == ["`tau` has a row in math.md but appears nowhere in the draft"]

    def test_a_row_used_only_in_a_block_is_not_an_orphan(self, isolated_config):
        text = "<!-- math -->\n```\ndW/dt\n```\n"
        assert _math_findings.warnings(text, {"dW/dt": "X"}, True) == []

    def test_orphans_are_not_reported_when_there_is_no_mapping_file(self, isolated_config):
        assert _math_findings.warnings("no maths here", {"tau": "\\tau"}, False) == []

    def test_a_span_inside_a_marked_block_is_not_scanned_as_inline(self, isolated_config):
        text = "<!-- math -->\n```\nh = 9\n```\n"
        assert _math_findings.warnings(text, {"h = 9": "h = 9"}, True) == []

    def test_a_span_inside_an_ordinary_fence_is_not_scanned_as_inline(self, isolated_config):
        text = "```markdown\nThe gain is `tau` here.\n```\n"
        assert _math_findings.warnings(text, {"x": "\\tau + 1"}, False) == []


class TestAnUnmarkedFenceHoldingAnEquation:
    def test_an_untagged_fence_holding_a_relation_is_a_gap(self, isolated_config):
        text = "> Call it `C`. Adopt when\n>\n> ```\n> C x I  >  F\n> ```\n>\n> where `I`\n"
        assert _math_findings.warnings(text, {}, False)[0] == (
            "`C x I  >  F` looks like a displayed equation but its fence has no "
            "`<!-- math -->` marker. Tag the fence if it is code."
        )

    def test_a_marked_fence_is_not_reported_as_unmarked(self, isolated_config):
        text = "<!-- math -->\n```\nC x I > F\n```\n"
        assert _math_findings.warnings(text, {"C x I > F": "C \\times I > F"}, True) == []

    def test_a_tagged_fence_is_code(self, isolated_config):
        text = "```python\nDRY_THRESHOLD = 35.0\n```\n"
        assert _math_findings.warnings(text, {}, False) == []

    def test_a_fence_of_program_output_is_code(self, isolated_config):
        text = "```\nhour 11  sensor= 38.2  predicted_next= 35.0\n```\n"
        assert _math_findings.warnings(text, {}, False) == []

    def test_a_fence_with_no_operator_in_it_is_not_an_equation(self, isolated_config):
        assert _math_findings.warnings("```\nchitragupta draft render\n```\n", {}, False) == []

    def test_an_ascii_figure_is_not_an_equation(self, isolated_config):
        figure = "\n".join(["+------+", "| twin | -> readings", "+------+", "", "|", "v"])
        assert _math_findings.warnings(f"```\n{figure}\n```\n", {}, False) == []

    def test_an_empty_fence_is_not_an_equation(self, isolated_config):
        assert _math_findings.warnings("```\n```\n", {}, False) == []

    def test_a_tagged_fence_does_not_hide_the_untagged_one_after_it(self, isolated_config):
        text = "```sql\nselect 1\n```\n\ntext\n\n```\nC x I > F\n```\n"
        assert _math_findings.warnings(text, {}, False) == [
            "`C x I > F` looks like a displayed equation but its fence has no "
            "`<!-- math -->` marker. Tag the fence if it is code."
        ]

    def test_the_first_line_names_a_multi_line_equation(self, isolated_config):
        text = "```\n-8 = -24k + g\ng = 24k - 8\n```\n"
        assert _math_findings.warnings(text, {}, False) == [
            "`-8 = -24k + g` looks like a displayed equation but its fence has no "
            "`<!-- math -->` marker. Tag the fence if it is code."
        ]


class TestCheckRefusesOnlyTheCertainCases:
    def test_a_marker_with_no_mapping_file_is_refused(self, isolated_config):
        draft = _draft(mapping=None)
        with pytest.raises(_math.MathMappingError, match="renamed or moved"):
            _math.check(draft.read_text(encoding="utf-8"), draft, {})

    def test_a_marker_with_no_row_is_refused(self, isolated_config):
        draft = _draft(mapping="| ASCII | LaTeX |\n| --- | --- |\n| `x` | `x` |\n")
        with pytest.raises(_math.MathMappingError, match="no row in math.md"):
            _math.check(draft.read_text(encoding="utf-8"), draft, {"x": "x"})

    def test_a_marker_with_no_fence_after_it_is_refused(self, isolated_config):
        draft = _draft(text="<!-- math -->\n\nprose, no fence\n")
        with pytest.raises(_math.MathMappingError, match="no fenced"):
            _math.check(draft.read_text(encoding="utf-8"), draft, {})

    def test_a_draft_with_no_markers_never_raises(self, isolated_config):
        draft = _draft(mapping=None, text="just `h = 9` inline, no display maths\n")
        _math.check(draft.read_text(encoding="utf-8"), draft, {})

    def test_a_resolved_marker_never_raises(self, isolated_config):
        draft = _draft()
        _math.check(draft.read_text(encoding="utf-8"), draft, _math.load_mapping(draft))

    def test_a_heuristic_gap_is_never_fatal(self, isolated_config):
        draft = _draft(mapping=None, text="a `h = 9` gap and nothing else\n")
        _math.check(draft.read_text(encoding="utf-8"), draft, {})


class TestCheckedMathMapping:
    def test_returns_the_mapping_and_prints_gaps_to_stderr(self, isolated_config, capsys):
        draft = _draft(text="a mapped `tau` and an unmapped `h = 9`\n")
        mapping = render_output._checked_math_mapping(draft.read_text(encoding="utf-8"), draft)
        assert mapping["tau"] == "\\tau"
        err = capsys.readouterr().err
        assert "[math] `h = 9` looks like a quantity" in err

    def test_a_clean_draft_says_nothing(self, isolated_config, capsys):
        draft = _draft(
            mapping="| ASCII | LaTeX |\n| --- | --- |\n| `tau` | `\\tau` |\n"
            "\n## Symbols\n\n| `tau` | time constant |\n",
            text="a mapped `tau` and the field `as_of`\n",
        )
        render_output._checked_math_mapping(draft.read_text(encoding="utf-8"), draft)
        assert "[math]" not in capsys.readouterr().err

    def test_it_raises_before_warning_on_an_unresolvable_marker(self, isolated_config):
        draft = _draft(mapping=None)
        with pytest.raises(_math.MathMappingError):
            render_output._checked_math_mapping(draft.read_text(encoding="utf-8"), draft)


class TestTheMarkdownPathLeavesTheAsciiAlone:
    def test_an_empty_mapping_changes_nothing(self):
        assert _math.substitute(ASCII_DRAFT, {}) == ASCII_DRAFT

    def test_the_md_render_keeps_backticked_quantities(self, isolated_config):
        draft = _draft()
        rendered = render_output.render(str(draft), output_format="md")
        text = rendered.read_text(encoding="utf-8")
        assert "`tau = 48`" in text and "```\ndW/dt = -W/tau\n```" in text
        assert "$" not in text


class TestImportBoundary:
    def test_imports_stay_inside_the_bare_python_set(self):
        allowed = {"chitragupta.config", "chitragupta.citation_gate", "chitragupta.references"}
        source = Path(_math.__file__).read_text(encoding="utf-8")
        self._assert_imports_within(source, allowed, "chitragupta.config", "_math.py")

    def test_the_shape_rules_import_only_math(self):
        source = Path(_math_shapes.__file__).read_text(encoding="utf-8")
        allowed = {"chitragupta.render_output._math"}
        self._assert_imports_within(
            source, allowed, "chitragupta.render_output._math", "_math_shapes.py"
        )

    @staticmethod
    def _assert_imports_within(source, allowed, expected, name):
        imported = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.update(
                    f"{node.module}.{a.name}" if node.module == "chitragupta" else node.module
                    for a in node.names
                )
        assert expected in imported, (
            "the import scan found no chitragupta imports at all, so it is not "
            f"checking anything -- has {name}'s import style changed?"
        )
        offenders = {n for n in imported if n.startswith("chitragupta")} - allowed
        assert offenders == set(), (
            f"{name} imports {offenders}, outside the set _paths.py commits this "
            "package to. Locate the dossier with config.mirrored_dir() instead."
        )

    def test_the_duplicated_path_rule_still_agrees_with_dossier_dir(self, isolated_config):
        from chitragupta import dossier

        draft = config.DRAFTS_DIR / "dt" / "tank.md"
        assert _math.mapping_path(draft) == dossier.dossier_dir(draft) / _math.MAPPING_FILENAME


class TestFindingsCarryTheirKind:
    def test_every_kind_is_reported_under_its_own_name(self, isolated_config):
        text = "the value `h = 9` and `W` here\n\n```\nC x I > F\n```\n"
        kinds = [
            found.kind for found in _math_findings.findings(text, {"tau": "\\tau", "x": "W"}, True)
        ]
        assert sorted(set(kinds)) == ["fence", "gap", "orphan", "symbol"]

    def test_warnings_is_findings_reduced_to_its_messages(self, isolated_config):
        text = "the value `h = 9` here"
        found = _math_findings.findings(text, {"tau": "\\tau"}, True)
        assert _math_findings.warnings(text, {"tau": "\\tau"}, True) == [f.message for f in found]

    def test_the_orphan_filter_survives_a_reworded_message(self, isolated_config, monkeypatch):
        from chitragupta.dossier import _draft_fingerprint

        monkeypatch.setattr(
            _math_findings,
            "findings",
            lambda text, mapping, found_file, **_: [
                _math_findings.MathFinding("gap", "`h = 9` looks like a quantity, no row"),
                _math_findings.MathFinding("orphan", "`tau` has a row but is unused"),
            ],
        )
        monkeypatch.setattr(_math, "load_mapping", lambda draft: {"tau": "\\tau"})
        monkeypatch.setattr(_math, "mapping_path", lambda draft: None)
        found = _draft_fingerprint._math_desync(Path("draft.md"), "no maths here")
        assert found == ["`tau` has a row but is unused"]


class TestShapeRules:
    @pytest.mark.parametrize(
        "span, rule",
        [
            ("h = 9", "relation"),
            ("3 - 1", "digit-op-digit"),
            ("-1", "signed-number"),
            ("-0.074", "signed-number"),
            ("[1 0]", "vector"),
            ("[120.0, 1.5]", "vector"),
            ("[118.5, 1.5]", "vector"),
            ("[1; -1]", "vector"),
            ("[a, b; c, d]", "matrix"),
            ("A * P_est * A^T + Q", "star-caret"),
            ("A^T", "star-caret"),
            ("t + h", "spaced-op"),
            ("a / b", "spaced-op"),
            ("dT/dt", "derivative"),
            ("d^2x/dt^2", "derivative"),
            ("dV/dSoC", "derivative"),
            ("P(A | B)", "conditional"),
            ("p(x_k | z_{1:k})", "conditional"),
            ("sigma_2", "greek-subscript"),
            ("Pi_ij", "greek-subscript"),
            ("mu_i", "greek-subscript"),
            ("T_k+1", "index-step"),
            ("x_{k+1}", "index-step"),
            ("1e-12", "sci-number"),
            ("1.44e6", "sci-number"),
            ("0, 3", "number-list"),
            ("0.65, 0.3, 0.05", "number-list"),
        ],
    )
    def test_each_rule_names_itself(self, span, rule):
        assert _math_shapes.rule_for(span, frozenset(), False) == rule

    @pytest.mark.parametrize(
        "span",
        [
            "-m",
            "--write",
            "Ctrl+C",
            "PI",
            "[DIGITAL MODEL]",
            "plant-1",
            "*.md",
            "12:30",
            "192.168.1.1",
            "as_of",
            "sleep(5)",
            "N(118.5, 9.25)",
            "pip install -e .",
            "noauthor_digital_nodate-1",
            "1,000",
            "[1]",
            "plant_id+1",
        ],
    )
    def test_near_misses_stay_code(self, span):
        assert _math_shapes.rule_for(span, frozenset(), False) is None


class TestNotMathematicsIsBlankedFirst:
    @pytest.mark.parametrize(
        "span",
        [
            "02-02-math-model-solution.md",
            "code/02-01-create-mock-physical-twin/",
            "/home/u/content/drafts/zz/02-01-s.md",
            "python -m chitragupta.review uncited /x/content/drafts/zz/02-01-s.md --write",
            "?limit=",
            "?since_timestamp=",
            "GET /sensing/plant_1/moisture?limit=1",
            "<unit>_<parameter>",
            "2026-02-01",
            "6.157.0",
            "fastapi-0.115.12",
        ],
    )
    def test_is_not_a_quantity(self, span):
        assert _math_shapes.rule_for(span, frozenset(), True) is None

    def test_a_relation_beside_a_file_name_still_is(self):
        assert _math_shapes.rule_for("x = 02-01-a.md", frozenset(), False) == "relation"

    def test_a_derivative_is_judged_before_it_could_be_blanked(self):
        assert _math_shapes.rule_for("dV/dSoC", frozenset(), False) == "derivative"


class TestTheDraftsOwnMathematics:
    def test_single_letters_bare_numbers_and_greek_need_a_mapping_file(self):
        for span, rule in (("t", "single-letter"), ("0.5", "bare-number"), ("Pi", "greek")):
            assert _math_shapes.rule_for(span, frozenset(), True) == rule
            assert _math_shapes.rule_for(span, frozenset(), False) is None

    def test_names_from_the_ascii_column_are_known(self):
        symbols = _math._symbols_of({"EC - EC_0": "x", "V_t = OCV(SoC) - R_0 * I": "y"})
        assert {"EC", "OCV", "SoC", "V", "R", "I"} <= symbols

    def test_lowercase_words_in_the_ascii_column_are_not_names(self):
        symbols = _math._symbols_of({"level + h * (pump_flow - demand) / area": "x"})
        assert "level" not in symbols and "demand" not in symbols and "h" in symbols

    @pytest.mark.parametrize(
        "span, rule",
        [
            ("SoC", "symbol"),
            ("EC_0", "symbol-built"),
            ("-k", "symbol-built"),
            ("OCV(SoC)", "symbol-built"),
            ("f(T_k)", "symbol-built"),
            ("N(mu, 9.25)", "symbol-built"),
            ("(A, B, C)", "symbol-built"),
        ],
    )
    def test_a_span_built_from_known_names(self, span, rule):
        symbols = frozenset({"SoC", "EC", "k", "OCV", "f", "T", "N", "mu", "A", "B", "C"})
        assert _math_shapes.rule_for(span, symbols, False) == rule

    def test_a_function_of_numbers_alone_is_code(self):
        assert _math_shapes.rule_for("sleep(5)", frozenset({"k"}), True) is None

    def test_a_function_counts_by_its_own_name_not_its_argument(self):
        assert _math_shapes.rule_for("print(k)", frozenset({"k"}), False) is None

    def test_a_tuple_needs_every_member_known_or_numeric(self):
        assert _math_shapes.rule_for("(A, foo)", frozenset({"A"}), False) is None

    def test_no_known_names_means_no_symbol_rule(self):
        assert _math_shapes.rule_for("SoC", frozenset(), False) is None


class TestGapMessagesNameTheirRule:
    def test_a_signed_number(self):
        assert _math_findings.warnings("the sign is `-1` here", {}, False) == [
            "`-1` looks like a quantity (signed-number) but has no row in math.md"
        ]

    def test_a_built_symbol(self):
        found = _math_findings.warnings("the `EC_0` value", {"EC - EC_0 = 1": "x"}, False)
        assert found == [
            "`EC_0` is built from symbols this draft's own equations use, but has no row in math.md"
        ]

    def test_an_untagged_fence_with_an_identifier_expression(self):
        assert _math_findings.warnings("```\nx = A * x\n```\n", {}, False) != []

    def test_an_untagged_fence_holding_a_path_is_code(self):
        assert _math_findings.warnings("```\nls code/02-01-x/\n```\n", {}, False) == []


NOT_MATH_TABLE = """\
| ASCII in the draft | LaTeX |
| --- | --- |
| `tau` | `\\tau` |

## Not mathematics

| Code in the draft |
| --- |
| `404` |
| `21.4` |
"""


class TestTheNotMathematicsTable:
    def test_it_is_read_and_never_enters_the_mapping(self, isolated_config):
        draft = _draft(mapping=NOT_MATH_TABLE, text="`tau` `404` `21.4`")
        assert _math.not_math(_math.mapping_text(draft)) == frozenset({"404", "21.4"})
        assert _math.load_mapping(draft) == {"tau": "\\tau"}

    def test_a_listed_span_is_not_a_gap(self):
        text = "the `tau` and `404` and `21.4` here"
        found = _math_findings.warnings(
            text, {"tau": "\\tau"}, True, not_math=frozenset({"404", "21.4"})
        )
        assert found == []

    def test_without_the_table_the_bare_number_warns(self):
        found = _math_findings.warnings("status `404` here", {"tau": "\\tau"}, True)
        assert "`404` looks like a quantity (bare-number)" in found[0]

    def test_a_listed_span_appearing_nowhere_is_reported(self):
        found = _math_findings.findings("no code", {}, True, not_math=frozenset({"404"}))
        assert found == [
            _math_findings.MathFinding(
                "unused-code",
                "`404` is listed as not mathematics in math.md but appears nowhere in the draft",
            )
        ]

    def test_the_orphan_filter_ignores_a_stale_code_row(self, isolated_config):
        from chitragupta.dossier import _draft_fingerprint

        draft = _draft(mapping=NOT_MATH_TABLE, text="`tau`")
        assert _draft_fingerprint._math_desync(draft, "`tau`") == []


DUPLICATE_ROWS = """\
| ASCII in the draft | LaTeX |
| --- | --- |
| `eps_k = y^T * S^-1 * y` | `\\epsilon_k = y^\\top S^{-1} y` |
| `eps_k = y^T * S^-1 * y` | `\\varepsilon_k = y^\\top S^{-1} y` |
| `K = P * H^T` | `K = P H^\\top` |
| `K = P * H^T` | `K = P H^\\top` |
"""


class TestDuplicateRows:
    def test_rows_keep_file_order_and_the_last_row_still_wins(self, isolated_config):
        draft = _draft(mapping=DUPLICATE_ROWS)
        assert len(_math.mapping_rows(_math.mapping_text(draft))) == 4
        assert _math.load_mapping(draft)["eps_k = y^T * S^-1 * y"].startswith("\\varepsilon")

    def test_differing_latex_is_reported_with_both_values(self, isolated_config):
        rows = _math.mapping_rows(_math.mapping_text(_draft(mapping=DUPLICATE_ROWS)))
        found = _math_findings.duplicates(rows)
        assert found == [
            _math_findings.MathFinding(
                "duplicate",
                "`eps_k = y^T * S^-1 * y` has 2 rows in math.md with different LaTeX: "
                "`\\epsilon_k = y^\\top S^{-1} y`, `\\varepsilon_k = y^\\top S^{-1} y`; "
                "the last is rendered",
            )
        ]

    def test_a_span_both_mapped_and_listed_is_reported(self):
        found = _math_findings.duplicates([("404", "404")], frozenset({"404"}))
        assert found == [
            _math_findings.MathFinding(
                "duplicate",
                "`404` has a row in math.md and is also listed as not mathematics; "
                "the row is rendered",
            )
        ]


class TestWhereNoMappingCanExist:
    def test_a_review_report_prints_no_math_findings(self, isolated_config, capsys):
        from chitragupta.render_output import _substitution

        report = config.REVIEW_DIR / "02-01-s.uncited.md"
        _substitution._checked_math_mapping("the value `h = 9` here", report)
        assert "[math]" not in capsys.readouterr().err

    def test_the_same_text_in_a_draft_still_warns(self, isolated_config, capsys):
        from chitragupta.render_output import _substitution

        _substitution._checked_math_mapping("the value `h = 9` here", _draft(mapping=None))
        assert "[math] `h = 9` looks like a quantity" in capsys.readouterr().err

    def test_a_marker_in_a_report_is_still_refused(self, isolated_config):
        from chitragupta.render_output import _substitution

        report = config.REVIEW_DIR / "r.md"
        with pytest.raises(_math.MathMappingError):
            _substitution._checked_math_mapping("<!-- math -->\n```\nx = 1\n```\n", report)

    def test_duplicates_are_printed(self, isolated_config, capsys):
        from chitragupta.render_output import _substitution

        draft = _draft(mapping=DUPLICATE_ROWS, text="`eps_k = y^T * S^-1 * y` `K = P * H^T`")
        _substitution._checked_math_mapping(draft.read_text(encoding="utf-8"), draft)
        assert "[math] `eps_k = y^T * S^-1 * y` has 2 rows" in capsys.readouterr().err


class TestAMappingNamedByTheCaller:
    def test_a_review_copy_takes_the_mapping_it_is_given(self, isolated_config, capsys):
        from chitragupta.render_output import _substitution

        mapping = _math.mapping_path(_draft())
        side = config.REVIEW_DIR / "dt" / "tank.diff" / "new" / "tank.md"
        mapped = _substitution._checked_math_mapping(ASCII_DRAFT, side, mapping)
        assert mapped["dW/dt = -W/tau"] == "\\frac{dW}{dt} = -\\frac{W}{\\tau}"
        assert "[math]" not in capsys.readouterr().err

    def test_without_it_the_review_copy_is_refused(self, isolated_config):
        from chitragupta.render_output import _substitution

        _draft()
        side = config.REVIEW_DIR / "dt" / "tank.diff" / "new" / "tank.md"
        with pytest.raises(_math.MathMappingError, match="there is no"):
            _substitution._checked_math_mapping(ASCII_DRAFT, side)

    def test_a_named_mapping_outside_content_is_refused(self, isolated_config, tmp_path):
        from chitragupta.render_output import _substitution

        outside = tmp_path / "elsewhere" / "math.md"
        outside.parent.mkdir()
        outside.write_text(MAPPING, encoding="utf-8")
        side = config.REVIEW_DIR / "dt" / "tank.diff" / "new" / "tank.md"
        with pytest.raises(config.OutsideContentDir):
            _substitution._checked_math_mapping(ASCII_DRAFT, side, outside)

    def test_render_hands_its_mapping_on(self, isolated_config, monkeypatch):
        seen = []

        class Stop(Exception):
            pass

        def checked(draft_text, input_path, mapping_path=None):
            seen.append(mapping_path)
            raise Stop

        monkeypatch.setattr(render_output, "_checked_math_mapping", checked)
        draft = _draft()
        mapping = _math.mapping_path(draft)
        with pytest.raises(Stop):
            render_output.render(str(draft), output_format="tex", math_mapping_path=mapping)
        assert seen == [mapping]


class TestTheIssuesReproductions:
    def test_1115_file_and_directory_names(self, isolated_config, capsys):
        from chitragupta.render_output import _substitution

        text = (
            "The solution is in `02-02-math-model-solution.md`, and the code is in "
            "`code/02-01-create-mock-physical-twin/`.\n"
        )
        _substitution._checked_math_mapping(text, _draft(mapping=None, text=text))
        assert "[math]" not in capsys.readouterr().err

    def test_1116_six_unmapped_quantities(self, isolated_config, capsys):
        from chitragupta.render_output import _substitution

        mapping = (
            "| ASCII | LaTeX |\n| --- | --- |\n"
            "| `eps_k = y_inn^T * S^-1 * y_inn` | `\\epsilon_k = y^\\top S^{-1} y` |\n"
            "| `K = P * H^T` | `K = P H^\\top` |\n"
        )
        text = (
            "The statistic is `eps_k = y_inn^T * S^-1 * y_inn`, and the gain is `K = P * H^T`.\n\n"
            "The output matrix is `[1 0]` and the noise sign flips to `-1`.\n"
            "The state starts at `[120.0, 1.5]` and moves to `[118.5, 1.5]`.\n"
            "The predicted covariance is `A * P_est * A^T + Q`.\n"
            "The innovation is `-0.074`.\n"
        )
        _substitution._checked_math_mapping(text, _draft(mapping=mapping, text=text))
        err = capsys.readouterr().err
        for span in (
            "[1 0]",
            "-1",
            "[120.0, 1.5]",
            "[118.5, 1.5]",
            "A * P_est * A^T + Q",
            "-0.074",
        ):
            assert f"[math] `{span}` looks like a quantity" in err


def test_a_citekey_shaped_key_contributes_no_names():
    assert _math._symbols_of({"zech_digital-twins-as--service_2024": "12"}) == frozenset()
