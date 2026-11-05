"""chitragupta/render_output/_math_symbols.py: `math.md`'s `## Symbols`
table, what a symbol means, and what `render` says about it (#1143).

The mapping table stays the only source of a symbol's LaTeX; `## Symbols`
only gives a mapped key a meaning. `tests/test_render_output_math.py`
covers the mapping table itself.
"""

from pathlib import Path

import pytest

from chitragupta import config, render_output
from chitragupta.render_output import _math, _math_findings, _math_symbols
from tests.test_render_output_math import TestImportBoundary

MAPPING = """\
# Mathematics

| ASCII in the draft | LaTeX |
| --- | --- |
| `m_t` | `m_\\mathrm{t}` |
| `T_r` | `T_\\mathrm{r}` |
| `T_r = 10` | `T_\\mathrm{r} = 10` |
"""

SYMBOLS = """\
## Symbols

| Symbol | Meaning |
| --- | --- |
| `m_t` | **Target moisture** |
| `T_r` | **Time between reads**, configured |
"""


def _draft(math: str, text: str = "", glossary: "str | None" = None) -> Path:
    """A draft with `math` as its math.md and `glossary` as scope.md's
    `## Glossary` body."""
    draft = config.DRAFTS_DIR / "dt" / "tank.md"
    draft.parent.mkdir(parents=True, exist_ok=True)
    draft.write_text(text, encoding="utf-8")
    dossier = config.DOSSIERS_DIR / "dt" / "tank"
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / "math.md").write_text(math, encoding="utf-8")
    if glossary is not None:
        scope = f"# Scope\n\n## House style\n\n- `x` style.\n\n## Glossary\n\n{glossary}\n"
        (dossier / "scope.md").write_text(scope, encoding="utf-8")
    return draft


def kinds(found) -> "list[str]":
    return [finding.kind for finding in found]


# --- the table and its rows -------------------------------------------------


class TestReadingTheTable:
    def test_the_three_forms_and_a_note(self):
        rows = dict(
            _math_symbols.load_symbols(
                "## Symbols\n\n| Symbol | Meaning |\n| --- | --- |\n"
                "| `m_t` | **Target moisture** |\n"
                "| `m_lo` | **Moisture thresholds**, lower |\n"
                "| `T_c` | see 02-plant |\n"
                "| `e_q` | quantisation error |\n"
            )
        )
        assert rows["m_t"][:3] == ("link", "Target moisture", "")
        assert rows["m_lo"][:3] == ("link", "Moisture thresholds", "lower")
        assert rows["T_c"][:3] == ("see", "02-plant", "")
        assert rows["e_q"][:3] == ("text", "quantisation error", "")

    def test_a_row_knows_its_line_in_the_file(self):
        rows = _math_symbols.load_symbols(MAPPING + "\n" + SYMBOLS)
        assert rows[0][1].line == MAPPING.count("\n") + 6

    def test_an_escaped_pipe_is_part_of_the_meaning(self):
        ((_, meaning),) = _math_symbols.load_symbols(
            "## Symbols\n\n| `p` | the chance of A \\| B |\n"
        )
        assert meaning.text == "the chance of A | B"

    @pytest.mark.parametrize("cell", ["", "   ", "**Term** and more", "**unclosed"])
    def test_an_empty_or_half_bold_meaning_is_malformed(self, cell):
        ((_, meaning),) = _math_symbols.load_symbols(f"## Symbols\n\n| `p` | {cell} |\n")
        assert meaning.kind == "malformed"

    def test_no_section_means_no_rows(self):
        assert _math_symbols.load_symbols(MAPPING) == []
        assert not _math_symbols.has_symbols_section(MAPPING)

    def test_the_section_ends_at_the_next_heading_in_either_order(self):
        text = SYMBOLS + "\n## Not mathematics\n\n| `404` |\n"
        assert [s for s, _ in _math_symbols.load_symbols(text)] == ["m_t", "T_r"]
        assert _math.not_math(text) == frozenset({"404"})


class TestTheMappingIgnoresTheSymbolsTable:
    def test_a_backticked_meaning_is_not_a_mapping_row(self):
        text = MAPPING + "\n## Symbols\n\n| `f_s` | `1 / T_s` |\n"
        assert "f_s" not in dict(_math.mapping_rows(text))
        assert "T_r" in dict(_math.mapping_rows(text))

    def test_a_one_cell_row_under_symbols_is_not_listed_as_code(self):
        assert _math.not_math("## Symbols\n\n| `x` |\n") == frozenset()


@pytest.mark.parametrize(
    "key, bare",
    [
        ("m", True),
        ("T_oil", True),
        ("omega_r", True),
        ("x_hat", True),
        ("C_build", True),
        ("r(t)", False),
        ("m(0)", False),
        ("T_c = 6", False),
        ("10^9", False),
        ("h^2", False),
        ("1 / T_s", False),
    ],
)
def test_which_keys_are_bare_symbols(key, bare):
    assert _math.is_bare_symbol(key) is bare


# --- what render says -------------------------------------------------------


class TestSymbolFindings:
    def test_a_complete_table_says_nothing(self):
        text = MAPPING + "\n" + SYMBOLS
        assert _math_symbols.findings(_math.mapping_rows(text), text) == []

    def test_a_mapped_symbol_with_no_meaning(self):
        text = MAPPING + "\n## Symbols\n\n| `m_t` | **Target moisture** |\n"
        (found,) = _math_symbols.findings(_math.mapping_rows(text), text)
        assert found.kind == "meaning"
        assert "`T_r` is mapped in math.md but has no meaning in its ## Symbols" in found.message

    def test_no_section_is_one_line_not_one_per_symbol(self):
        (found,) = _math_symbols.findings(_math.mapping_rows(MAPPING), MAPPING)
        assert found.kind == "meaning"
        assert "math.md has no ## Symbols: 2 mapped symbols have no meaning" in found.message

    def test_one_missing_symbol_is_singular(self):
        text = "| `k` | `k` |\n"
        (found,) = _math_symbols.findings(_math.mapping_rows(text), text)
        assert "1 mapped symbol has no meaning" in found.message

    def test_a_file_with_only_expressions_needs_no_section(self):
        text = "| `T_c = 6` | `T_c = 6` |\n"
        assert _math_symbols.findings(_math.mapping_rows(text), text) == []

    def test_a_meaning_with_no_mapping_row_cannot_be_typeset(self):
        text = MAPPING + "\n" + SYMBOLS + "| `tol` | **Tolerance** |\n"
        (found,) = _math_symbols.findings(_math.mapping_rows(text), text)
        assert found.kind == "unmapped"
        assert "`tol` has a meaning in ## Symbols but no row in the mapping table" in found.message

    def test_an_expression_may_have_a_meaning(self):
        text = "| `r(t)` | `r(t)` |\n\n## Symbols\n\n| `r(t)` | **Residual** |\n"
        assert _math_symbols.findings(_math.mapping_rows(text), text) == []

    def test_an_empty_meaning_and_a_repeated_symbol_are_malformed(self):
        text = MAPPING + "\n" + SYMBOLS + "| `m_t` | target |\n"
        text = text.replace("**Time between reads**, configured", "")
        found = _math_symbols.findings(_math.mapping_rows(text), text)
        assert kinds(found) == ["malformed", "malformed"]
        assert "`T_r` has a ## Symbols row with no meaning" in found[0].message
        assert "`m_t` has 2 ## Symbols rows" in found[1].message

    def test_a_half_bold_meaning_says_how_to_write_a_link(self):
        text = "| `x` | `x` |\n\n## Symbols\n\n| `x` | **State** vector |\n"
        (found,) = _math_symbols.findings(_math.mapping_rows(text), text)
        assert found.kind == "malformed"
        assert "**Term**, then an optional `, note`" in found.message

    @pytest.mark.parametrize("line", ["| v2 | words |", "| `v` | **A** | extra |"])
    def test_a_line_that_is_no_row_is_not_dropped_silently(self, line):
        text = "| `r(t)` | `r(t)` |\n\n## Symbols\n\n| Symbol | Meaning |\n| --- | --- |\n"
        text += line + "\n"
        (found,) = _math_symbols.findings(_math.mapping_rows(text), text)
        assert found.kind == "malformed"
        assert f"`{line}` under ## Symbols is not a | `symbol` | meaning | row" == found.message


class TestTheOrphanRule:
    def test_a_symbol_used_inside_a_mapped_formula_is_not_an_orphan(self):
        mapping = dict(_math.mapping_rows(MAPPING))
        found = _math_findings.findings("Reads every `T_r = 10` s, aiming at `m_t`.", mapping, True)
        assert "orphan" not in kinds(found)

    def test_it_is_an_orphan_once_the_last_formula_holding_it_goes(self):
        mapping = dict(_math.mapping_rows(MAPPING))
        found = _math_findings.findings("Aiming at `m_t`.", mapping, True)
        assert [f.message for f in found if f.kind == "orphan"] == [
            "`T_r` has a row in math.md but appears nowhere in the draft",
            "`T_r = 10` has a row in math.md but appears nowhere in the draft",
        ]

    def test_a_code_span_keeps_no_symbol_alive(self):
        mapping = {"n": "n", "m": "m"}
        found = _math_findings.findings("Call `range(n)` with `m`.", mapping, True)
        assert [f.message for f in found if f.kind == "orphan"] == [
            "`n` has a row in math.md but appears nowhere in the draft"
        ]

    def test_a_glossary_span_is_a_use(self):
        mapping = {"(M_0 - M_1) * c": "(M_0 - M_1)\\,c", "M_0": "M_0"}
        found = _math_findings.findings(
            "nothing here", mapping, True, glossary=frozenset({"(M_0 - M_1) * c"})
        )
        assert "orphan" not in kinds(found)

    def test_a_key_with_brackets_is_matched_literally(self):
        mapping = {"r": "r", "abs(r) > tol": "|r| > \\mathit{tol}"}
        found = _math_findings.findings("Alarm when `abs(r) > tol`.", mapping, True)
        assert "orphan" not in kinds(found)


class TestGlossarySpans:
    def test_reads_the_spans_of_the_glossary_section_only(self, isolated_config):
        draft = _draft(
            MAPPING,
            glossary="- **Target** -- hold `m_t` above `(M_0 - M_1) * c`.\n"
            "<!-- - **Old** -- `hidden` -->",
        )
        assert _math_symbols.glossary_spans(draft) == frozenset({"m_t", "(M_0 - M_1) * c"})

    def test_the_stamped_digest_line_is_not_a_span(self, isolated_config):
        draft = _draft(MAPPING, glossary="- **A** -- `m_t`.\n\n- draft digest: `123456789012`")
        assert _math_symbols.glossary_spans(draft) == frozenset({"m_t"})

    def test_none_without_a_scope_or_a_glossary(self, isolated_config):
        assert _math_symbols.glossary_spans(_draft(MAPPING)) == frozenset()
        no_glossary = _draft(MAPPING)
        scope = config.DOSSIERS_DIR / "dt" / "tank" / "scope.md"
        scope.write_text("# Scope\n\n## Reader\n\n`m_t` here is not a glossary.\n")
        assert _math_symbols.glossary_spans(no_glossary) == frozenset()
        assert _math_symbols.glossary_spans(config.REVIEW_DIR / "r.md") == frozenset()

    def test_the_section_reader_keeps_the_files_line_numbers(self):
        first_line, body = _math_symbols.glossary_section(
            "# Scope\n\n<!-- a\ncomment -->\n## Glossary\n\n- **A** -- b.\n## Next\n"
        )
        assert first_line == 5  # the heading's line; the body starts below it
        assert body.splitlines()[1] == "- **A** -- b."


class TestRenderPrintsThem:
    def test_the_findings_reach_stderr_and_a_glossary_row_is_not_an_orphan(
        self, isolated_config, capsys
    ):
        draft = _draft(
            MAPPING + "| `tol` | `\\mathit{tol}` |\n",
            text="Every `T_r = 10` s, aiming at `m_t`.\n",
            glossary="- **Tolerance** -- the error `tol` allows.",
        )
        render_output._checked_math_mapping(draft.read_text(encoding="utf-8"), draft)
        err = capsys.readouterr().err
        assert "[math] math.md has no ## Symbols: 3 mapped symbols have no meaning" in err
        assert "orphan" not in err and "`tol` has a row" not in err

    def test_dossier_status_counts_a_glossary_use(self, isolated_config):
        from chitragupta.dossier import _draft_fingerprint

        draft = _draft(
            "| `tol` | `\\mathit{tol}` |\n",
            text="No maths.\n",
            glossary="- **Tolerance** -- the error `tol` allows.",
        )
        assert _draft_fingerprint._math_desync(draft, "No maths.\n") == []


class TestImports:
    def test_stays_inside_the_bare_python_set(self):
        source = Path(_math_symbols.__file__).read_text(encoding="utf-8")
        allowed = {
            "chitragupta.render_output._math",
            "chitragupta.render_output._math_findings",
        }
        TestImportBoundary._assert_imports_within(
            source, allowed, "chitragupta.render_output._math", "_math_symbols.py"
        )
