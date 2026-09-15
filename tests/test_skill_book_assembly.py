"""`book-assembler` must run the consistency check and surface it.

This file is where #138's "blocking global check" actually lives, and it
is worth saying why a text scan is the right enforcement rather than a
weak substitute for one.

`python -m chitragupta.draft registry check` exits 0 whatever it finds, because
docs/ARCHITECTURE.md's "Layer 4" says a check measured against a
machine's reading of prose "reports and never blocks, whichever layer it
lives in", and that what may be enforced is *invocation* rather than
conformance: "a harness may guarantee that it runs and that its findings
are seen, never that they were obeyed." The assembly skill is that
harness. So the guarantee is exactly this: the skill file tells the
assembling agent to run the check and to report every finding before
composing anything, and a hand edit that dropped either half would be
the bug.

Same shape and same reasoning as tests/test_skill_verbatim_scan_step.py
and tests/test_skill_style_check_step.py -- what the commands do has its
own tests (tests/test_registry.py, tests/test_unit.py, tests/test_spec.py);
this pins only that the skill still tells anyone to run them.
"""

import re
from pathlib import Path

SKILL = (
    Path(__file__).resolve().parent.parent / ".claude" / "skills" / "book-assembler" / "SKILL.md"
)


def _body() -> str:
    """The skill, whitespace collapsed -- these files are hand-wrapped, so
    a command can sit across a line break without being a different
    command."""
    return re.sub(r"\s+", " ", SKILL.read_text(encoding="utf-8"))


def test_the_assembler_runs_the_consistency_check():
    assert "-m chitragupta.draft registry check" in _body()


def test_the_assembler_reports_every_finding_rather_than_summarising():
    """The half that matters. A check that ran and was paraphrased into
    "a few small issues" has not been surfaced."""
    body = _body()
    assert "print every finding to the user, in full, before composing" in body


def test_the_assembler_says_the_check_cannot_block():
    """So nobody later "fixes" the exit code to make the skill's refusal
    automatic -- which is the change DEVELOPER-AGENTS.md bars outright."""
    assert "exits 0 whatever it finds" in _body()


def test_the_assembler_confirms_both_human_gates():
    body = _body()
    assert "-m chitragupta.draft spec status" in body, "the outline sign-off is the first gate"
    assert "-m chitragupta.draft unit status" in body, "assembling unaccepted prose is the failure"
    assert "Do not say the book is finished" in body, "the second gate is a person's"


def test_the_assembler_runs_the_gate_on_what_it_composed():
    """Every unit passed the gate already; the assembled document is a
    new file, and this layer has one exit whatever produced the file."""
    assert "-m chitragupta.draft gate content/rendered/<book>/book.tex" in _body()


def test_the_assembler_writes_no_prose_and_says_where_that_line_is():
    body = _body()
    assert "It writes no prose." in body
    assert "draft-reviser" in body, "a wording change belongs to the reviser, not here"


def test_a_unit_is_converted_by_render_with_the_fragment_flag():
    """A plain `render --format tex` emits a standalone `article` with its
    own `\\begin{document}`, which cannot be `\\input` into a book -- this
    file said to use one until the first real assembly. `--fragment` is
    the flag that exists for it, and going through `render` rather than a
    restated pandoc invocation is what keeps the citeproc, IEEE-style and
    citekey-aliasing behaviour identical to every other rendered draft.

    No `--output-dir`: a draft's renders already mirror its own path, so
    `content/drafts/<book>/<id>.md` lands in `content/rendered/<book>/`,
    which is where `book.tex` is composed. Naming the directory again was
    what put assembly output in the authored one."""
    body = _body()
    assert "--format tex --fragment" in body
    assert "--fragment --output-dir" not in body, "the default already mirrors there"


def test_the_book_carries_no_bibliography_of_its_own():
    """Each chapter's citations were resolved per unit into its own IEEE
    list, so a book-level bibliography would be a second, differently
    numbered answer to the same question."""
    body = _body()
    assert "There is no bibliography at the end" in body
    assert "no bibliography pass at all" in body


def test_the_book_supplies_pandocs_citeproc_macros():
    """The one thing a fragment legitimately emits that only the
    standalone preamble defines. Without this block the book fails on
    `Environment CSLReferences undefined`."""
    assert "print-default-template=latex" in _body()


def test_the_assembler_writes_a_markdown_twin_of_the_book():
    body = _body()
    assert "write `book.md`" in body
    assert "hyperlinking the chapter files" in body


def test_the_assembler_checks_the_build_log_before_believing_the_pdf():
    """pdflatex exits 0 on a book that is missing something: a dropped
    citation is a warning, not an error."""
    assert "Read `book.log` before believing the PDF" in _body()


def test_the_citeproc_macros_go_in_their_own_file():
    """Inline, that block fails the gate on the assembled book: it holds
    `\\cite{#1}` and `\\citeproc{mm}`, which read as citekeys. Found by
    gating a real 15-chapter book, which FAILed on `@mm`, `@#1`, `@#2`."""
    body = _body()
    assert "citeproc-defs.def" in body
    assert "**not inline**" in body


def test_the_assembly_is_composed_into_rendered_not_beside_its_units():
    """`content/drafts/<book>/` holds authored chapters only. Everything
    assembly produces is output, and output mirrors to `content/rendered/`
    like every other render -- which is also why step 4 needs no
    `--output-dir` to put the fragments beside `book.tex`."""
    body = _body()
    assert "content/rendered/<book>/book.tex" in body
    assert "content/rendered/<book>/book.md" in body
    assert "cd content/rendered/<book>" in body, "the build runs where the \\input paths resolve"


def test_the_skeleton_states_its_numbering_and_stops_the_toc_at_sections():
    """`secnumdepth{2}` restates the `book` class default so the book says
    what its numbering is; `tocdepth{1}` is the real departure (the class
    lists subsections). An outline's section titles carry no numbers, so
    there is nothing to be numbered twice."""
    body = _body()
    assert r"\setcounter{secnumdepth}{2}" in body
    assert r"\setcounter{tocdepth}{1}" in body
    assert r"\setcounter{secnumdepth}{-2}" in body, "still the documented override"


def test_an_authored_preamble_is_optional_copied_and_input_last():
    """`content/specs/<book>/preamble.tex` is where a book overrides the
    skeleton -- including the `-2` a self-numbering book needs. Absent is
    the ordinary case and must produce no `\\input` and no remark."""
    body = _body()
    assert "content/specs/<book>/preamble.tex" in body
    assert r"\input{preamble}" in body
    assert "last line of the preamble" in body, "an override after \\begin{document} is too late"
    assert "write no `\\input` and say nothing about it" in body
