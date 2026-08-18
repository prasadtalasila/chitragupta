"""`book-assembler` must run the consistency check and surface it.

This file is where #138's "blocking global check" actually lives, and it
is worth saying why a text scan is the right enforcement rather than a
weak substitute for one.

`python -m src.draft registry check` exits 0 whatever it finds, because
docs/ARCHITECTURE.md's "Layer 4" says a check measured against a
machine's reading of prose "reports and never blocks, whichever layer it
lives in", and that what may be enforced is *invocation* rather than
conformance: "a harness may guarantee that it runs and that its findings
are seen, never that they were obeyed." The assembly skill is that
harness. So the guarantee is exactly this: the skill file tells the
assembling agent to run the check and to report every finding before
composing anything, and a hand edit that dropped either half would be
the bug.

Same shape and same reasoning as tests/test_skill_verbatim_scan_offer.py
and tests/test_skill_style_check_step.py -- what the commands do has its
own tests (tests/test_registry.py, tests/test_unit.py, tests/test_spec.py);
this pins only that the skill still tells anyone to run them.
"""

import re
from pathlib import Path

SKILL = (Path(__file__).resolve().parent.parent
         / ".claude" / "skills" / "book-assembler" / "SKILL.md")


def _body() -> str:
    """The skill, whitespace collapsed -- these files are hand-wrapped, so
    a command can sit across a line break without being a different
    command."""
    return re.sub(r"\s+", " ", SKILL.read_text(encoding="utf-8"))


def test_the_assembler_runs_the_consistency_check():
    assert "-m src.draft registry check" in _body()


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
    assert "-m src.draft spec status" in body, "the outline sign-off is the first gate"
    assert "-m src.draft unit status" in body, "assembling unaccepted prose is the failure"
    assert "Do not say the book is finished" in body, "the second gate is a person's"


def test_the_assembler_runs_the_gate_on_what_it_composed():
    """Every unit passed the gate already; the assembled document is a
    new file, and this layer has one exit whatever produced the file."""
    assert "-m src.draft gate content/drafts/<book>/book.tex" in _body()


def test_the_assembler_writes_no_prose_and_says_where_that_line_is():
    body = _body()
    assert "It writes no prose." in body
    assert "draft-reviser" in body, "a wording change belongs to the reviser, not here"
