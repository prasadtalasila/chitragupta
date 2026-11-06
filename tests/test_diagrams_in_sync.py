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
from scripts import render_diagrams
from scripts.render_diagrams import fingerprint

REPO_ROOT = Path(__file__).resolve().parent.parent
DIAGRAMS_MD = REPO_ROOT / "docs" / "DIAGRAMS.md"
DIAGRAMS_DIR = REPO_ROOT / "docs" / "diagrams"
DIAGRAMS_TEXT = DIAGRAMS_MD.read_text(encoding="utf-8")

NAMES = render_diagrams.export_names(DIAGRAMS_TEXT)

_TITLE = re.compile(r"\A---\ntitle:.*?\n---\n", re.DOTALL)
BLOCKS = render_diagrams.blocks(DIAGRAMS_TEXT)

# Every diagram in the docs, DIAGRAMS.md's first: `(doc, name, block)`. A
# block outside DIAGRAMS.md is named by the marker line above it.
ALL = [
    (path.relative_to(REPO_ROOT).as_posix(), name, block)
    for path, names in render_diagrams.sources()
    for name, block in zip(names, render_diagrams.blocks(path.read_text(encoding="utf-8")))
]
ALL_NAMES = [name for _, name, _ in ALL]


def _body(name: str) -> str:
    """A `.mmd` export's Mermaid, without the title front matter the
    fenced block does not carry."""
    return _TITLE.sub("", (DIAGRAMS_DIR / f"{name}.mmd").read_text(encoding="utf-8")).strip()


class TestTheScanIsNotVacuous:
    def test_there_are_diagrams_to_check(self):
        assert len(BLOCKS) >= 10
        assert len({doc for doc, _, _ in ALL}) > 1, "no diagram outside DIAGRAMS.md was found"

    def test_the_table_the_exports_and_the_blocks_agree(self):
        on_disk = sorted(p.stem for p in DIAGRAMS_DIR.glob("*.mmd"))
        assert sorted(ALL_NAMES) == on_disk, (
            "The docs' diagrams (DIAGRAMS.md's 'Editing these' table and every "
            "`<!-- diagram: <name> -->` marker) and docs/diagrams/*.mmd disagree. "
            f"Only in the docs: {sorted(set(ALL_NAMES) - set(on_disk))}; "
            f"only on disk: {sorted(set(on_disk) - set(ALL_NAMES))}."
        )
        assert len(BLOCKS) == len(NAMES), (
            f"docs/DIAGRAMS.md has {len(BLOCKS)} fenced blocks but its 'Editing these' "
            f"table lists {len(NAMES)}. Add or remove the row with the diagram."
        )


class TestTheNameListReadsTheTable:
    def test_a_reworded_table_fails_loudly(self):
        with pytest.raises(ValueError, match="no longer has"):
            render_diagrams.export_names("# Diagrams\n\nno table here\n")

    def test_it_reads_names_in_order_and_skips_the_header(self):
        text = (
            f"{render_diagrams.EDITING_HEADING}\n\n| Diagram | `<name>` |\n| --- | --- |\n"
            "| B | `b-two` |\n| A | `a-one` |\n"
        )
        assert render_diagrams.export_names(text) == ["b-two", "a-one"]


class TestEveryDiagramWearsTheHouseTheme:
    """#1017: one theme, held in one place, in every diagram in the docs. The test for
    the `.mmd` side is the block comparison below; this is the block side."""

    STYLE_TEXT = render_diagrams.STYLE_DOC.read_text(encoding="utf-8")
    THEME = render_diagrams.house_theme(render_diagrams.palette(STYLE_TEXT))

    @pytest.mark.parametrize("doc,name,block", ALL, ids=ALL_NAMES)
    def test_the_block_carries_the_current_theme(self, doc, name, block):
        assert block == render_diagrams.stamp(block, self.THEME), (
            f"The fenced block for {name} in {doc} does not carry the current "
            "house theme. Restamp every block and copy it to its .mmd:\n"
            "    python scripts/render_diagrams.py --sync"
        )

    @pytest.mark.parametrize("doc,name,block", ALL, ids=ALL_NAMES)
    def test_its_classes_are_the_four_roles(self, doc, name, block):
        """A diagram-local classDef brings back a hue the palette does not
        have; a `class` line naming anything else styles nothing."""
        defined = set(re.findall(r"^\s*classDef (\w+)", block, re.MULTILINE))
        used = set(re.findall(r"^\s*class [\w,]+ (\w+)\s*$", block, re.MULTILINE))
        used |= set(re.findall(r":::(\w+)", block))
        roles = set(render_diagrams.ROLES)
        assert defined <= roles and used <= roles, (
            f"{name} uses {sorted((defined | used) - roles)}; map them onto "
            f"{render_diagrams.ROLES} (docs/DIAGRAMS.md, 'Editing these')."
        )
        assert used <= defined, (
            f"{name} uses {sorted(used - defined)} without defining them, so they style "
            "nothing. scripts/render_diagrams.py's _TAKES_CLASSDEF decides which diagram "
            "types --sync adds the roles to."
        )

    def test_no_block_types_a_hex_of_its_own(self):
        """The palette hexes come from docs/TIKZ-STYLE.md and nowhere else:
        every colour a block names is one the generated theme holds."""
        allowed = set(re.findall(r"#[0-9A-F]{6}", "\n".join(self.THEME)))
        typed = {h.upper() for _, _, b in ALL for h in re.findall(r"#[0-9A-Fa-f]{6}\b", b)}
        assert typed <= allowed, f"hexes outside the house theme: {sorted(typed - allowed)}"

    def test_the_sites_stylesheet_is_the_palette(self):
        """mkdocs-material's own Mermaid colours beat the init directive;
        docs/stylesheets/mermaid.css sets them from the same palette."""
        css = REPO_ROOT / "docs" / "stylesheets" / "mermaid.css"
        expected = render_diagrams.mermaid_css(render_diagrams.palette(self.STYLE_TEXT))
        assert css.read_text(encoding="utf-8") == expected, (
            "docs/stylesheets/mermaid.css does not match the house palette:\n"
            "    python scripts/render_diagrams.py --sync"
        )
        mkdocs = (REPO_ROOT / "mkdocs.yml").read_text(encoding="utf-8")
        assert "- docs/stylesheets/mermaid.css" in mkdocs

    def test_the_theme_is_the_tikz_palette(self):
        """Read the palette again, independently of the script's parser, so
        a parser that silently found the wrong colours is caught too."""
        defined = dict(
            re.findall(r"\\definecolor\{(cg\w+)\}\{HTML\}\{([0-9A-F]{6})\}", self.STYLE_TEXT)
        )
        init, roles = self.THEME
        for colour in ("cgFlow", "cgAlt", "cgAccent"):
            assert f"stroke:#{defined[colour]}" in roles
            assert f'BorderColor": "#{defined[colour]}"' in init
        ink = defined["cgInk"]
        assert f'"primaryTextColor": "#{ink}"' in init


class TestEachSvgWasRenderedFromItsCurrentSource:
    """#850: a stale SVG fails with the source to re-render, not only when
    an aid name happens to be missing from it."""

    MANIFEST = json.loads((DIAGRAMS_DIR / "svg" / "sources.json").read_text(encoding="utf-8"))

    def test_every_export_is_in_the_manifest(self):
        assert sorted(self.MANIFEST) == sorted(ALL_NAMES)

    @pytest.mark.parametrize("name", ALL_NAMES)
    def test_the_svg_was_rendered_from_this_mmd(self, name):
        assert self.MANIFEST[name] == fingerprint(DIAGRAMS_DIR / f"{name}.mmd"), (
            f"docs/diagrams/{name}.mmd changed after docs/diagrams/svg/{name}.svg was "
            f"rendered. Re-render it:\n    python scripts/render_diagrams.py {name}"
        )


class TestEachExportMatchesItsFencedBlock:
    @pytest.mark.parametrize("doc,name,block", ALL, ids=ALL_NAMES)
    def test_the_mmd_is_the_block(self, doc, name, block):
        assert _body(name) == block.strip(), (
            f"docs/diagrams/{name}.mmd has drifted from its fenced block in {doc}. "
            "The block is the source of truth -- copy it over and re-render:\n"
            f"    python scripts/render_diagrams.py --sync && "
            f"python scripts/render_diagrams.py {name}"
        )

    @pytest.mark.parametrize("fmt", render_diagrams.FORMATS)
    @pytest.mark.parametrize("name", ALL_NAMES)
    def test_every_export_exists(self, name, fmt):
        """An SVG for the web, a PDF for papers, a PNG for slides: the SVG's
        labels are HTML only a browser draws (docs/DIAGRAMS.md)."""
        assert (DIAGRAMS_DIR / fmt / f"{name}.{fmt}").is_file(), (
            f"docs/diagrams/{fmt}/{name}.{fmt} is missing. Render it:\n"
            f"    python scripts/render_diagrams.py {name}"
        )


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
