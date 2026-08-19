"""src/review/__init__.py: the review layer's shared output contract -- where a
report goes, what it opens with, and what it must never contain."""

from pathlib import Path

import pytest

from src import config, review


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

    def test_the_three_aids_share_a_directory_and_differ_by_name(self, isolated_config):
        draft = config.DRAFTS_DIR / "dt" / "survey.md"
        paths = [review.report_path(draft, aid) for aid in review.AIDS]
        assert len({p.parent for p in paths}) == 1
        assert len({p.name for p in paths}) == 3

    def test_a_flat_draft_writes_flat(self, isolated_config):
        draft = config.DRAFTS_DIR / "survey.md"
        assert review.report_path(draft, "provenance") == (
            config.REVIEW_DIR / "survey.provenance.md"
        )

    def test_a_draft_outside_drafts_dir_falls_back_flat(self, isolated_config):
        """render_output._output_dir's policy, not dossier_dir's raise: a
        review aid that refuses to run is a worse answer than one that
        writes flat, and nothing later looks the report up by its path."""
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

    def test_a_topic_directory_symlinked_out_of_review_is_refused(
        self, isolated_config, tmp_path
    ):
        """A draft's own path is never a reason to write outside content/."""
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
        text = "\n".join(review.header(draft, "provenance", "python -m src.x --flag v"))

        assert "Review aid, not a gate" in text
        assert str(draft) in text
        assert "python -m src.x --flag v" in text
        assert "chitragupta " in text

    def test_a_draft_path_with_a_space_stays_re_runnable(self, isolated_config):
        """The header claims to record the invocation, so it has to be
        one. Two ways it stopped being one: an unquoted path with a space
        names two arguments, and a bare filename names no directory at
        all -- so two drafts called `survey.md` in different topics wrote
        headers that read identically, the confusion the mirrored path
        exists to prevent, reintroduced inside the file."""
        from src.review import citation_provenance

        draft = config.DRAFTS_DIR / "my topic" / "survey.md"
        draft.parent.mkdir(parents=True)
        draft.write_text("No citations here.\n")

        body = citation_provenance.render_markdown(
            citation_provenance.build_report(draft)
        )

        assert f"- Draft: `{draft}`" in body
        assert f"'{draft}'" in body, "the command has to be shlex-quoted"

    def test_carries_no_date(self, isolated_config):
        """The reason to write a report at all is that it diffs across
        revisions; a wall-clock line defeats that for no gain. Asserted
        against the shape of a date rather than today's value, so this
        cannot pass by accident on the day it was written."""
        import re

        text = "\n".join(review.header(config.DRAFTS_DIR / "s.md", "verbatim", "cmd"))
        assert not re.search(r"\d{4}-\d{2}-\d{2}", text)

    def test_the_banner_names_its_sources_rather_than_linking(self, isolated_config):
        """A report's depth under content/review/ varies with the draft's
        topic path, so a relative link would be right for one report and
        broken for the next."""
        assert "](" not in review.BANNER


class TestWrite:
    def test_writes_the_md_and_returns_its_path(self, isolated_config):
        draft = config.DRAFTS_DIR / "dt" / "survey.md"
        written = review.write(draft, "coverage", "# body\n", ["md"])

        assert written == {"md": config.REVIEW_DIR / "dt" / "survey.coverage.md"}
        assert written["md"].read_text() == "# body\n"

    def test_renders_beside_the_report_not_into_rendered(self, isolated_config, monkeypatch):
        """The whole point of the output contract: a report's .tex/.pdf
        belong with the report, not in the drafting layer's publish
        output. Before 4.0.0 they landed in content/rendered/."""
        from src import render_output

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
        from src import render_output

        def raise_missing(*a, **k):
            raise render_output.MissingBinary("pandoc not found")

        monkeypatch.setattr(render_output, "render", raise_missing)
        written = review.write(
            config.DRAFTS_DIR / "survey.md", "provenance", "# body\n", ["md", "pdf"]
        )

        assert set(written) == {"md"}
        assert "pandoc not found" in capsys.readouterr().err

    def test_json_is_never_rendered(self, isolated_config, monkeypatch):
        """`json` in `--formats` names the payload's own path, and pandoc
        accepts `json` as a real output format -- so passing it on would
        spend a subprocess writing pandoc's document AST over the payload
        (or under it, depending on which ran last)."""
        from src import render_output

        def fail(*a, **k):  # pragma: no cover - the point is it is never called
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


class TestEnvelope:
    """The JSON payload's counterpart to `header()`: the same provenance
    as data, so a payload found on disk names the run that produced it."""

    def test_carries_the_notice_the_aid_the_draft_and_the_command(self, isolated_config):
        draft = config.DRAFTS_DIR / "dt" / "survey.md"

        envelope = review.envelope(draft, "verbatim", "python -m src.review verbatim scan x")

        assert envelope["aid"] == "verbatim"
        assert envelope["draft"] == str(draft)
        assert envelope["command"] == "python -m src.review verbatim scan x"
        assert envelope["version"] == review.version()
        assert "Review aid, not a gate" in envelope["notice"]

    def test_the_notice_leads(self, isolated_config):
        """A payload whose likeliest reader is an agent acting on it says
        what it is before it says what it found."""
        envelope = review.envelope(config.DRAFTS_DIR / "survey.md", "verbatim", "cmd")
        assert next(iter(envelope)) == "notice"

    def test_the_notice_is_the_banner_without_its_markdown(self, isolated_config):
        """Derived, not restated: the two cannot drift into saying
        different things about the same report."""
        envelope = review.envelope(config.DRAFTS_DIR / "survey.md", "verbatim", "cmd")

        assert not envelope["notice"].startswith(">")
        assert "**" not in envelope["notice"]
        assert envelope["notice"] in review.BANNER.replace("**", "")

    def test_carries_no_date(self, isolated_config):
        """The layer's rule, and the reason a payload diffs cleanly
        across revisions -- same as the Markdown header."""
        import re

        envelope = review.envelope(config.DRAFTS_DIR / "survey.md", "verbatim", "cmd")

        assert not re.search(r"\d{4}-\d{2}-\d{2}", str(envelope))

    def test_each_call_returns_a_fresh_dict(self, isolated_config):
        """Callers add their findings to it; a shared dict would leak one
        run's findings into the next one's payload."""
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
        """Same rule as the Markdown: no wall-clock anywhere, so a
        payload diffs cleanly against the next revision's."""
        draft = config.DRAFTS_DIR / "survey.md"
        payload = review.envelope(draft, "verbatim", "cmd") | {"findings": []}

        first = review.write_json(draft, "verbatim", payload).read_bytes()
        second = review.write_json(draft, "verbatim", payload).read_bytes()

        assert first == second

    def test_an_unknown_aid_is_rejected(self, isolated_config):
        """The same guard `report_path` gives the Markdown: a caller
        cannot invent a fourth report kind by typo."""
        with pytest.raises(ValueError, match="Unknown review aid"):
            review.write_json(config.DRAFTS_DIR / "survey.md", "bogus", {})


class TestPrintWritten:
    def test_lists_the_json_sibling_too(self, isolated_config, capsys):
        """A written file the caller isn't told about is one they will
        not know to look for."""
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
        """`verbatim scan --json --write`: this summary is a note to a
        person, and stdout has become machine-readable."""
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
            expected = tomllib.load(handle)["tool"]["poetry"]["version"]
        assert review.version() == expected

    def test_an_unreadable_pyproject_is_not_fatal(self, monkeypatch, tmp_path):
        """A report that cannot name its version is still a useful
        report."""
        # `shipped` rather than a root constant: the version comes from
        # distribution metadata that sits beside the *code*, so pointing
        # the seam at an empty directory is what "no pyproject here" now
        # means. This is also the shape an installed package really has.
        monkeypatch.setattr(config, "shipped", lambda *parts: tmp_path.joinpath(*parts))
        assert review.version() == "unknown"
