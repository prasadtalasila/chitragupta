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

# The order the fenced blocks appear in, mapped to the export names
# docs/DIAGRAMS.md's own "Editing these" table gives. Order is what ties a
# block to a file, so a diagram inserted in the middle without updating
# this list fails the count check below rather than silently comparing
# every later diagram against the wrong export.
NAMES = [
    "v1-overview",
    "v2-first-run",
    "00-main-workflow",
    "v3-artifacts",
    "v4-gates-and-failure",
    "v5-parallelism",
    "g1-corpus-led",
    "g2-teaching",
    "g3-thesis",
    "extra-sequence",
    "extra-ledger-state",
    "t1-discovery-ladder",
    "t2-topic-graphs",
]

_TITLE = re.compile(r"\A---\ntitle:.*?\n---\n", re.DOTALL)
BLOCKS = re.findall(r"```mermaid\n(.*?)```", DIAGRAMS_TEXT, re.DOTALL)


def _body(name: str) -> str:
    """A `.mmd` export's Mermaid, without the title front matter the
    fenced block does not carry."""
    return _TITLE.sub("", (DIAGRAMS_DIR / f"{name}.mmd").read_text(encoding="utf-8")).strip()


class TestTheScanIsNotVacuous:
    def test_there_are_diagrams_to_check(self):
        assert len(BLOCKS) >= 10

    def test_the_block_count_matches_the_export_list(self):
        assert len(BLOCKS) == len(NAMES), (
            f"docs/DIAGRAMS.md has {len(BLOCKS)} fenced blocks but this test knows "
            f"{len(NAMES)} export names. A diagram was added or removed: update NAMES "
            "here and docs/DIAGRAMS.md's own 'Editing these' table together."
        )


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
