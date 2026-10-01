"""docs/DIAGRAMS.md's fenced blocks against the standalone exports beside
them.

DIAGRAMS.md states the invariant itself: the fenced block is the source of
truth, `docs/diagrams/<name>.mmd` and `docs/diagrams/svg/<name>.svg` are
exports, and *"Edit the fenced block first, then re-render, or the two
drift apart."* Nothing enforced that, and they had drifted -- caught while
auditing the diagrams for the same PR that added this file, and caused by
that PR's own earlier commit, which updated two fenced blocks and left
their `.mmd` exports behind.

That is the failure worth automating: it is silent, it is invisible in
review (the fenced block in the diff looks right), and the stale artefact
is the one a reader drops into a slide deck.

**What this checks, and what it cannot.** Fenced block against `.mmd` is
exact and cheap, so that is enforced strictly. SVG freshness is checked
through `docs/diagrams/svg/sources.json` (#850), which
`scripts/render_diagrams.py` writes as it renders: the fingerprint of the
`.mmd` each export was rendered from. An `.mmd` edited without a
re-render fails here, naming the command to run. Rendering itself is not
done here -- it needs `mermaid-cli` plus a browser, which a unit suite
does not install -- so the manifest is the render's own record, and the
label-text check below remains as a second line for the aid names.
"""

import json
import re
from pathlib import Path

import pytest

from chitragupta import review
from scripts.render_diagrams import fingerprint

REPO_ROOT = Path(__file__).resolve().parent.parent
DIAGRAMS_MD = REPO_ROOT / "docs" / "DIAGRAMS.md"
DIAGRAMS_DIR = REPO_ROOT / "docs" / "diagrams"
DIAGRAMS_TEXT = DIAGRAMS_MD.read_text(encoding="utf-8")

_EDITING_HEADING = "## ✏ Editing these"
_NAME_ROW = re.compile(r"^\| [^|]+ \| `([\w-]+)` \|$", re.MULTILINE)


def _export_names(text: str) -> list[str]:
    """The `<name>` column of DIAGRAMS.md's "Editing these" table, in
    order. That table is the one hand-kept list of diagrams (#866), and
    its order is what ties fenced block i to export i -- so a diagram
    inserted in the middle without its row fails the agreement check
    below rather than silently comparing every later block against the
    wrong export. Refuses to return an empty list: an empty NAMES would
    make every parametrised test below vanish while the run stayed
    green."""
    _, found, tail = text.partition(_EDITING_HEADING)
    names = _NAME_ROW.findall(tail) if found else []
    assert names, (
        f"docs/DIAGRAMS.md no longer has a {_EDITING_HEADING!r} table this test can "
        "read. Rewording it is fine; teach _NAME_ROW the new shape in the same change."
    )
    return names


NAMES = _export_names(DIAGRAMS_TEXT)

_TITLE = re.compile(r"\A---\ntitle:.*?\n---\n", re.DOTALL)
BLOCKS = re.findall(r"```mermaid\n(.*?)```", DIAGRAMS_TEXT, re.DOTALL)


def _body(name: str) -> str:
    """A `.mmd` export's Mermaid, without the title front matter the
    fenced block does not carry."""
    return _TITLE.sub("", (DIAGRAMS_DIR / f"{name}.mmd").read_text(encoding="utf-8")).strip()


class TestTheScanIsNotVacuous:
    def test_there_are_diagrams_to_check(self):
        assert len(BLOCKS) >= 10

    def test_the_table_the_exports_and_the_blocks_agree(self):
        on_disk = sorted(p.stem for p in DIAGRAMS_DIR.glob("*.mmd"))
        assert sorted(NAMES) == on_disk, (
            "docs/DIAGRAMS.md's 'Editing these' table and docs/diagrams/*.mmd disagree. "
            f"Only in the table: {sorted(set(NAMES) - set(on_disk))}; "
            f"only on disk: {sorted(set(on_disk) - set(NAMES))}."
        )
        assert len(BLOCKS) == len(NAMES), (
            f"docs/DIAGRAMS.md has {len(BLOCKS)} fenced blocks but its 'Editing these' "
            f"table lists {len(NAMES)}. Add or remove the row with the diagram."
        )


class TestTheNameListReadsTheTable:
    def test_a_reworded_table_fails_loudly(self):
        with pytest.raises(AssertionError, match="no longer has"):
            _export_names("# Diagrams\n\nno table here\n")

    def test_it_reads_names_in_order_and_skips_the_header(self):
        text = (
            f"{_EDITING_HEADING}\n\n| Diagram | `<name>` |\n| --- | --- |\n"
            "| B | `b-two` |\n| A | `a-one` |\n"
        )
        assert _export_names(text) == ["b-two", "a-one"]


class TestEachSvgWasRenderedFromItsCurrentSource:
    """#850: a stale SVG fails with the source to re-render, not only when
    an aid name happens to be missing from it."""

    MANIFEST = json.loads((DIAGRAMS_DIR / "svg" / "sources.json").read_text(encoding="utf-8"))

    def test_every_export_is_in_the_manifest(self):
        assert sorted(self.MANIFEST) == sorted(NAMES)

    @pytest.mark.parametrize("name", NAMES)
    def test_the_svg_was_rendered_from_this_mmd(self, name):
        assert self.MANIFEST[name] == fingerprint(DIAGRAMS_DIR / f"{name}.mmd"), (
            f"docs/diagrams/{name}.mmd changed after docs/diagrams/svg/{name}.svg was "
            f"rendered. Re-render it:\n    python scripts/render_diagrams.py {name}"
        )


class TestEachExportMatchesItsFencedBlock:
    @pytest.mark.parametrize("index,name", list(enumerate(NAMES)))
    def test_the_mmd_is_the_block(self, index, name):
        assert _body(name) == BLOCKS[index].strip(), (
            f"docs/diagrams/{name}.mmd has drifted from its fenced block in "
            "docs/DIAGRAMS.md. The block is the source of truth -- copy it over and "
            f"re-render:\n"
            f"    python scripts/render_diagrams.py {name}"
        )

    @pytest.mark.parametrize("name", NAMES)
    def test_the_svg_export_exists(self, name):
        assert (DIAGRAMS_DIR / "svg" / f"{name}.svg").is_file()


class TestTheReviewLayerIsDrawnCompletely:
    """The specific staleness that keeps recurring.

    Three diagrams enumerate the review aids and present the enumeration
    as complete -- "REVIEW AIDS: you run these", "Layer 4, the review
    layer". Each listed three of six until this PR. A diagram that merely
    *mentions* one aid is not making a claim about the set and is not
    checked here; these three are.
    """

    ENUMERATING = ("00-main-workflow", "v3-artifacts", "g1-corpus-led", "extra-sequence")

    @pytest.mark.parametrize("name", ENUMERATING)
    def test_it_names_every_aid(self, name):
        body = _body(name)
        missing = [aid for aid in sorted(review.AIDS) if aid not in body]
        assert not missing, (
            f"docs/diagrams/{name}.mmd enumerates the review layer but omits "
            f"{missing}. Update the fenced block in docs/DIAGRAMS.md, copy it over, "
            "and re-render. If this diagram should no longer claim to list them all, "
            "drop it from ENUMERATING here and say why."
        )

    @pytest.mark.parametrize("name", ENUMERATING)
    def test_the_svg_carries_the_same_aids(self, name):
        # The label-text half of SVG freshness: an export re-rendered
        # before the aid landed still says so, and this is what a reader
        # pasting it into a paper would ship.
        svg = (DIAGRAMS_DIR / "svg" / f"{name}.svg").read_text(encoding="utf-8")
        missing = [aid for aid in sorted(review.AIDS) if aid not in svg]
        assert not missing, (
            f"docs/diagrams/svg/{name}.svg omits {missing} -- the .mmd was updated "
            "but not re-rendered."
        )
