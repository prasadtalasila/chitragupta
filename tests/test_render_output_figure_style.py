"""The renderer reports a figure's house block and never rewrites it (#1013)."""

from pathlib import Path

from chitragupta import figure
from chitragupta.render_output import _figure_style
from tests.conftest import MARKED_INPUT, MARKED_MD, TIKZ_FIGURE, figure_pair


def draft(tmp_path, name, body):
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


class TestWarnings:
    def test_a_missing_block_is_reported_with_the_command(self, tmp_path):
        figure_pair(tmp_path)
        [line] = _figure_style.warnings(MARKED_MD, draft(tmp_path, "d.md", MARKED_MD))
        assert line.startswith("figures/fig1.tex: ") and "figure sync" in line

    def test_a_latex_draft_is_checked_too(self, tmp_path):
        figure_pair(tmp_path)
        assert _figure_style.warnings(MARKED_INPUT, draft(tmp_path, "d.tex", MARKED_INPUT))

    def test_a_current_block_says_nothing(self, tmp_path):
        figure_pair(tmp_path)
        source = tmp_path / "figures" / "fig1.tex"
        source.write_text(figure.load_house().text + TIKZ_FIGURE, encoding="utf-8")
        assert _figure_style.warnings(MARKED_MD, draft(tmp_path, "d.md", MARKED_MD)) == []

    def test_the_figure_file_is_not_written(self, tmp_path):
        figure_pair(tmp_path)
        source = tmp_path / "figures" / "fig1.tex"
        before = source.read_bytes()
        _figure_style.warnings(MARKED_MD, draft(tmp_path, "d.md", MARKED_MD))
        assert source.read_bytes() == before

    def test_an_unresolvable_figure_is_left_to_figure_warnings(self, tmp_path):
        assert _figure_style.warnings(MARKED_MD, draft(tmp_path, "d.md", MARKED_MD)) == []

    def test_a_figure_named_twice_is_reported_once(self, tmp_path):
        figure_pair(tmp_path)
        body = MARKED_MD + MARKED_MD
        assert len(_figure_style.warnings(body, draft(tmp_path, "d.md", body))) == 1

    def test_a_broken_install_is_one_line_not_a_crash(self, tmp_path, monkeypatch):
        figure_pair(tmp_path)

        def broken():
            raise OSError("gone")

        monkeypatch.setattr(_figure_style, "load_house", broken)
        [line] = _figure_style.warnings(MARKED_MD, draft(tmp_path, "d.md", MARKED_MD))
        assert "not checked" in line

    def test_an_input_outside_a_figures_directory_is_not_a_figure(self, tmp_path):
        (tmp_path / "sections").mkdir()
        (tmp_path / "sections" / "intro.tex").write_text("Prose.\n", encoding="utf-8")
        body = "\\input{sections/intro.tex}\n"
        assert _figure_style.warnings(body, draft(tmp_path, "d.tex", body)) == []

    def test_an_unreadable_figure_is_skipped_not_raised(self, tmp_path, monkeypatch):
        figure_pair(tmp_path)
        house = figure.load_house()
        monkeypatch.setattr(_figure_style, "load_house", lambda: house)

        def refuse(*_args, **_kwargs):
            raise PermissionError("denied")

        monkeypatch.setattr(Path, "read_text", refuse)
        assert _figure_style.warnings(MARKED_MD, tmp_path / "d.md") == []

    def test_no_figures_never_loads_the_block(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_figure_style, "load_house", lambda: 1 / 0)
        assert _figure_style.warnings("No figure.\n", draft(tmp_path, "d.md", "x")) == []


class TestItReachesTheRenderWarnings:
    def test_draft_warnings_carries_it_under_the_figure_tag(self, tmp_path):
        from chitragupta.render_output._substitution import _draft_warnings

        figure_pair(tmp_path)
        tags = _draft_warnings(MARKED_MD, draft(tmp_path, "d.md", MARKED_MD))
        assert any(tag == "figure" and "figure sync" in text for tag, text in tags)

    def test_a_clean_stamped_pair_has_no_figure_warning_at_all(self, tmp_path):
        from chitragupta.render_output._substitution import _draft_warnings

        figure_pair(tmp_path)
        source = tmp_path / "figures" / "fig1.tex"
        source.write_text(figure.stamp(TIKZ_FIGURE, figure.load_house()), encoding="utf-8")
        tags = _draft_warnings(MARKED_MD, draft(tmp_path, "d.md", MARKED_MD))
        assert [text for tag, text in tags if tag == "figure"] == []
