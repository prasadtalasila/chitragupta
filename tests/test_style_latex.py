"""What Vale is handed for a `.tex` draft (style_latex.for_vale).

Vale reads a `.tex` fragment as Markdown. Two faults followed, both
measured on a real 8.7k-word thesis chapter:

- Two ``...'' in one paragraph made a Markdown code span of everything
  between them, so the draft's own words there were never checked.
- `vale.ini`'s `TokenIgnores` entries for LaTeX (citation commands,
  `$...$`, command names) dropped findings in long paragraphs: with one
  planted defect marker per prose line, 636 of 839 were reported.

`for_vale` blanks those spans itself, with spaces of the same width, so
every column Vale reports is still the draft's.
"""

import shutil

import pytest

from chitragupta import style_check, style_latex

SAMPLE = (
    "They wrote ``a quote'' \\citep[p.~3]{key_one_2020} and \\emph{this}, with $x_i$.\n"
    "\\begin{verbatim}\nsimply obviously\n\\end{verbatim}\n"
)


def test_every_column_and_line_stays_where_it_was():
    seen = style_latex.for_vale(SAMPLE)
    assert len(seen) == len(SAMPLE)
    assert [i for i, c in enumerate(seen) if c == "\n"] == [
        i for i, c in enumerate(SAMPLE) if c == "\n"
    ]


def test_a_latex_opening_quote_is_no_longer_a_code_span_opener():
    assert "``" not in style_latex.for_vale(SAMPLE)


def test_a_citation_command_and_its_arguments_are_blanked():
    seen = style_latex.for_vale(SAMPLE)
    assert "key_one_2020" not in seen and "p.~3" not in seen


def test_a_command_name_is_blanked_and_its_argument_kept():
    seen = style_latex.for_vale(SAMPLE)
    assert "\\emph" not in seen and "{this}" in seen


def test_inline_math_is_blanked():
    assert "x_i" not in style_latex.for_vale(SAMPLE)


def test_an_escaped_dollar_opens_no_math():
    text = "It costs \\$5 today.\n\nWe did it in order to test, with $x$.\n"
    assert "in order to test" in style_latex.for_vale(text)


def test_math_never_crosses_a_blank_line():
    """An unclosed `$` costs at most its paragraph, as when Vale applied
    the pattern block by block."""
    text = "A stray $ sign.\n\nWe did it in order to test, with $x$ here.\n"
    seen = style_latex.for_vale(text)
    assert "in order to test" in seen and "x" not in seen.split("\n")[2][-8:]


def test_a_command_opening_a_line_does_not_leave_an_indented_code_block():
    """Four leading spaces are a Markdown code block, which Vale skips."""
    seen = style_latex.for_vale("\\emph{obviously} so.\n  \\textbf{also} here.\n")
    assert [line[: len(line) - len(line.lstrip())] for line in seen.splitlines()] == ["", "  "]
    assert seen.startswith(".") and seen.splitlines()[1].lstrip().startswith(".")


def test_a_verbatim_environment_is_blanked_whole():
    """Blanking `\\begin{verbatim}` alone would leave its body as prose,
    since vale.ini's BlockIgnores finds the block by that line."""
    assert "obviously" not in style_latex.for_vale(SAMPLE)


vale_only = pytest.mark.skipif(shutil.which("vale") is None, reason="vale not installed")


def _rules(tmp_path, text, rule):
    draft = tmp_path / "d.tex"
    draft.write_text(text, encoding="utf-8")
    found = style_check.check(draft, override="en-GB", propose=False)["findings"]
    return [(f["line"], f["match"]) for f in found if f["rule"] == rule]


@vale_only
def test_an_escaped_dollar_hides_nothing_from_vale(tmp_path):
    text = (
        "The unit costs \\$5 today.\n\nWe did it in order to test.\n\n"
        "Here $x$ is fine, and in order to win, $y$ too.\n"
    )
    assert _rules(tmp_path, text, "Microsoft.Wordiness") == [(3, "in order to")]


@vale_only
def test_text_between_two_latex_quotations_is_checked(tmp_path):
    text = "Use \\texttt{``x''} in order to test. They wrote ``in order to win''.\n"
    assert _rules(tmp_path, text, "Microsoft.Wordiness") == [(1, "in order to")]


@vale_only
def test_a_long_paragraph_of_citations_and_commands_keeps_its_findings(tmp_path):
    """With only the quotes rewritten, Vale reported nothing for line 4 of
    this paragraph; its TokenIgnores lost the findings."""
    text = (
        "A survey of sensor networks treats the topic as a layered problem, and warns\n"
        "that a tool which ``works at the lower level'' loses the meaning of what was\n"
        "sent \\citep{alpha_one_2025}. At the \\emph{first} level, two nodes share a\n"
        "link -- FOOB, BARQ, ZUPX -- and this is solved; it is not where systems fail.\n"
        "At the \\emph{second} level, they share a format and a schema, so a message\n"
        "can be read. At the \\emph{third} level, they agree on what the fields\n"
        "mean. Beyond that, \\emph{fourth} level agreement -- whether an exchange is\n"
        "allowed and accountable -- is a separate requirement that one consortium's\n"
        "framework names directly, observing that data may come from many places and\n"
        "so may carry ``mixed formats and meanings that must be joined within a\n"
        "single\n"
        "thread'' \\citep{beta_two_2021}. The rest of the work stays at the first.\n"
    )
    assert _rules(tmp_path, text, "chitragupta.Acronyms") == [
        (4, "FOOB"),
        (4, "BARQ"),
        (4, "ZUPX"),
    ]
