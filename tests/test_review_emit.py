"""chitragupta/review/_emit.py: the one output procedure every review aid
ran a copy of (#849).

The per-aid CLI tests still pin each aid's own report; these pin the
shared sequence -- which of the four `--json`/`--write` combinations
prints what, where the written-files summary goes, and that nothing is
built for a combination that does not need it.
"""

import argparse
import json
from pathlib import Path

import pytest

from chitragupta import config, ledger, review
from chitragupta.review import _emit
from tests.conftest import make_reference

DRAFT = Path("content/drafts/t/survey.md")


def args(*, as_json=False, write=False, formats="md"):
    return argparse.Namespace(json=as_json, write=write, formats=formats)


@pytest.fixture
def filed(monkeypatch):
    """What `review.write`/`write_json` were asked to file, without
    touching the filesystem."""
    calls = {}

    def write(draft, aid, body, formats):
        calls["md"] = (draft, aid, body, formats)
        return {fmt: Path(f"{aid}.{fmt}") for fmt in formats}

    def write_json(draft, aid, payload):
        calls["json"] = (draft, aid, payload)
        return Path(f"{aid}.json")

    monkeypatch.setattr(review, "write", write)
    monkeypatch.setattr(review, "write_json", write_json)
    return calls


def emit(arguments, built):
    """`_emit.emit` for an aid called `demo`, recording which of its
    lazy pieces were asked for."""

    def piece(name, value):
        def build(*_):
            built.append(name)
            return value

        return build

    return _emit.emit(
        DRAFT,
        "demo",
        arguments,
        text=piece("text", "the report"),
        command=piece("command", "python -m chitragupta.review demo"),
        payload=piece("payload", {"aid": "demo"}),
        markdown=piece("markdown", "# Demo"),
    )


class TestFormats:
    def test_it_splits_strips_and_drops_empties(self):
        assert _emit.formats(args(formats=" md, pdf ,,tex")) == ["md", "pdf", "tex"]


class TestEmit:
    def test_plain_prints_the_text_and_builds_nothing_else(self, filed, capsys):
        built = []
        assert emit(args(), built) == 0
        assert capsys.readouterr().out == "the report\n"
        assert built == ["text"]
        assert filed == {}

    def test_json_prints_the_payload_and_files_nothing(self, filed, capsys):
        built = []
        assert emit(args(as_json=True), built) == 0
        assert json.loads(capsys.readouterr().out) == {"aid": "demo"}
        assert "text" not in built and "markdown" not in built
        assert filed == {}

    def test_write_prints_the_text_then_files_both_and_lists_them_on_stdout(self, filed, capsys):
        built = []
        assert emit(args(write=True, formats="md,pdf"), built) == 0
        out = capsys.readouterr().out
        assert out.startswith("the report\n")
        assert "demo.pdf" in out and "demo.json" in out
        assert filed["md"] == (DRAFT, "demo", "# Demo", ["md", "pdf"])
        assert filed["json"] == (DRAFT, "demo", {"aid": "demo"})

    def test_json_and_write_keep_stdout_valid_json(self, filed, capsys):
        """The summary moves to stderr, so `--json --write > out.json`
        stays a JSON file."""
        built = []
        assert emit(args(as_json=True, write=True), built) == 0
        captured = capsys.readouterr()
        assert json.loads(captured.out) == {"aid": "demo"}
        assert "demo.json" in captured.err
        assert "text" not in built

    def test_the_command_is_built_once_and_handed_to_both(self, filed):
        seen = []
        _emit.emit(
            DRAFT,
            "demo",
            args(write=True),
            text=lambda: "t",
            command=lambda: seen.append("command") or "cmd",
            payload=lambda command: {"command": command},
            markdown=lambda command: f"# {command}",
        )
        assert seen == ["command"]
        assert filed["md"][2] == "# cmd"
        assert filed["json"][2] == {"command": "cmd"}

    def test_a_report_the_render_gate_refuses_still_files_its_json(
        self, isolated_config, ledger_con
    ):
        """#949: the agenda reads the `.json`, so a `tex` the gate refuses
        must not leave the previous run's payload there."""
        ledger.upsert_reference(ledger_con, make_reference(citekey="smith2024"))
        ledger_con.commit()
        draft = config.DRAFTS_DIR / "t" / "survey.md"

        _emit.emit(
            draft,
            "verbatim",
            args(write=True, formats="md,tex"),
            text=lambda: "the report",
            command=lambda: "python -m chitragupta.review verbatim scan",
            payload=lambda _: {"aid": "verbatim", "run": "this one"},
            markdown=lambda _: "> quoted [@not_a_real_citekey_2026]\n",
        )

        filed = json.loads(review.report_path(draft, "verbatim").with_suffix(".json").read_text())
        assert filed["run"] == "this one"


class TestAnnounce:
    """For the aids that file their report unconditionally."""

    def test_plain_lists_what_was_written_on_stdout(self, capsys):
        _emit.announce({"aid": "demo"}, {"md": Path("demo.md")}, as_json=False)
        captured = capsys.readouterr()
        assert "demo.md" in captured.out and captured.err == ""

    def test_json_prints_the_payload_and_moves_the_list_to_stderr(self, capsys):
        _emit.announce({"aid": "demo"}, {"md": Path("demo.md")}, as_json=True)
        captured = capsys.readouterr()
        assert json.loads(captured.out) == {"aid": "demo"}
        assert "demo.md" in captured.err
