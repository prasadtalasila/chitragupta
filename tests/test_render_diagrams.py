"""scripts/render_diagrams.py: re-render the diagram exports and record
which source each was rendered from (#850).

The launcher is faked throughout -- a real render needs mermaid-cli and a
headless browser, which a unit suite does not install. What is pinned is
the part that can go wrong silently: which command runs, that a failed
render records nothing, and what the manifest holds.
"""

import json
import subprocess

import pytest

from scripts import render_diagrams


@pytest.fixture
def tree(tmp_path, monkeypatch):
    """A diagrams directory with two sources, wired in as the script's own."""
    diagrams = tmp_path / "diagrams"
    (diagrams / "svg").mkdir(parents=True)
    (diagrams / "a.mmd").write_text("flowchart LR\n  A --> B\n", encoding="utf-8")
    (diagrams / "b.mmd").write_text("flowchart LR\n  B --> C\n", encoding="utf-8")
    monkeypatch.setattr(render_diagrams, "DIAGRAMS", diagrams)
    monkeypatch.setattr(render_diagrams, "MANIFEST", diagrams / "svg" / "sources.json")
    return diagrams


def recorder(returncode=0):
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, returncode, stdout="", stderr="boom")

    return calls, run


class TestFingerprint:
    def test_a_crlf_checkout_fingerprints_like_an_lf_one(self, tmp_path):
        """Windows CI checks the sources out with CRLF under autocrlf; the
        fingerprint must not change with the line endings."""
        lf, crlf = tmp_path / "lf.mmd", tmp_path / "crlf.mmd"
        lf.write_bytes(b"flowchart LR\n  A --> B\n")
        crlf.write_bytes(b"flowchart LR\r\n  A --> B\r\n")
        assert render_diagrams.fingerprint(lf) == render_diagrams.fingerprint(crlf)

    def test_an_edit_changes_it(self, tmp_path):
        one, two = tmp_path / "one.mmd", tmp_path / "two.mmd"
        one.write_text("A --> B\n", encoding="utf-8")
        two.write_text("A --> C\n", encoding="utf-8")
        assert render_diagrams.fingerprint(one) != render_diagrams.fingerprint(two)


class TestRender:
    def test_it_runs_the_documented_command_for_each_source(self, tree):
        calls, run = recorder()
        assert render_diagrams.render(["a", "b"], run=run) == 0
        assert calls[0] == [
            "mmdc",
            "-i",
            str(tree / "a.mmd"),
            "-o",
            str(tree / "svg" / "a.svg"),
            "-b",
            "white",
            "-w",
            "1900",
        ]
        assert len(calls) == 2

    def test_it_records_each_rendered_sources_fingerprint(self, tree):
        _calls, run = recorder()
        render_diagrams.render(["a"], run=run)
        manifest = json.loads((tree / "svg" / "sources.json").read_text(encoding="utf-8"))
        assert manifest == {"a": render_diagrams.fingerprint(tree / "a.mmd")}

    def test_it_keeps_the_entries_it_did_not_render(self, tree):
        (tree / "svg" / "sources.json").write_text(json.dumps({"b": "old"}), encoding="utf-8")
        _calls, run = recorder()
        render_diagrams.render(["a"], run=run)
        manifest = json.loads((tree / "svg" / "sources.json").read_text(encoding="utf-8"))
        assert manifest["b"] == "old" and "a" in manifest

    def test_a_failed_render_is_not_recorded_as_fresh(self, tree, capsys):
        """Recording a fingerprint for an SVG that did not re-render would
        assert a freshness nothing checked -- the one thing this file must
        never say."""
        _calls, run = recorder(returncode=1)
        assert render_diagrams.render(["a"], run=run) == 1
        assert not (tree / "svg" / "sources.json").exists()
        assert "boom" in capsys.readouterr().err

    def test_a_puppeteer_config_is_passed_through(self, tree):
        calls, run = recorder()
        render_diagrams.render(["a"], run=run, puppeteer_config="pp.json")
        assert calls[0][-2:] == ["-p", "pp.json"]

    def test_mmdc_missing_is_a_message_not_a_traceback(self, tree, capsys):
        def run(argv, **kwargs):
            raise FileNotFoundError(argv[0])

        assert render_diagrams.render(["a"], run=run) == 1
        assert "npm install -g @mermaid-js/mermaid-cli@11" in capsys.readouterr().err


class TestMain:
    def test_no_names_means_every_source(self, tree, monkeypatch):
        seen = []
        monkeypatch.setattr(
            render_diagrams, "render", lambda names, **kw: seen.append((names, kw)) or 0
        )
        assert render_diagrams.main([]) == 0
        assert seen == [(["a", "b"], {"puppeteer_config": None})]

    def test_names_and_the_config_reach_render(self, tree, monkeypatch):
        seen = []
        monkeypatch.setattr(
            render_diagrams, "render", lambda names, **kw: seen.append((names, kw)) or 0
        )
        render_diagrams.main(["b", "--puppeteer-config", "pp.json"])
        assert seen == [(["b"], {"puppeteer_config": "pp.json"})]

    def test_an_unknown_name_is_refused(self, tree, capsys):
        assert render_diagrams.main(["nope"]) == 2
        assert "nope" in capsys.readouterr().err


PALETTE_DOC = """# Style

## 🎨 The house palette

```latex
\\definecolor{cgInk}{HTML}{1A1A1A}
\\definecolor{cgFlow}{HTML}{0072B2}
\\definecolor{cgAccent}{HTML}{D55E00}
\\definecolor{cgAlt}{HTML}{009E73}
```

## Elsewhere

\\definecolor{cgStray}{HTML}{123456}
"""

THEME = render_diagrams.house_theme(render_diagrams.palette(PALETTE_DOC))


class TestPalette:
    def test_it_reads_the_house_palette_section_only(self):
        assert render_diagrams.palette(PALETTE_DOC) == {
            "cgInk": "1A1A1A",
            "cgFlow": "0072B2",
            "cgAccent": "D55E00",
            "cgAlt": "009E73",
        }

    def test_a_missing_palette_fails_loudly(self):
        with pytest.raises(ValueError, match="definecolor"):
            render_diagrams.palette("# Style\n\nno palette here\n")


class TestTint:
    def test_it_mixes_with_white_as_tikz_does(self):
        assert render_diagrams.tint("0072B2", 10) == "E6F1F7"

    def test_the_ends_of_the_range(self):
        assert render_diagrams.tint("0072B2", 100) == "0072B2"
        assert render_diagrams.tint("0072B2", 0) == "FFFFFF"


class TestHouseTheme:
    def test_the_roles_take_their_strokes_from_the_palette(self):
        init, roles = THEME
        assert '"primaryBorderColor": "#0072B2"' in init
        assert "classDef key fill:#FBEFE6,stroke:#D55E00" in roles
        assert "stroke-dasharray" in roles.splitlines()[-1]

    def test_the_directive_is_mermaid_json(self):
        init, _ = THEME
        body = init.removeprefix("%%{init: ").removesuffix("}%%")
        assert json.loads(body)["theme"] == "base"


class TestStamp:
    def test_a_flowchart_gets_the_directive_and_the_roles(self):
        out = render_diagrams.stamp("flowchart LR\n  A --> B\n", THEME)
        assert out.startswith(THEME[0] + "\nflowchart LR\n")
        assert out.endswith(THEME[1] + "\n")

    def test_a_sequence_diagram_gets_the_directive_only(self):
        out = render_diagrams.stamp("sequenceDiagram\n  A->>B: hi\n", THEME)
        assert out == THEME[0] + "\nsequenceDiagram\n  A->>B: hi\n"

    def test_a_leading_comment_does_not_hide_a_flowchart(self):
        out = render_diagrams.stamp("%% a note\nflowchart LR\n  A --> B\n", THEME)
        assert out.endswith(THEME[1] + "\n")

    def test_a_state_diagram_keeps_its_roles(self):
        """stateDiagram takes classDef; dropping a hand-written role and
        putting nothing back would leave its `class` lines styling nothing."""
        out = render_diagrams.stamp(
            "stateDiagram-v2\n  classDef flow fill:#fff\n  class a flow\n", THEME
        )
        assert out.endswith(THEME[1] + "\n") and "fill:#fff" not in out

    def test_an_empty_block_gets_the_directive_only(self):
        assert render_diagrams.stamp("", THEME) == THEME[0] + "\n\n"

    def test_restamping_is_a_no_op(self):
        once = render_diagrams.stamp("flowchart LR\n  A --> B\n", THEME)
        assert render_diagrams.stamp(once, THEME) == once

    def test_an_older_theme_is_replaced_not_stacked(self):
        old = render_diagrams.house_theme(
            dict(render_diagrams.palette(PALETTE_DOC), cgFlow="112233")
        )
        stale = render_diagrams.stamp("flowchart LR\n  A --> B\n", old)
        assert render_diagrams.stamp(stale, THEME) == render_diagrams.stamp(
            "flowchart LR\n  A --> B\n", THEME
        )


@pytest.fixture
def docs(tree, tmp_path, monkeypatch):
    """A DIAGRAMS.md listing `a` and `b`, and a palette, wired in."""
    style = tmp_path / "TIKZ-STYLE.md"
    style.write_text(PALETTE_DOC, encoding="utf-8")
    md = tmp_path / "DIAGRAMS.md"
    md.write_text(
        "# Diagrams\n\n```mermaid\nflowchart LR\n  A --> B\n```\n\n"
        "```mermaid\nsequenceDiagram\n  A->>B: hi\n```\n\n"
        f"{render_diagrams.EDITING_HEADING}\n\n| Diagram | `<name>` |\n| --- | --- |\n"
        "| A | `a` |\n| B | `b` |\n",
        encoding="utf-8",
    )
    (tree / "a.mmd").write_text('---\ntitle: "A"\n---\nflowchart LR\n  A --> B\n', encoding="utf-8")
    monkeypatch.setattr(render_diagrams, "DIAGRAMS_MD", md)
    monkeypatch.setattr(render_diagrams, "STYLE_DOC", style)
    return md


class TestSync:
    def test_it_stamps_the_blocks_and_copies_them_keeping_the_title(self, docs, tree):
        assert render_diagrams.sync() == ["a", "b"]
        blocks = render_diagrams.blocks(docs.read_text(encoding="utf-8"))
        assert blocks[0] == render_diagrams.stamp("flowchart LR\n  A --> B\n", THEME)
        assert (tree / "a.mmd").read_text(encoding="utf-8") == '---\ntitle: "A"\n---\n' + blocks[0]
        assert (tree / "b.mmd").read_text(encoding="utf-8") == blocks[1]

    def test_a_second_run_changes_nothing(self, docs):
        render_diagrams.sync()
        assert render_diagrams.sync() == []

    def test_a_block_without_a_row_is_refused(self, docs):
        docs.write_text(
            docs.read_text(encoding="utf-8").replace("| B | `b` |\n", ""), encoding="utf-8"
        )
        with pytest.raises(ValueError, match="2 fenced blocks"):
            render_diagrams.sync()

    def test_main_names_what_to_re_render(self, docs, capsys):
        assert render_diagrams.main(["--sync"]) == 0
        assert "render_diagrams.py a b" in capsys.readouterr().out
        assert render_diagrams.main(["--sync"]) == 0
        assert "already matches" in capsys.readouterr().out
