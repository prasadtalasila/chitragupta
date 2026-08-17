"""src/render_output/_paths.py: where a rendered draft lands.

Split from one test module to mirror `src/render_output/`'s own split,
the way `tests/test_enrich_*.py` mirrors `src/enrich/`. Shared setup --
the binary probes and the figure fixtures -- lives in `tests/conftest.py`
so the eight modules do not each re-run a `kpsewhich` subprocess at
import.
"""

import sys
import pytest
from src import render_output


class TestOutputDir:
    """Where a render lands: beside the draft's own place under
    content/drafts/, mirrored into content/rendered/."""

    def test_a_draft_in_a_topic_directory_renders_into_that_topic(self, isolated_config):
        draft = isolated_config.DRAFTS_DIR / "dt" / "survey.md"
        assert render_output._output_dir(draft) == isolated_config.RENDERED_DIR / "dt"

    def test_mirrors_a_path_of_any_depth(self, isolated_config):
        # The layout a user asks for by naming a place rather than a
        # topic ("a book chapter in books/software-engineering").
        draft = isolated_config.DRAFTS_DIR / "books" / "software-engineering" / "chapter.md"
        assert render_output._output_dir(draft) == (
            isolated_config.RENDERED_DIR / "books" / "software-engineering"
        )

    def test_a_flat_draft_is_unchanged(self, isolated_config):
        # The layout every documented invocation uses -- it must keep
        # landing exactly where it always has.
        draft = isolated_config.DRAFTS_DIR / "survey.md"
        assert render_output._output_dir(draft) == isolated_config.RENDERED_DIR

    def test_a_review_report_is_not_a_draft_and_does_not_mirror(self, isolated_config):
        """`content/review/` is not a mirror source.

        3.19.2 made `PROVENANCE_DIR` a second source root so a report's
        renders would follow the report. 4.0.0 replaced that with
        `render(output_dir=...)`: `src/review/__init__.py` says where its renders
        go, and this function is left answering only "where does a
        *draft* render to". Reaching here with a report at all means the
        caller forgot to pass `output_dir`, and the flat fallback is the
        right answer for a file that isn't under `content/drafts/`.
        """
        report = isolated_config.REVIEW_DIR / "dt" / "survey.provenance.md"
        assert render_output._output_dir(report) == isolated_config.RENDERED_DIR

    def test_a_draft_outside_the_drafts_directory_falls_back_to_flat(
        self, isolated_config, tmp_path
    ):
        # Since 3.17.0 `render()` confines its *input* to content/ too,
        # so this is reachable only for a file under content/ but outside
        # content/drafts/ -- there is no path to mirror, so the flat
        # directory stands. Called directly here, below that check.
        assert render_output._output_dir(tmp_path / "elsewhere" / "draft.md") == (
            isolated_config.RENDERED_DIR
        )

    def test_a_parent_escaping_argument_cannot_steer_the_output(
        self, isolated_config, tmp_path
    ):
        # `..` is gone by the time anything is compared, because both
        # sides are resolved first -- so this names a draft outside
        # content/drafts/ and gets the flat directory, not a write into
        # tmp_path.
        escaping = isolated_config.DRAFTS_DIR / ".." / ".." / "outside" / "draft.md"
        assert render_output._output_dir(escaping) == isolated_config.RENDERED_DIR

    def test_a_symlinked_draft_is_judged_by_where_it_really_lives(
        self, isolated_config, tmp_path
    ):
        # The draft's path says content/drafts/dt/, but the file is
        # elsewhere on disk. Mirroring the name rather than the reality
        # would be a directory this project doesn't own.
        real = tmp_path / "outside" / "survey.md"
        real.parent.mkdir(parents=True)
        real.write_text("# T\n")
        link_dir = isolated_config.DRAFTS_DIR / "dt"
        link_dir.mkdir(parents=True)
        (link_dir / "survey.md").symlink_to(real)

        assert render_output._output_dir(link_dir / "survey.md") == (
            isolated_config.RENDERED_DIR
        )

    def test_a_mirrored_directory_that_escapes_is_refused(self, isolated_config, tmp_path):
        # content/rendered/dt/ already exists as a symlink out of
        # content/. Following it would write the render outside the
        # content directory; redirecting it to the flat directory
        # instead would be a second place the user didn't name either.
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
        # Neither content/rendered nor content/drafts may resolve out of
        # the content directory: the mirroring rule is defined between
        # the two, and one of them living elsewhere means every render
        # writes where nothing else in the pipeline looks.
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
