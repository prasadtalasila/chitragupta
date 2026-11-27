from chitragupta.render_output import _equation_captions, _math

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
    return _math.substitute(text, MAPPING)


class TestEquations:
    def test_reads_id_and_number_in_document_order(self):
        found = _equation_captions.equations(DRAFT)
        assert [(e.id, e.number) for e in found] == [("energy", 1)]

    def test_an_unmarked_math_block_declares_nothing(self):
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
        out = _equation_captions.substitute(DRAFT + DRAFT, "md")
        assert "**Equation 1:**\n<!-- math -->\n```\nE = m * c^2\n```" in out
        assert "**Equation 2:**\n<!-- math -->\n```\nE = m * c^2\n```" in out


class TestSubstituteLatexBound:
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
        out = _equation_captions.substitute(_mathed(), "pdf")
        assert "$$\nm = E/c^2\n$$" in out

    def test_latex_and_tex_and_pdf_agree(self):
        mathed = _mathed()
        assert _equation_captions.substitute(mathed, "latex") == _equation_captions.substitute(
            mathed, "pdf"
        )


class TestSubstituteOtherPandocFormats:
    def test_docx_keeps_the_dollar_form_and_gets_a_literal_number(self):
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
        mathed = _mathed(DRAFT + DRAFT)
        out = _equation_captions.substitute(mathed, "docx")
        assert "**Equation 1:**\n$$\nE = mc^2\n$$" in out
        assert "**Equation 2:**\n$$\nE = mc^2\n$$" in out


class TestSubstituteLeavesAlone:
    def test_a_latex_fragment_is_untouched(self):
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
