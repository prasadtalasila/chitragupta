"""chitragupta/render_output/_equation_captions.py: issue 457's opt-in
equation number, and the `equationref` that reads it.

Split per module the way `tests/test_render_output_tables.py` and
`tests/test_render_output_figure_captions.py` are, mirroring
`chitragupta/render_output/`'s own split.

The discriminating tests here are `TestSubstituteLatexBound` and
`TestSubstituteMarkdown`: unlike a table or a figure, an equation's
*content* is transformed by `_math.substitute` before this module ever
sees it, on every format except `md` -- so the two have to recognise two
different shapes of the same marked block, not just choose a different
caption string. Getting either wrong renders an equation with a stray
`<!-- equation: id -->` comment and no number at all.
"""

from chitragupta.render_output import _equation_captions, _math

# The pre-substitution shape: `equation:` directly above `math`, directly
# above a fence -- what a draft actually contains.
DRAFT = """\
# Energy

<!-- equationref: energy --> relates mass and energy.

<!-- equation: energy -->
<!-- math -->
```
E = m * c^2
```

A second, unmarked step is not numbered:

<!-- math -->
```
m = E / c^2
```

<!-- equationref: energy --> is the one that matters.
"""

MAPPING = {"E = m * c^2": "E = mc^2", "m = E / c^2": "m = E/c^2"}


def _mathed(text: str = DRAFT) -> str:
    """`DRAFT` after `_math.substitute` has run with `MAPPING` -- the shape
    every non-`md` format actually hands this module, per `_substituted`'s
    composition order."""
    return _math.substitute(text, MAPPING)


class TestEquations:
    def test_reads_id_and_number_in_document_order(self):
        found = _equation_captions.equations(DRAFT)
        assert [(e.id, e.number) for e in found] == [("energy", 1)]

    def test_an_unmarked_math_block_declares_nothing(self):
        # The second block in DRAFT has no `equation:` marker -- this is
        # the whole mechanism that leaves a derivation step unnumbered.
        assert len(_equation_captions.equations(DRAFT)) == 1

    def test_a_draft_with_no_equation_marker_declares_nothing(self):
        assert _equation_captions.equations("<!-- math -->\n```\nx\n```\n") == []


class TestEquationReferences:
    def test_no_references_in_plain_prose(self):
        assert _equation_captions.references("Just prose.\n") == []

    def test_every_equationref_is_found_with_its_line(self):
        found = _equation_captions.references(DRAFT)
        assert [id_ for id_, _ in found] == ["energy", "energy"]


class TestSubstituteMarkdown:
    """`md` never reaches pandoc, so `_math.substitute` is a no-op on this
    path -- this module sees the *pristine* ascii+fence shape, and has to
    number it without touching the equation's own content."""

    def test_a_numbered_label_is_added_above_the_untouched_block(self):
        out = _equation_captions.substitute(DRAFT, "md")
        assert "**Equation 1:**\n<!-- math -->\n```\nE = m * c^2\n```" in out
        assert "<!-- equation: energy -->" not in out

    def test_the_math_content_itself_is_byte_identical(self):
        out = _equation_captions.substitute(DRAFT, "md")
        assert "E = m * c^2" in out
        assert "m = E / c^2" in out

    def test_an_unmarked_block_gets_no_label(self):
        out = _equation_captions.substitute(DRAFT, "md")
        assert "**Equation 2:**" not in out

    def test_references_carry_the_literal_number(self):
        out = _equation_captions.substitute(DRAFT, "md")
        assert "Equation 1 relates mass and energy." in out
        assert "Equation 1 is the one that matters." in out

    def test_two_equations_sharing_an_id_are_numbered_positionally(self):
        # m-57: a `numbers` dict keyed by id let a later equation
        # overwrite an earlier one's number -- both equations claiming
        # `energy` used to render as "Equation 2". _tables.substitute
        # already numbers by position for the same reason (a reused id
        # cannot resolve as a dict key); this must match.
        out = _equation_captions.substitute(DRAFT + DRAFT, "md")
        assert "**Equation 1:**\n<!-- math -->\n```\nE = m * c^2\n```" in out
        assert "**Equation 2:**\n<!-- math -->\n```\nE = m * c^2\n```" in out


class TestSubstituteLatexBound:
    """The text handed in here is already past `_math.substitute`, which
    is what turns the marked block into real `$$...$$` on this path."""

    def test_becomes_a_real_equation_environment(self):
        out = _equation_captions.substitute(_mathed(), "pdf")
        assert "\\begin{equation}\nE = mc^2\n\\label{eq:energy}\n\\end{equation}" in out
        assert "<!-- equation: energy -->" not in out
        assert "$$" not in out.split("\\end{equation}")[0].split("\\begin{equation}")[1]

    def test_a_reference_becomes_a_latex_ref(self):
        out = _equation_captions.substitute(_mathed(), "tex")
        assert "`Equation~\\ref{eq:energy}`{=latex} relates mass" in out
        assert "<!-- equationref:" not in out

    def test_an_unmarked_equation_stays_plain_display_math(self):
        # The second, unmarked block: still real math after `_math`, but
        # never wrapped in an `equation` environment.
        out = _equation_captions.substitute(_mathed(), "pdf")
        assert "$$\nm = E/c^2\n$$" in out

    def test_latex_and_tex_and_pdf_agree(self):
        mathed = _mathed()
        assert _equation_captions.substitute(mathed, "latex") == _equation_captions.substitute(
            mathed, "pdf"
        )


class TestSubstituteOtherPandocFormats:
    def test_docx_keeps_the_dollar_form_and_gets_a_literal_number(self):
        # Verified against how `_math.substitute` behaves on this path:
        # docx/html reach pandoc with a real mapping too, so the block is
        # already `$$...$$` by the time this module runs -- pandoc's own
        # writers do not number it, so the number is written as text.
        out = _equation_captions.substitute(_mathed(), "docx")
        assert "**Equation 1:**\n$$\nE = mc^2\n$$" in out
        assert "\\begin{equation}" not in out

    def test_html_is_treated_the_same_way_as_docx(self):
        mathed = _mathed()
        assert _equation_captions.substitute(mathed, "docx") == _equation_captions.substitute(
            mathed, "html"
        )

    def test_a_reference_becomes_a_literal_equation_number(self):
        out = _equation_captions.substitute(_mathed(), "docx")
        assert "Equation 1 relates mass" in out

    def test_two_equations_sharing_an_id_are_numbered_positionally(self):
        # m-57: same last-wins bug, on the dollar-substituted path.
        mathed = _mathed(DRAFT + DRAFT)
        out = _equation_captions.substitute(mathed, "docx")
        assert "**Equation 1:**\n$$\nE = mc^2\n$$" in out
        assert "**Equation 2:**\n$$\nE = mc^2\n$$" in out


class TestSubstituteLeavesAlone:
    def test_a_latex_fragment_is_untouched(self):
        # thesis-chapter-writer writes \[...\]/\(...\) directly and has no
        # marker vocabulary at all -- §12's existing carve-out.
        fragment = "See \\[E = mc^2\\]. No marker here.\n"
        assert _equation_captions.substitute(fragment, "pdf") == fragment

    def test_an_unknown_reference_is_left_in_place(self):
        text = "As <!-- equationref: nowhere --> shows.\n"
        assert _equation_captions.substitute(text, "md") == text


class TestWarnings:
    def test_an_equation_marker_with_no_math_block_after_it(self):
        text = "<!-- equation: bare -->\n\nprose, no math marker\n"
        assert _equation_captions.warnings(text) == [
            "`bare` names no `<!-- math -->` block directly below it, so nothing numbers it"
        ]

    def test_a_reference_to_an_id_no_equation_declares(self):
        assert _equation_captions.warnings(DRAFT + "\nAlso <!-- equationref: ghost -->.\n") == [
            "`ghost` is referred to but no equation declares it"
        ]

    def test_two_equations_claiming_one_id(self):
        found = _equation_captions.warnings(DRAFT + DRAFT)
        assert "`energy` is declared by more than one equation" in found

    def test_a_clean_draft_warns_about_nothing(self):
        assert _equation_captions.warnings(DRAFT) == []
