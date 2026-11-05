"""A fragment's auto-generated heading labels carry its unit's id (#1122).

Units in a book repeat their section names -- Summary, Exercises,
Further reading -- and pandoc derives a heading's label from its text
alone, so an assembled `book.tex` defined `summary` once per chapter: 84
`multiply defined` warnings in a real seven-chapter book, and any
`\\ref` to one of them resolved to whichever chapter LaTeX read last.
pandoc's own `--id-prefix` is no remedy: its LaTeX writer ignores it
(checked against pandoc 3.7.0.2).

These run the shipped filter through real pandoc, with exactly the argv
`_unit_labels.pandoc_args` adds, rather than through `render` -- the
filter is the whole fix, and a render would add a ledger and a
bibliography that have nothing to do with labels.
"""

import subprocess
from pathlib import Path

import pytest

from chitragupta import render_output
from chitragupta.render_output import _unit_labels
from tests.conftest import pandoc_available

needs_pandoc = pytest.mark.skipif(not pandoc_available, reason="pandoc not installed")


def _fragment(path: Path, text: str) -> str:
    """`text`, written to `path`, as the LaTeX a `--fragment` render emits."""
    path.write_text(text, encoding="utf-8")
    cmd = ["pandoc", str(path), "-t", "latex", "--top-level-division=chapter"]
    return subprocess.run(
        cmd + _unit_labels.pandoc_args(path, True), capture_output=True, text=True, check=True
    ).stdout


_UNIT = "# Unit {n}\n\n## Summary\n\nFirst.\n\n## Exercises\n\nDo it.\n"


@needs_pandoc
class TestTheFilter:
    def test_two_units_with_the_same_headings_share_no_label(self, tmp_path):
        """The issue's own reproduction."""
        one = _fragment(tmp_path / "u1.md", _UNIT.format(n="one"))
        two = _fragment(tmp_path / "u2.md", _UNIT.format(n="two"))

        assert "\\section{Summary}\\label{u1-summary}" in one
        assert "\\section{Summary}\\label{u2-summary}" in two
        assert "\\label{u1-exercises}" in one
        assert "\\chapter{Unit one}\\label{u1-unit-one}" in one

    def test_a_label_the_author_wrote_is_left_as_written(self, tmp_path):
        """An authored `{#id}` is what the outline and the registry resolve
        against (docs/WRITE-A-BOOK.md's "Why an id is required"), so it
        must survive unchanged -- even when it happens to equal the label
        pandoc would have derived."""
        text = "# One\n\n## Summary {#summary}\n\nA.\n\n## Exercises {#ex-shadow .unnumbered}\n"

        out = _fragment(tmp_path / "u1.md", text)

        assert "\\label{summary}" in out
        assert "\\label{ex-shadow}" in out
        assert "\\label{u1-one}" in out

    def test_a_link_inside_the_unit_follows_the_label_it_points_at(self, tmp_path):
        """Prefixing the label without the link would turn every in-unit
        `[see](#exercises)` into a reference to nothing."""
        text = "# One\n\nSee [the exercises](#exercises) and [it](#mine).\n\n## Exercises\n\n"
        text += "## Mine {#mine}\n"

        out = _fragment(tmp_path / "u1.md", text)

        assert "\\hyperref[u1-exercises]{the exercises}" in out
        assert "\\hyperref[mine]{it}" in out

    def test_a_link_to_another_units_label_is_left_alone(self, tmp_path):
        """A target this unit does not define is another unit's authored
        anchor, which the registry resolves; it is not this filter's to
        rename."""
        out = _fragment(tmp_path / "u1.md", "# One\n\nSee [chapter 2](#ch-2).\n")

        assert "\\hyperref[ch-2]{chapter 2}" in out

    def test_a_latex_unit_keeps_its_labels_and_gets_prefixed_auto_ones(self, tmp_path):
        """A `.tex` draft reaches `render(fragment=True)` too, and pandoc's
        LaTeX reader derives a label for a heading that has none."""
        text = "\\section{Summary}\n\nA.\n\n\\section{Kept}\\label{kept}\n\nB.\n"

        out = _fragment(tmp_path / "u1.tex", text)

        assert "\\label{u1-summary}" in out
        assert "\\label{kept}" in out


class TestTheCommand:
    def _cmd(self, fragment):
        names = ("in.md", "bib.bib", "ieee.csl", "out.tex", "03-unit.md")
        cmd, _ = render_output._pandoc_command(
            *(Path(name) for name in names),
            "tex", "article", "12pt", "a4", "1in", [], fragment, False, [],
        )  # fmt: skip
        return cmd

    def test_a_fragment_prefixes_with_the_drafts_own_stem(self):
        """The input path's stem, not the temporary copy pandoc reads:
        that copy has a name of its own, and a draft's stem is its unit
        id (book-assembler step 4)."""
        cmd = self._cmd(True)

        assert "chitragupta-label-prefix=03-unit-" in cmd
        assert str(_unit_labels.FILTER) in cmd

    def test_a_standalone_render_is_unchanged(self):
        """A standalone document is never `\\input` beside another, so
        its labels cannot collide and stay pandoc's own."""
        assert str(_unit_labels.FILTER) not in self._cmd(False)
