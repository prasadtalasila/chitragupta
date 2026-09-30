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
