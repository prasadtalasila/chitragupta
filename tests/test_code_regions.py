"""chitragupta/_code_regions.py: code-region pairing by linear scan (#824).

The three scanners replaced three DOTALL regexes whose lazy `.*?` ran to
the end of the file for every opener with no closer -- O(N x L) on a
draft of N unclosed fences, enough to take the citation gate hook past
the harness's 30 s kill. The replaced regexes are kept below as
**oracles**: the scanners must agree with them on every input, unclosed
and malformed ones included, so the change is to the cost and nothing
else. The generated documents are small on purpose -- the oracle is the
quadratic thing -- and are built from the constructs whose pairing is
subtle: marker lengths that make the fence regex backtrack, indents,
tildes, info strings, `\\begin`/`\\end` mid-line and at line start,
starred environments, form feeds, and openers left unclosed.

The cost half is asserted by counting the scanners' own probes, never by
wall clock: a 20k-line draft must cost a small multiple of its length.
"""

import random
import re

import pytest

from chitragupta import _code_regions, citation_gate, style_typeset
from chitragupta.render_output._tables import line_of

# citation_gate._LATEX_VERBATIM_RE, as it was.
GATE_ORACLE = re.compile(r"\\begin\{(verbatim|lstlisting|minted)\*?\}.*?\\end\{\1\*?\}", re.DOTALL)
# style_typeset._FENCE_RE, as it was; the body is group 3.
FENCE_ORACLE = re.compile(
    r"^([ \t]*)(`{3,}|~{3,})[^\n]*\n(.*?)^[ \t]*\2[^\n]*$", re.MULTILINE | re.DOTALL
)
# style_typeset._LATEX_VERBATIM_RE, as it was; the body is group 2.
TEX_ORACLE = re.compile(
    r"\\begin\{(verbatim|lstlisting|minted)\*?\}[^\n]*\n(.*?)^[ \t]*\\end\{\1\*?\}",
    re.MULTILINE | re.DOTALL,
)

PIECES = [
    "```",
    "````",
    "`````",
    "``",
    "~~~",
    "~~~~",
    "```python",
    "  ```",
    "\t~~~",
    " ````x",
    "\\begin{verbatim}",
    "\\begin{verbatim*}",
    "\\end{verbatim}",
    "  \\end{verbatim*}",
    "\\begin{lstlisting}[x]",
    "\\end{lstlisting}",
    "\\begin{minted}{py}",
    "\\end{minted} after",
    "text \\begin{verbatim} mid",
    "mid \\end{verbatim} text",
    "\\end{verbatim}\\begin{verbatim}",
    "\\begin{verbatimx}",
    "prose [@a_2024]",
    "\f",
    "",
    "x",
]


def documents(count: int, seed: int = 824):
    rng = random.Random(seed)
    for _ in range(count):
        lines = [rng.choice(PIECES) for _ in range(rng.randint(0, 14))]
        text = "\n".join(lines)
        yield text + ("\n" if rng.random() < 0.5 else "")


def oracle_blank(text: str) -> str:
    return GATE_ORACLE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)


def oracle_bodies(pattern: "re.Pattern", group: int, text: str) -> list:
    return [(line_of(text, m.start(group)), m.group(group)) for m in pattern.finditer(text)]


class TestAgreesWithTheReplacedRegexes:
    def test_gate_blanking(self):
        for text in documents(4000):
            assert _code_regions.blank_latex_verbatim(text) == oracle_blank(text), repr(text)

    def test_fenced_bodies(self):
        for text in documents(4000, seed=1):
            assert _code_regions.fenced_bodies(text) == oracle_bodies(FENCE_ORACLE, 3, text), repr(
                text
            )

    def test_latex_verbatim_bodies(self):
        for text in documents(4000, seed=2):
            expected = oracle_bodies(TEX_ORACLE, 2, text)
            assert _code_regions.latex_verbatim_bodies(text) == expected, repr(text)

    @pytest.mark.parametrize(
        "text",
        [
            "`````\nbody\n```\n",  # a longer opener backtracks to a shorter close
            "```\nbody\n`````python\n",  # a longer close still closes
            "```\n```",  # a closer on the last line, no trailing newline
            "```",  # an opener with no newline after it never opens
            "~~~\nbody\n```\n~~~\n",  # a closer must use the opener's character
            "```\n\fbody\f\n```\n",  # a form feed is not a line break
        ],
    )
    def test_the_fence_regexs_edge_cases(self, text):
        assert _code_regions.fenced_bodies(text) == oracle_bodies(FENCE_ORACLE, 3, text)

    @pytest.mark.parametrize(
        "text",
        [
            "a \\begin{verbatim}x\\end{verbatim} [@k] b",  # mid-line on both ends
            "\\begin{verbatim*}x\\end{verbatim}",  # the stars need not agree
            "\\begin{verbatim} open, never closed [@k]",  # unclosed stays live
            "\\begin{minted}\\end{verbatim}\\end{minted}",  # the close names the open
        ],
    )
    def test_the_gate_regexs_edge_cases(self, text):
        assert _code_regions.blank_latex_verbatim(text) == oracle_blank(text)


class TestLinearCost:
    """The probe counts that make the fix checkable without a stopwatch.

    Each scanner does its per-candidate work through one small function,
    so counting that function's calls counts the work. The replaced
    regexes re-scanned to the end of the file per unclosed opener; these
    must stay within a constant multiple of the draft's size."""

    LINES = 20_000

    @staticmethod
    def counting(monkeypatch, name: str) -> list:
        calls = []
        real = getattr(_code_regions, name)

        def counted(*args):
            calls.append(None)
            return real(*args)

        monkeypatch.setattr(_code_regions, name, counted)
        return calls

    def test_unclosed_verbatim_costs_one_lookup_per_opener(self, monkeypatch, tmp_path):
        """check_text on 20k unclosed `\\begin{verbatim}` lines: the gate
        runs the verbatim pass on Markdown and LaTeX alike, and before
        #824 this input took it O(N x L). An unclosed opener is still
        not blanked, so the citation after them stays checked."""
        lookups = self.counting(monkeypatch, "_next_closer")
        text = "\\begin{verbatim}\n" * self.LINES + "A claim [@nope_2026].\n"
        for suffix in (".md", ".tex"):
            del lookups[:]
            draft = tmp_path / f"big{suffix}"
            draft.write_text(text)
            result = citation_gate.check_text(draft, text, set())
            assert len(lookups) == self.LINES
            if suffix == ".md":
                assert result.unknown == [(self.LINES + 1, "nope_2026")]

    def test_an_unclosed_markdown_draft_is_linear(self, monkeypatch, tmp_path):
        """typeset findings on a 20k-line Markdown draft: an unclosed fence
        on top, then 20k unclosed `\\begin{verbatim}` lines, which the
        gate's blanking pass inside `findings` also scans."""
        lookups = self.counting(monkeypatch, "_next_closer")
        marks = self.counting(monkeypatch, "_fence")
        probes = self.counting(monkeypatch, "_closes")
        draft = tmp_path / "big.md"
        draft.write_text("```python\n" + "\\begin{verbatim}\n" * self.LINES)
        assert style_typeset.findings(draft) == []
        assert len(lookups) == self.LINES
        assert len(marks) == self.LINES + 2  # one per line, the empty last included
        assert probes == []  # no closer anywhere, so nothing was searched for

    def test_a_descending_fence_run_is_linear(self, monkeypatch, tmp_path):
        """A strictly descending run of fence lengths is the fence regex's
        worst case: every opener fails at its own length, scans to the end
        of the file, and only then backtracks to a shorter one. Here no
        line is probed more than once."""
        probes = self.counting(monkeypatch, "_closes")
        count = 2_000
        lines = ["`" * (3 + count - i) for i in range(count)]
        draft = tmp_path / "descending.md"
        draft.write_text("\n".join(lines) + "\n")
        # Each line pairs with the next, shortened to its length: 1000
        # empty blocks, and a delimiter line is never measured for width.
        assert style_typeset.findings(draft) == []
        assert len(_code_regions.fenced_bodies(draft.read_text())) == count // 2
        assert len(probes) <= 2 * len(lines)  # findings, then the direct call

    def test_unclosed_tex_verbatim_costs_one_lookup_per_opener(self, monkeypatch, tmp_path):
        lookups = self.counting(monkeypatch, "_next_closer")
        draft = tmp_path / "big.tex"
        draft.write_text("\\begin{verbatim}\n" * self.LINES)
        assert style_typeset.findings(draft) == []
        assert len(lookups) == self.LINES
