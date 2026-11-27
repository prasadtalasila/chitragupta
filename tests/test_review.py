import subprocess
from pathlib import Path

import pytest

from chitragupta import config, ledger, render_output, review
from chitragupta.render_output._failures import RENDER_FAILURES
from tests.conftest import lualatex_available, make_reference, pandoc_available


class TestReportPath:
    def test_mirrors_the_drafts_topic_directory(self, isolated_config):
        draft = config.DRAFTS_DIR / "dt" / "survey.md"
        assert review.report_path(draft, "provenance") == (
            config.REVIEW_DIR / "dt" / "survey.provenance.md"
        )

    def test_mirrors_a_path_of_any_depth(self, isolated_config):
        draft = config.DRAFTS_DIR / "books" / "se" / "chapter.md"
        assert review.report_path(draft, "verbatim") == (
            config.REVIEW_DIR / "books" / "se" / "chapter.verbatim.md"
        )

    def test_two_topics_sharing_a_stem_do_not_collide(self, isolated_config):
        a = review.report_path(config.DRAFTS_DIR / "topic-a" / "survey.md", "coverage")
        b = review.report_path(config.DRAFTS_DIR / "topic-b" / "survey.md", "coverage")
        assert a != b

    def test_every_aid_shares_a_directory_and_differs_by_name(self, isolated_config):
        draft = config.DRAFTS_DIR / "dt" / "survey.md"
        paths = [review.report_path(draft, aid) for aid in review.AIDS]
        assert len({p.parent for p in paths}) == 1
        assert len({p.name for p in paths}) == len(review.AIDS)

    def test_a_flat_draft_writes_flat(self, isolated_config):
        draft = config.DRAFTS_DIR / "survey.md"
        assert review.report_path(draft, "provenance") == (
            config.REVIEW_DIR / "survey.provenance.md"
        )

    def test_a_draft_outside_drafts_dir_falls_back_flat(self, isolated_config):
        draft = config.CONTENT_DIR / "loose.md"
        assert review.report_path(draft, "provenance") == (
            config.REVIEW_DIR / "loose.provenance.md"
        )

    def test_an_unknown_aid_is_rejected(self, isolated_config):
        with pytest.raises(ValueError, match="Unknown review aid"):
            review.report_path(config.DRAFTS_DIR / "survey.md", "typo")

    def test_an_escaping_review_dir_is_refused(self, isolated_config, tmp_path):
        outside = tmp_path / "outside"
        outside.mkdir()
        config.REVIEW_DIR.parent.mkdir(parents=True, exist_ok=True)
        config.REVIEW_DIR.symlink_to(outside)

        with pytest.raises(config.OutsideContentDir):
            review.report_path(config.DRAFTS_DIR / "survey.md", "provenance")

    def test_a_topic_directory_symlinked_out_of_review_is_refused(self, isolated_config, tmp_path):
        outside = tmp_path / "outside"
        outside.mkdir()
        (config.REVIEW_DIR).mkdir(parents=True, exist_ok=True)
        (config.REVIEW_DIR / "dt").symlink_to(outside)

        with pytest.raises(config.OutsideContentDir):
            review.report_path(config.DRAFTS_DIR / "dt" / "survey.md", "provenance")


class TestRequireReviewable:
    def test_accepts_a_draft_under_drafts(self, isolated_config):
        draft = config.DRAFTS_DIR / "survey.md"
        draft.parent.mkdir(parents=True)
        draft.write_text("# s\n")
        assert review.require_reviewable(draft) == draft

    def test_refuses_a_draft_outside_content(self, isolated_config, tmp_path):
        outside = tmp_path / "outside.md"
        outside.write_text("# s\n")
        with pytest.raises(config.OutsideContentDir):
            review.require_reviewable(outside)

    def test_refuses_a_missing_draft(self, isolated_config):
        with pytest.raises(FileNotFoundError):
            review.require_reviewable(config.DRAFTS_DIR / "nope.md")

    def test_a_symlink_is_judged_by_where_it_really_lives(self, isolated_config, tmp_path):
        real = tmp_path / "outside.md"
        real.write_text("# s\n")
        config.DRAFTS_DIR.mkdir(parents=True)
        link = config.DRAFTS_DIR / "survey.md"
        link.symlink_to(real)

        with pytest.raises(config.OutsideContentDir):
            review.require_reviewable(link)


class TestHeader:
    def test_carries_the_banner_the_draft_and_the_command(self, isolated_config):
        draft = config.DRAFTS_DIR / "dt" / "survey.md"
        text = "\n".join(review.header(draft, "provenance", "python -m chitragupta.x --flag v"))

        assert "Review aid, not a gate" in text
        assert str(draft) in text
        assert "python -m chitragupta.x --flag v" in text
        assert "chitragupta " in text

    def test_a_draft_path_with_a_space_stays_re_runnable(self, isolated_config, ledger_con):
        from chitragupta.review import _citation_provenance_render, citation_provenance

        draft = config.DRAFTS_DIR / "my topic" / "survey.md"
        draft.parent.mkdir(parents=True)
        draft.write_text("No citations here.\n")

        body = _citation_provenance_render.render_markdown(citation_provenance.build_report(draft))

        assert f"- Draft: `{draft}`" in body
        assert f"'{draft}'" in body, "the command has to be shlex-quoted"

    def test_carries_no_date(self, isolated_config):
        import re

        text = "\n".join(review.header(config.DRAFTS_DIR / "s.md", "verbatim", "cmd"))
        assert not re.search(r"\d{4}-\d{2}-\d{2}", text)

    def test_the_banner_names_its_sources_rather_than_linking(self, isolated_config):
        assert "](" not in review.BANNER


class TestWrite:
    def test_writes_the_md_and_returns_its_path(self, isolated_config):
        draft = config.DRAFTS_DIR / "dt" / "survey.md"
        written = review.write(draft, "coverage", "# body\n", ["md"])

        assert written == {"md": config.REVIEW_DIR / "dt" / "survey.coverage.md"}
        assert written["md"].read_text() == "# body\n"

    def test_renders_beside_the_report_not_into_rendered(self, isolated_config, monkeypatch):
        from chitragupta import render_output

        seen = {}

        def fake_render(path, fmt, **kwargs):
            seen["output_dir"] = kwargs.get("output_dir")
            return kwargs["output_dir"] / f"survey.provenance.{fmt}"

        monkeypatch.setattr(render_output, "render", fake_render)
        draft = config.DRAFTS_DIR / "dt" / "survey.md"

        written = review.write(draft, "provenance", "# body\n", ["md", "tex"])

        assert seen["output_dir"] == config.REVIEW_DIR / "dt"
        assert written["tex"].parent == written["md"].parent

    def test_a_missing_binary_degrades_to_the_md(self, isolated_config, monkeypatch, capsys):
        from chitragupta import render_output

        def raise_missing(*a, **k):
            raise render_output.MissingBinary("pandoc not found")

        monkeypatch.setattr(render_output, "render", raise_missing)
        written = review.write(
            config.DRAFTS_DIR / "survey.md", "provenance", "# body\n", ["md", "pdf"]
        )

        assert set(written) == {"md"}
        assert "pandoc not found" in capsys.readouterr().err

    @pytest.mark.parametrize("failure", RENDER_FAILURES, ids=lambda c: c.__name__)
    def test_every_render_failure_degrades_to_the_md(
        self, isolated_config, monkeypatch, capsys, failure
    ):
        def refuse(*a, **k):
            if failure is subprocess.CalledProcessError:
                raise failure(1, ["pandoc"], stderr="pandoc said no")
            raise failure("render refused")

        monkeypatch.setattr(render_output, "render", refuse)
        written = review.write(
            config.DRAFTS_DIR / "survey.md", "verbatim", "# body\n", ["md", "tex"]
        )

        assert set(written) == {"md"}
        assert "WARNING: skipped tex" in capsys.readouterr().err

    def test_a_report_quoting_an_unknown_key_still_writes_its_md(
        self, isolated_config, ledger_con, capsys
    ):
        ledger.upsert_reference(ledger_con, make_reference(citekey="smith2024"))
        ledger_con.commit()

        written = review.write(
            config.DRAFTS_DIR / "survey.md",
            "verbatim",
            "> quoted [@not_a_real_citekey_2026]\n",
            ["md", "tex"],
        )

        assert set(written) == {"md"}
        assert "not_a_real_citekey_2026" in capsys.readouterr().err

    def test_json_is_never_rendered(self, isolated_config, monkeypatch):
        from chitragupta import render_output

        def fail(*a, **k):  # never called: that is the point
            raise AssertionError("json reached render_output.render")

        monkeypatch.setattr(render_output, "render", fail)

        written = review.write(
            config.DRAFTS_DIR / "survey.md", "verbatim", "# body\n", ["md", "json"]
        )

        assert set(written) == {"md"}

    def test_two_writes_of_the_same_body_are_byte_identical(self, isolated_config):
        draft = config.DRAFTS_DIR / "survey.md"
        body = "\n".join(review.header(draft, "verbatim", "cmd") + ["## Findings", ""])

        first = review.write(draft, "verbatim", body, ["md"])["md"].read_bytes()
        second = review.write(draft, "verbatim", body, ["md"])["md"].read_bytes()

        assert first == second

    def test_a_private_use_character_is_written_as_a_marker(self, isolated_config, capsys):
        body = "> updated at every step \ue230 and the gain follows.\n"

        written = review.write(config.DRAFTS_DIR / "survey.md", "provenance", body, ["md"])

        assert written["md"].read_text(encoding="utf-8") == (
            "> updated at every step [U+E230] and the gain follows.\n"
        )
        assert "shown as [U+E230]" in capsys.readouterr().err

    def test_a_report_without_one_prints_no_note(self, isolated_config, capsys):
        review.write(config.DRAFTS_DIR / "survey.md", "provenance", "# body\n", ["md"])
        assert "private-use" not in capsys.readouterr().err

    @pytest.mark.slow
    @pytest.mark.skipif(
        not (pandoc_available and lualatex_available), reason="pandoc/lualatex not installed"
    )
    def test_the_issues_report_now_renders_a_pdf(self, isolated_config):
        isolated_config.BIB_FILE_PATH.write_text("")
        body = (
            "# Provenance\n\nClosest passage in the source:\n\n"
            "> The filter state is updated at every step \ue230 and the gain follows.\n"
        )

        written = review.write(config.DRAFTS_DIR / "x.md", "provenance", body, ["md", "pdf"])

        assert written["pdf"].exists()


class TestEnvelope:
    def test_carries_the_notice_the_aid_the_draft_and_the_command(self, isolated_config):
        draft = config.DRAFTS_DIR / "dt" / "survey.md"

        envelope = review.envelope(
            draft, "verbatim", "python -m chitragupta.review verbatim scan x"
        )

        assert envelope["aid"] == "verbatim"
        assert envelope["draft"] == str(draft)
        assert envelope["command"] == "python -m chitragupta.review verbatim scan x"
        assert envelope["version"] == review.version()
        assert "Review aid, not a gate" in envelope["notice"]

    def test_the_notice_leads(self, isolated_config):
        envelope = review.envelope(config.DRAFTS_DIR / "survey.md", "verbatim", "cmd")
        assert next(iter(envelope)) == "notice"

    def test_the_notice_is_the_banner_without_its_markdown(self, isolated_config):
        envelope = review.envelope(config.DRAFTS_DIR / "survey.md", "verbatim", "cmd")

        assert not envelope["notice"].startswith(">")
        assert "**" not in envelope["notice"]
        assert envelope["notice"] in review.BANNER.replace("**", "")

    def test_carries_no_date(self, isolated_config):
        import re

        envelope = review.envelope(config.DRAFTS_DIR / "survey.md", "verbatim", "cmd")

        assert not re.search(r"\d{4}-\d{2}-\d{2}", str(envelope))

    def test_each_call_returns_a_fresh_dict(self, isolated_config):
        draft = config.DRAFTS_DIR / "survey.md"
        first = review.envelope(draft, "verbatim", "cmd")
        first["findings"] = ["mine"]

        assert "findings" not in review.envelope(draft, "verbatim", "cmd")


class TestWriteJson:
    def test_lands_beside_the_markdown_report(self, isolated_config):
        draft = config.DRAFTS_DIR / "dt" / "survey.md"

        path = review.write_json(draft, "verbatim", {"findings": []})

        assert path == config.REVIEW_DIR / "dt" / "survey.verbatim.json"
        assert path.parent == review.report_path(draft, "verbatim").parent

    def test_round_trips_as_json_with_a_trailing_newline(self, isolated_config):
        import json

        path = review.write_json(
            config.DRAFTS_DIR / "survey.md", "verbatim", {"findings": [{"page": 2}]}
        )
        text = path.read_text()

        assert json.loads(text) == {"findings": [{"page": 2}]}
        assert text.endswith("}\n")

    def test_two_writes_of_the_same_payload_are_byte_identical(self, isolated_config):
        draft = config.DRAFTS_DIR / "survey.md"
        payload = review.envelope(draft, "verbatim", "cmd") | {"findings": []}

        first = review.write_json(draft, "verbatim", payload).read_bytes()
        second = review.write_json(draft, "verbatim", payload).read_bytes()

        assert first == second

    def test_an_unknown_aid_is_rejected(self, isolated_config):
        with pytest.raises(ValueError, match="Unknown review aid"):
            review.write_json(config.DRAFTS_DIR / "survey.md", "bogus", {})


class TestPrintWritten:
    def test_lists_the_json_sibling_too(self, isolated_config, capsys):
        review.print_written({"md": Path("a.md"), "json": Path("a.json")})

        out = capsys.readouterr().out
        assert "a.md" in out
        assert "a.json" in out

    def test_defaults_to_stdout(self, isolated_config, capsys):
        review.print_written({"md": Path("a.md")})

        captured = capsys.readouterr()
        assert "a.md" in captured.out
        assert captured.err == ""

    def test_a_caller_whose_stdout_is_a_payload_can_route_it_to_stderr(
        self, isolated_config, capsys
    ):
        import sys

        review.print_written({"md": Path("a.md"), "json": Path("a.json")}, stream=sys.stderr)

        captured = capsys.readouterr()
        assert captured.out == ""
        assert "a.md" in captured.err
        assert "a.json" in captured.err


class TestVersion:
    def test_reads_the_single_source_of_truth(self):
        import tomllib

        with open(config.shipped("pyproject.toml"), "rb") as handle:
            expected = tomllib.load(handle)["project"]["version"]
        assert expected != "unknown"
        assert review.version() == expected

    def test_an_unreadable_pyproject_is_not_fatal(self, monkeypatch, tmp_path):
        monkeypatch.setattr(config, "shipped", lambda *parts: tmp_path.joinpath(*parts))
        assert review.version() == "unknown"
