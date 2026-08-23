"""chitragupta/render_output/_csl.py: the CSL style a render formats citations with.

Split from one test module to mirror `chitragupta/render_output/`'s own split,
the way `tests/test_enrich_*.py` mirrors `chitragupta/enrich/`. Shared setup --
the binary probes and the figure fixtures -- lives in `tests/conftest.py`
so the eight modules do not each re-run a `kpsewhich` subprocess at
import.
"""

from pathlib import Path
from chitragupta import render_output


class TestResolveCsl:
    def test_absolute_path_is_used_as_given(self, tmp_path):
        style = tmp_path / "house.csl"
        style.write_text("<style/>")
        assert render_output._resolve_csl(str(style)) == style

    def test_relative_path_resolves_against_the_working_directory(self, tmp_path, monkeypatch):
        style = tmp_path / "house.csl"
        style.write_text("<style/>")
        monkeypatch.chdir(tmp_path)
        assert render_output._resolve_csl("house.csl").resolve() == style.resolve()

    def test_repo_relative_path_works_from_another_directory(self, tmp_path, monkeypatch):
        # config.toml's `[render] csl` is documented repo-root-relative and
        # --help prints the default in that form, so the same string has to
        # work when the command is run from outside the repo.
        monkeypatch.chdir(tmp_path)
        resolved = render_output._resolve_csl("assets/csl/ieee.csl")
        assert resolved.is_file()
        assert resolved == render_output.config.shipped("assets", "csl", "ieee.csl")

    def test_the_working_directory_wins_when_both_exist(self, tmp_path, monkeypatch):
        # A local file the user actually typed a path to is never shadowed
        # by a same-named one in the repo.
        local = tmp_path / "assets" / "csl"
        local.mkdir(parents=True)
        (local / "ieee.csl").write_text("<style>local</style>")
        monkeypatch.chdir(tmp_path)
        assert (
            render_output._resolve_csl("assets/csl/ieee.csl").read_text() == "<style>local</style>"
        )

    def test_unresolvable_path_is_returned_as_typed(self, tmp_path, monkeypatch):
        # So the error message names what the user wrote, not a repo-root
        # path they never mentioned.
        monkeypatch.chdir(tmp_path)
        assert render_output._resolve_csl("nope.csl") == Path("nope.csl")


class TestCollapsedCsl:
    def test_adds_the_collapse_attribute_to_a_temp_copy(self, tmp_path):
        csl = tmp_path / "style.csl"
        csl.write_text("<style>\n  <citation>\n    <layout/>\n  </citation>\n</style>\n")
        out_dir = tmp_path / "render-tmp"
        out_dir.mkdir()
        out = render_output._collapsed_csl(csl, out_dir)

        assert out != csl, "must not edit the vendored style in place"
        assert '<citation collapse="citation-number">' in out.read_text()
        assert "collapse=" not in csl.read_text(), "original left untouched"

    def test_keeps_existing_attributes_on_the_citation_tag(self, tmp_path):
        csl = tmp_path / "style.csl"
        csl.write_text('<style><citation et-al-min="3"><layout/></citation></style>')
        text = render_output._collapsed_csl(csl, tmp_path).read_text()
        assert 'collapse="citation-number"' in text
        assert 'et-al-min="3"' in text

    def test_a_style_that_already_collapses_is_returned_unchanged(self, tmp_path):
        csl = tmp_path / "style.csl"
        csl.write_text('<style><citation collapse="year"><layout/></citation></style>')
        # Overriding the style author's own choice would silently change
        # how someone's style renders.
        assert render_output._collapsed_csl(csl, tmp_path) == csl

    def test_a_style_with_no_citation_element_is_returned_unchanged(self, tmp_path):
        csl = tmp_path / "style.csl"
        csl.write_text("<style><bibliography><layout/></bibliography></style>")
        assert render_output._collapsed_csl(csl, tmp_path) == csl


class TestVendoredIeeeStyle:
    def test_is_present_and_is_the_configured_default(self):
        from chitragupta import config

        style = Path(__file__).resolve().parent.parent / "assets" / "csl" / "ieee.csl"
        assert style.is_file()
        assert config.CSL_STYLE_PATH.name == "ieee.csl"

    def test_is_unmodified_upstream(self):
        # assets/csl/README.md promises this file is byte-identical to the
        # CSL project's own ieee.csl, so it can be re-fetched and diffed.
        # The one deviation this project needs lives in _collapsed_csl, so
        # an edit here would mean that promise had quietly been broken.
        style = Path(__file__).resolve().parent.parent / "assets" / "csl" / "ieee.csl"
        assert "collapse=" not in style.read_text()
