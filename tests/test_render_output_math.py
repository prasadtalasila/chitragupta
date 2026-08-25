"""chitragupta/render_output/_math.py: the dossier mapping and the per-format swap.

Split per module the way `tests/test_render_output_figures.py` is, mirroring
`chitragupta/render_output/`'s own split.

The discriminating test here is `TestConvergesOnTheDollarConvention`: a draft
written as ASCII plus a mapping, and the same document written with `$...$`
under `§12`, must hand pandoc byte-identical text. That is the design's whole
claim -- same pdf, different Markdown -- and it tests it without going near
pdf bytes.
"""

import ast
from pathlib import Path

import pytest

from chitragupta import config, render_output
from chitragupta.render_output import _math


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
    """A draft under the patched `content/drafts/`, with an optional mapping."""
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
        # A review report renders through the same function and is not a
        # draft; answering None is what keeps it out of the dossier tree.
        assert _math.mapping_path(config.REVIEW_DIR / "report.md") is None

    def test_a_symlinked_topic_directory_out_of_the_tree_is_refused(
        self, isolated_config, tmp_path
    ):
        # Same guard dossier_dir makes: otherwise a render could read a
        # mapping from anywhere on disk.
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
        # The ordinary state of every draft written before this existed.
        assert _math.load_mapping(_draft(mapping=None)) == {}

    def test_a_draft_with_no_possible_mapping_is_empty(self, isolated_config):
        assert _math.load_mapping(config.REVIEW_DIR / "report.md") == {}

    def test_the_header_row_is_not_a_mapping_row(self, isolated_config):
        # "| ASCII in the draft | LaTeX |" has no backticks, so it cannot
        # match -- but a header that did would silently map prose.
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
        # Every other fence holds code. This is the whole reason the
        # marker exists rather than a ```math tag.
        text = "```\ntau = 48\n```\n"
        assert _math.substitute(text, {"tau = 48": "\\tau = 48"}) == text

    def test_a_marked_block_with_no_row_is_left_alone(self, isolated_config):
        text = "<!-- math -->\n```\nunmapped\n```\n"
        assert _math.substitute(text, {}) == text

    def test_a_block_inside_a_blockquote_keeps_its_indent(self, isolated_config):
        # #406's real-world shape: the fence was nested in a blockquote.
        text = "> <!-- math -->\n> ```\n> C x I > F\n> ```\n"
        out = _math.substitute(text, {"C x I > F": "C \\times I > F"})
        assert out == "> $$\n> C \\times I > F\n> $$\n"

    def test_blocks_substitute_before_spans(self, isolated_config):
        # Order is load-bearing: span-first walks into the fence body and
        # rewrites `W` there, corrupting the block before the display rule
        # sees it.
        text = "<!-- math -->\n```\nW\n```\n"
        out = _math.substitute(text, {"W": "W_{\\text{tank}}", "\nW\n": "wrong"})
        assert out == "$$\nW_{\\text{tank}}\n$$\n"

    def test_a_double_backtick_span_is_not_a_span(self, isolated_config):
        assert _math.substitute("``tau``", {"tau": "\\tau"}) == "``tau``"


class TestConvergesOnTheDollarConvention:
    """The design's central claim, and the cheapest way to test it."""

    def test_ascii_plus_mapping_equals_the_dollar_spelling(self, isolated_config):
        draft = _draft()
        substituted = _math.substitute(draft.read_text(encoding="utf-8"), _math.load_mapping(draft))
        assert substituted == DOLLAR_DRAFT


class TestWarnings:
    def test_a_math_shaped_span_with_no_row_is_a_gap(self, isolated_config):
        found = _math.warnings("the value `h = 9` here", {}, False)
        assert found == ["`h = 9` looks like a quantity but has no row in math.md"]

    def test_a_bare_symbol_the_equations_use_is_a_gap(self, isolated_config):
        # The case the operator heuristic cannot see, and the dominant
        # shape in the corpus this was measured against.
        found = _math.warnings("predicts `W` now", {"x": "W + 1"}, False)
        assert found == [
            "`W` is a symbol this draft's own equations use, but has no row in math.md"
        ]

    def test_a_greek_control_word_counts_as_a_symbol(self, isolated_config):
        found = _math.warnings("the `tau` here", {"x": "\\tau + 1"}, False)
        assert "`tau` is a symbol" in found[0]

    def test_a_non_greek_control_word_is_not_a_symbol(self, isolated_config):
        # \frac must not make `frac` a symbol worth warning about.
        assert _math.warnings("the `frac` here", {"x": "\\frac{1}{2}"}, False) == []

    def test_a_plain_identifier_is_not_a_gap(self, isolated_config):
        assert _math.warnings("field `as_of` here", {}, False) == []

    def test_a_citekey_is_never_a_gap(self, isolated_config):
        assert _math.warnings("see `zech_digital-twins-as--service_2024`", {}, False) == []

    def test_a_mapped_span_is_not_a_gap(self, isolated_config):
        assert _math.warnings("the `tau` here", {"tau": "\\tau"}, True) == []

    def test_a_row_matching_nothing_is_an_orphan(self, isolated_config):
        found = _math.warnings("no maths here", {"tau": "\\tau"}, True)
        assert found == ["`tau` has a row in math.md but appears nowhere in the draft"]

    def test_a_row_used_only_in_a_block_is_not_an_orphan(self, isolated_config):
        text = "<!-- math -->\n```\ndW/dt\n```\n"
        assert _math.warnings(text, {"dW/dt": "X"}, True) == []

    def test_orphans_are_not_reported_when_there_is_no_mapping_file(self, isolated_config):
        # Without a file there is nothing to have gone stale, and every
        # row would be reported against a draft that never had one.
        assert _math.warnings("no maths here", {"tau": "\\tau"}, False) == []

    def test_a_span_inside_a_marked_block_is_not_scanned_as_inline(self, isolated_config):
        # The block is handled by check(); scanning its body as spans too
        # would double-report.
        text = "<!-- math -->\n```\nh = 9\n```\n"
        assert _math.warnings(text, {"h = 9": "h = 9"}, True) == []


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
        # A wrong guess about an inline span must not stop a render; only
        # a marker the author wrote deliberately is certain enough.
        draft = _draft(mapping=None, text="a `h = 9` gap and nothing else\n")
        _math.check(draft.read_text(encoding="utf-8"), draft, {})


class TestCheckedMathMapping:
    """`render`'s own wrapper: load, refuse the certain, warn the rest.

    Extracted from `render` because the four statements pushed it over
    docs/CODE-STANDARDS.md's 25-statement limit, and tested here rather
    than through `render` so a host without pandoc still exercises it.
    """

    def test_returns_the_mapping_and_prints_gaps_to_stderr(self, isolated_config, capsys):
        draft = _draft(text="a mapped `tau` and an unmapped `h = 9`\n")
        mapping = render_output._checked_math_mapping(draft.read_text(encoding="utf-8"), draft)
        assert mapping["tau"] == "\\tau"
        err = capsys.readouterr().err
        assert "[math] `h = 9` looks like a quantity" in err

    def test_a_clean_draft_says_nothing(self, isolated_config, capsys):
        # Every row used, no unmapped quantity: the quiet path. Needs a
        # mapping matching this text exactly -- the fuller MAPPING would
        # report four orphans here, which is the orphan check being right.
        draft = _draft(
            mapping="| ASCII | LaTeX |\n| --- | --- |\n| `tau` | `\\tau` |\n",
            text="a mapped `tau` and the field `as_of`\n",
        )
        render_output._checked_math_mapping(draft.read_text(encoding="utf-8"), draft)
        assert "[math]" not in capsys.readouterr().err

    def test_it_raises_before_warning_on_an_unresolvable_marker(self, isolated_config):
        # check() runs first, so a certain failure is not buried under a
        # list of heuristic warnings.
        draft = _draft(mapping=None)
        with pytest.raises(_math.MathMappingError):
            render_output._checked_math_mapping(draft.read_text(encoding="utf-8"), draft)


class TestTheMarkdownPathLeavesTheAsciiAlone:
    """§12's whole point, and now also a load-bearing equivalence.

    `render`'s Markdown-to-Markdown path composes the same substitution
    chain as the pandoc path (`_substituted`) and passes an **empty**
    mapping, so the two have one definition rather than two. That is only
    correct because an empty mapping substitutes nothing -- this is what
    says so, rather than leaving it to a reader of `_math.substitute`.
    """

    def test_an_empty_mapping_changes_nothing(self):
        assert _math.substitute(ASCII_DRAFT, {}) == ASCII_DRAFT

    def test_the_md_render_keeps_backticked_quantities(self, isolated_config):
        draft = _draft()
        rendered = render_output.render(str(draft), output_format="md")
        text = rendered.read_text(encoding="utf-8")
        assert "`tau = 48`" in text and "```\ndW/dt = -W/tau\n```" in text
        assert "$" not in text


class TestImportBoundary:
    """`render_output` renders under bare `python`; `_math` must not widen that.

    `_paths.py` commits the package to stdlib plus `config`/`citation_gate`/
    `references` so a genre skill can render without the project installed.
    Importing `chitragupta.dossier` for `dossier_dir()` is the obvious
    "simplification" and would break exactly that.
    """

    def test_imports_stay_inside_the_bare_python_set(self):
        allowed = {"chitragupta.config", "chitragupta.citation_gate", "chitragupta.references"}
        source = Path(_math.__file__).read_text(encoding="utf-8")
        imported = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.update(
                    f"{node.module}.{a.name}" if node.module == "chitragupta" else node.module
                    for a in node.names
                )
        # Non-vacuous guard: an AST walk that matched nothing would make
        # the assertion below pass forever, for the wrong reason.
        assert "chitragupta.config" in imported, (
            "the import scan found no chitragupta imports at all, so it is not "
            "checking anything -- has _math.py's import style changed?"
        )
        offenders = {n for n in imported if n.startswith("chitragupta")} - allowed
        assert offenders == set(), (
            f"_math.py imports {offenders}, outside the set _paths.py commits this "
            "package to. Locate the dossier with config.mirrored_dir() instead."
        )

    def test_the_duplicated_path_rule_still_agrees_with_dossier_dir(self, isolated_config):
        """`mapping_path` re-derives what `dossier.dossier_dir` already knows.

        That duplication is deliberate -- importing the dossier package would
        break bare-`python` rendering -- but a duplicate only stays correct
        while nobody moves the original. A test may import what the module
        may not, so this is where the two are held together.
        """
        from chitragupta import dossier

        draft = config.DRAFTS_DIR / "dt" / "tank.md"
        assert _math.mapping_path(draft) == dossier.dossier_dir(draft) / _math.MAPPING_FILENAME
