"""assets/tikz/: the known-good layout scaffolds, one per metaphor.

docs/FEATURE-ROADMAP.md's D3 (#382). docs/TIKZ-STYLE.md tells an author
to commit to a layout metaphor before placing a node; these are what
that choice hands them, so a figure starts from a file rather than from
an empty `tikzpicture`.

**The point of this file is that "known-good" is a check and not a
claim.** #382's acceptance criterion is that every scaffold reports zero
binary findings from `python -m chitragupta.review figure`, and the aid
shipped in #314, so the criterion is testable and is tested here rather
than asserted in a README.

Two things it guards that are easy to miss:

- **The metaphor list is read out of docs/TIKZ-STYLE.md**, not restated.
  Adding a row to that table without adding a file here fails, which is
  the coverage half of the criterion.
- **Zero findings has to be earned, not vacuous.** The aid measures a
  node's geometry only where the source spells an explicit `(name)`, so
  a picture that names nothing reports no overlap and no protrusion
  because nothing was measurable at all. Exactly 1 of the 43 figures in
  this repository's own drafted book names a node (#393), so this is the
  normal case rather than a corner. Every scaffold is therefore also
  asserted to have every name it declares come back measured. That
  assertion used to be this file's own workaround for the aid reporting
  the two cases identically; #405 moved the distinction into the aid, so
  it is now a second opinion on a thing `has_findings` already covers
  rather than the only thing covering it.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from chitragupta.review import figure_layout

REPO_ROOT = Path(__file__).resolve().parent.parent
SCAFFOLD_DIR = REPO_ROOT / "assets" / "tikz"
STYLE_DOC = REPO_ROOT / "docs" / "TIKZ-STYLE.md"

# The metaphor table in docs/TIKZ-STYLE.md, found by its header rather
# than by position: the rows after `| Metaphor | TikZ idiom |` and its
# `| --- |` separator, up to the first line that is not a table row.
_TABLE_HEADER = "| Metaphor | TikZ idiom |"
_ROW_RE = re.compile(r"^\|\s*(?P<metaphor>[^|]+?)\s*\|\s*(?P<idiom>[^|]+?)\s*\|$")


def _metaphors() -> list[str]:
    """Every metaphor docs/TIKZ-STYLE.md's table names, in its order."""
    lines = STYLE_DOC.read_text(encoding="utf-8").splitlines()
    start = lines.index(_TABLE_HEADER) + 2  # header, then the `| --- |`
    found = []
    for line in lines[start:]:
        match = _ROW_RE.match(line)
        if match is None:
            break
        found.append(match.group("metaphor"))
    return found


def _slug(metaphor: str) -> str:
    """The file name a metaphor maps to: `Layered stack` ->
    `layered-stack`. Mechanical on purpose -- the mapping is a rule a
    reader can apply, not a lookup table that has to be maintained
    alongside the doc it mirrors."""
    return re.sub(r"[^a-z0-9]+", "-", metaphor.lower()).strip("-")


def _scaffolds() -> list[Path]:
    return sorted(SCAFFOLD_DIR.glob("*.tex"))


def _has_tikz() -> bool:
    """Whether this host can compile a TikZ figure at all.

    The same probe tests/test_figure_layout.py uses, and for the same
    reason: CI's Windows leg installs no `os-deps`, so the geometry half
    of this file has to self-skip rather than fail there.
    """
    if shutil.which("pdflatex") is None or shutil.which("kpsewhich") is None:
        return False
    probe = subprocess.run(["kpsewhich", "tikz.sty"], capture_output=True, check=False)
    return probe.returncode == 0


needs_tikz = pytest.mark.skipif(not _has_tikz(), reason="needs pdflatex with tikz.sty")

# Parametrised by file rather than by metaphor so a failure names the
# scaffold a reader would go and open.
by_scaffold = pytest.mark.parametrize("scaffold", _scaffolds(), ids=lambda p: p.stem)


class TestMetaphorCoverage:
    """The set covers docs/TIKZ-STYLE.md's table, in both directions."""

    def test_the_table_was_actually_read_past_its_first_row(self):
        """The non-vacuous-scan guard every repo-walking test here owes.

        A doc reformat that renamed a column or reflowed the table makes
        `_metaphors()` return nothing, and an empty list satisfies
        `test_every_metaphor_has_a_scaffold` for the wrong reason. More
        than one row also catches the row loop breaking early.

        Deliberately not `>= 6`: the number of metaphors is the style
        doc's to change, and pinning today's count here would turn
        dropping one into a test failure in the wrong file. The set
        equality below is what actually holds the two in step.
        """
        assert len(_metaphors()) > 1

    def test_every_metaphor_has_a_scaffold(self):
        missing = [m for m in _metaphors() if not (SCAFFOLD_DIR / f"{_slug(m)}.tex").exists()]

        assert missing == []

    def test_no_scaffold_names_a_metaphor_the_doc_dropped(self):
        """The other direction: a row deleted from the table leaves a
        file here claiming to implement guidance that no longer
        exists."""
        expected = {_slug(m) for m in _metaphors()}

        assert {path.stem for path in _scaffolds()} == expected


class TestEverySourceProperty:
    """What can be checked without a toolchain, so it runs everywhere."""

    @by_scaffold
    def test_carries_its_own_usetikzlibrary_line(self, scaffold):
        """The renderer's preamble loads `tikz` and no library, so a
        scaffold that relies on `positioning`/`matrix`/`fit` and does
        not load it fails the whole render rather than just itself."""
        assert "\\usetikzlibrary{" in scaffold.read_text(encoding="utf-8")

    @by_scaffold
    def test_names_the_nodes_it_draws(self, scaffold):
        """The measurability precondition, checked from source so it
        also holds on a host with no TeX."""
        assert figure_layout.node_names(scaffold.read_text(encoding="utf-8"))

    @by_scaffold
    def test_no_node_text_past_the_conciseness_line(self, scaffold):
        source = scaffold.read_text(encoding="utf-8")

        assert figure_layout.overlong_nodes(source) == []


@needs_tikz
class TestEveryGeometryProperty:
    """The half that needs a real `pdflatex`."""

    @by_scaffold
    def test_compiles_and_measures_every_name_it_declares(self, scaffold):
        """Zero findings, earned rather than vacuous -- see this
        module's docstring."""
        source = scaffold.read_text(encoding="utf-8")
        boxes = figure_layout.node_boxes(scaffold)
        measured = set(boxes) - {figure_layout.BBOX_NAME}

        assert measured == set(figure_layout.node_names(source))

    @by_scaffold
    def test_no_two_nodes_collide(self, scaffold):
        assert figure_layout.overlaps(figure_layout.node_boxes(scaffold)) == []

    @by_scaffold
    def test_nothing_protrudes(self, scaffold):
        assert figure_layout.protrudes(figure_layout.node_boxes(scaffold)) is False


@needs_tikz
class TestThroughTheDocumentedCommand:
    """One scaffold checked the way an author actually reaches it.

    Everything above calls the library's own functions. This goes
    through `check_draft()`, which is what
    `python -m chitragupta.review figure <draft>` runs -- and which
    resolves a figure only *beside the draft that marks it*, so a
    scaffold is reached by being copied into a draft's `figures/`
    directory, exactly as assets/tikz/README.md tells an author to.
    """

    def test_a_draft_that_starts_from_a_scaffold_reports_no_finding(self, tmp_path):
        figures = tmp_path / "figures"
        figures.mkdir()
        shutil.copy(SCAFFOLD_DIR / "pipeline.tex", figures / "flow.tex")
        draft = tmp_path / "survey.md"
        draft.write_text("Prose.\n\n<!-- figure: figures/flow -->\n", encoding="utf-8")

        results = figure_layout.check_draft(draft)

        assert len(results) == 1
        assert results[0].skipped == ""
        # `has_findings` now carries the whole criterion, because #405
        # put "nothing was measurable" inside it. Before that this had to
        # additionally assert that every declared name came back measured
        # -- the aid could not tell a clean figure from an unmeasured
        # one, so every caller had to make the distinction for itself.
        assert results[0].has_findings is False
        assert results[0].unmeasured == []
