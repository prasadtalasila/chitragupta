import sys
import pytest
from chitragupta import render_output


class TestOutputDir:
    def test_a_draft_in_a_topic_directory_renders_into_that_topic(self, isolated_config):
        draft = isolated_config.DRAFTS_DIR / "dt" / "survey.md"
        assert render_output._output_dir(draft) == isolated_config.RENDERED_DIR / "dt"

    def test_mirrors_a_path_of_any_depth(self, isolated_config):
        draft = isolated_config.DRAFTS_DIR / "books" / "software-engineering" / "chapter.md"
        assert render_output._output_dir(draft) == (
            isolated_config.RENDERED_DIR / "books" / "software-engineering"
        )

    def test_a_flat_draft_is_unchanged(self, isolated_config):
        draft = isolated_config.DRAFTS_DIR / "survey.md"
        assert render_output._output_dir(draft) == isolated_config.RENDERED_DIR

    def test_a_review_report_is_not_a_draft_and_does_not_mirror(self, isolated_config):
        report = isolated_config.REVIEW_DIR / "dt" / "survey.provenance.md"
        assert render_output._output_dir(report) == isolated_config.RENDERED_DIR

    def test_a_draft_outside_the_drafts_directory_falls_back_to_flat(
        self, isolated_config, tmp_path
    ):
        assert render_output._output_dir(tmp_path / "elsewhere" / "draft.md") == (
            isolated_config.RENDERED_DIR
        )

    def test_a_parent_escaping_argument_cannot_steer_the_output(self, isolated_config, tmp_path):
        escaping = isolated_config.DRAFTS_DIR / ".." / ".." / "outside" / "draft.md"
        assert render_output._output_dir(escaping) == isolated_config.RENDERED_DIR

    def test_a_symlinked_draft_is_judged_by_where_it_really_lives(self, isolated_config, tmp_path):
        real = tmp_path / "outside" / "survey.md"
        real.parent.mkdir(parents=True)
        real.write_text("# T\n")
        link_dir = isolated_config.DRAFTS_DIR / "dt"
        link_dir.mkdir(parents=True)
        (link_dir / "survey.md").symlink_to(real)

        assert render_output._output_dir(link_dir / "survey.md") == (isolated_config.RENDERED_DIR)

    def test_a_mirrored_directory_that_escapes_is_refused(self, isolated_config, tmp_path):
        outside = tmp_path / "outside"
        outside.mkdir()
        isolated_config.RENDERED_DIR.mkdir(parents=True)
        (isolated_config.RENDERED_DIR / "dt").symlink_to(outside, target_is_directory=True)

        draft = isolated_config.DRAFTS_DIR / "dt" / "survey.md"
        draft.parent.mkdir(parents=True)
        draft.write_text("# T\n")

        with pytest.raises(render_output.OutsideContentDir, match="outside"):
            render_output._output_dir(draft)

    @pytest.mark.parametrize("attr", ["RENDERED_DIR", "DRAFTS_DIR"])
    def test_a_content_directory_pointing_out_of_the_tree_is_refused(
        self, isolated_config, tmp_path, monkeypatch, attr
    ):
        outside = tmp_path / "outside"
        outside.mkdir()
        link = isolated_config.CONTENT_DIR / f"linked-{attr}"
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(outside, target_is_directory=True)
        monkeypatch.setattr(isolated_config, attr, link)

        with pytest.raises(render_output.OutsideContentDir, match="content directory"):
            render_output._output_dir(isolated_config.DRAFTS_DIR / "survey.md")

    def test_the_cli_reports_an_escaping_directory_rather_than_raising(
        self, isolated_config, tmp_path, monkeypatch, capsys
    ):
        outside = tmp_path / "outside"
        outside.mkdir()
        isolated_config.CONTENT_DIR.mkdir(parents=True, exist_ok=True)
        link = isolated_config.CONTENT_DIR / "linked-rendered"
        link.symlink_to(outside, target_is_directory=True)
        monkeypatch.setattr(isolated_config, "RENDERED_DIR", link)

        draft = isolated_config.DRAFTS_DIR / "survey.md"
        draft.parent.mkdir(parents=True)
        draft.write_text("# T\n")
        monkeypatch.setattr(sys, "argv", ["render_output.py", str(draft), "--format", "md"])

        rc = render_output.main()

        assert rc == 1
        assert "[error]" in capsys.readouterr().out
