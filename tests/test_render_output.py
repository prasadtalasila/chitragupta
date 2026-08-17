"""src/render_output.py: Pandoc/LaTeX rendering. Stdlib + config/
citation_gate/references only (deliberately, so it runs with bare
python3 -- see the module docstring), so these tests use the real
pandoc/pdflatex binaries installed on this host rather than mocking
subprocess, for genuine end-to-end confidence on the one stage most
likely to have host-environment gaps (see Task-1's lmodern.sty find)."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from src import ledger
from src import render_output
from src.render_output import _cli as _render_cli  # noqa: F401  (attribute access below)

from tests.conftest import content_draft, make_reference

pandoc_available = shutil.which("pandoc") is not None
pdflatex_available = shutil.which("pdflatex") is not None
# tikz.sty is texlive-pictures (#222), a separate package from the ones
# scripts/install_full_pipeline.sh already installed for lmodern etc. --
# pdflatex being on PATH doesn't guarantee it, so this is its own probe
# rather than folded into pdflatex_available.
tikz_available = (
    shutil.which("kpsewhich") is not None
    and subprocess.run(
        ["kpsewhich", "tikz.sty"], capture_output=True, check=False
    ).returncode == 0
)


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
        assert resolved == render_output.config.REPO_ROOT / "assets" / "csl" / "ieee.csl"

    def test_the_working_directory_wins_when_both_exist(self, tmp_path, monkeypatch):
        # A local file the user actually typed a path to is never shadowed
        # by a same-named one in the repo.
        local = tmp_path / "assets" / "csl"
        local.mkdir(parents=True)
        (local / "ieee.csl").write_text("<style>local</style>")
        monkeypatch.chdir(tmp_path)
        assert render_output._resolve_csl("assets/csl/ieee.csl").read_text() == "<style>local</style>"

    def test_unresolvable_path_is_returned_as_typed(self, tmp_path, monkeypatch):
        # So the error message names what the user wrote, not a repo-root
        # path they never mentioned.
        monkeypatch.chdir(tmp_path)
        assert render_output._resolve_csl("nope.csl") == Path("nope.csl")


class TestCollapsedCsl:
    def test_adds_the_collapse_attribute_to_a_temp_copy(self, tmp_path):
        csl = tmp_path / "style.csl"
        csl.write_text('<style>\n  <citation>\n    <layout/>\n  </citation>\n</style>\n')
        out_dir = tmp_path / "render-tmp"
        out_dir.mkdir()
        out = render_output._collapsed_csl(csl, out_dir)

        assert out != csl, "must not edit the vendored style in place"
        assert '<citation collapse="citation-number">' in out.read_text()
        assert 'collapse=' not in csl.read_text(), "original left untouched"

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
        from src import config

        style = Path(__file__).resolve().parent.parent / "assets" / "csl" / "ieee.csl"
        assert style.is_file()
        assert config.CSL_STYLE_PATH.name == "ieee.csl"

    def test_is_unmodified_upstream(self):
        # assets/csl/README.md promises this file is byte-identical to the
        # CSL project's own ieee.csl, so it can be re-fetched and diffed.
        # The one deviation this project needs lives in _collapsed_csl, so
        # an edit here would mean that promise had quietly been broken.
        style = Path(__file__).resolve().parent.parent / "assets" / "csl" / "ieee.csl"
        assert 'collapse=' not in style.read_text()


class TestSwapManualRefsForCiteproc:
    def test_keeps_the_heading_and_swaps_the_entries_for_the_anchor(self):
        text = "# Title\n\nA claim [@k].\n\n## References\n\n[1] A Paper, 2024. `k`\n"
        assert render_output._swap_manual_refs_for_citeproc(text) == (
            "# Title\n\nA claim [@k].\n\n## References\n\n::: {#refs}\n:::\n"
        )

    def test_preserves_a_draft_s_own_numbered_heading(self):
        # textbook-chapter-writer passes --heading "6. References" to match
        # its other headings; citeproc emits no heading of its own, so
        # dropping this one left the rendered bibliography untitled.
        text = "A claim [@k].\n\n## 6. References\n\n[1] A Paper, 2024. `k`\n"
        assert "## 6. References" in render_output._swap_manual_refs_for_citeproc(text)

    def test_preserves_the_heading_level(self):
        text = "A claim [@k].\n\n#### References\n\n[1] A Paper, 2024. `k`\n"
        assert "#### References" in render_output._swap_manual_refs_for_citeproc(text)

    def test_handles_a_heading_on_the_final_line_without_a_newline(self):
        text = "A claim [@k].\n\n## References"
        out = render_output._swap_manual_refs_for_citeproc(text)
        assert out.endswith("## References\n\n::: {#refs}\n:::\n")

    def test_leaves_a_draft_without_one_alone(self):
        text = "# Title\n\nA claim [@k].\n"
        assert render_output._swap_manual_refs_for_citeproc(text) == text

    def test_leaves_a_latex_fragment_alone(self):
        # thesis-chapter-writer's .tex fragment has no Markdown heading and
        # defers to the user's own thesis-wide bibliography.
        text = "A claim \\citep{k}.\n\n\\section{References}\n"
        assert render_output._swap_manual_refs_for_citeproc(text) == text


class TestAliasFor:
    def test_replaces_double_hyphen(self):
        assert render_output._alias_for("zech_digital-twins-as--service_2024") == \
            "zech_digital-twins-as-x2d-service_2024"

    @pytest.mark.parametrize("citekey", [
        "zech_digital-twins-as--service_2024",
        # This project's own corpus has a 3-hyphen key. A single
        # replace("--", "-x2d-") leaves "state-x2d--art" -- still
        # truncating, so the citation resolves to nothing and the source
        # silently disappears from the rendered bibliography.
        "tygesen_state---art_2019",
        "a----b",
    ])
    def test_alias_never_leaves_a_double_hyphen_behind(self, citekey):
        assert "--" not in render_output._alias_for(citekey)

    def test_no_double_hyphen_unchanged_value(self):
        # _alias_for always transforms; callers only invoke it for keys
        # already known to contain "--" (see _safe_render_inputs).
        assert render_output._alias_for("plain_key_2024") == "plain_key_2024"


class TestSafeRenderInputs:
    def test_no_bad_keys_returns_original_paths(self, tmp_path):
        md = tmp_path / "in.md"
        md.write_text("Citing [@smith_2024].\n")
        bib = tmp_path / "bibliography.bib"
        bib.write_text("@article{smith_2024,\n  title={T},\n}\n")

        safe_md, safe_bib = render_output._safe_render_inputs(md, bib, tmp_path / "tmp")
        assert safe_md == md
        assert safe_bib == bib

    def test_double_hyphen_key_gets_aliased_in_both_files(self, tmp_path):
        md = tmp_path / "in.md"
        md.write_text("Citing [@zech_digital-twins-as--service_2024] here.\n")
        bib = tmp_path / "bibliography.bib"
        bib.write_text(
            "@article{zech_digital-twins-as--service_2024,\n  title={T},\n}\n"
            "@article{zech_digital-twins-as--service_2024-1,\n  title={T2},\n}\n"
        )
        tmp_dir = tmp_path / "tmp"
        tmp_dir.mkdir()

        safe_md, safe_bib = render_output._safe_render_inputs(md, bib, tmp_dir)
        assert safe_md != md
        assert safe_bib != bib

        md_text = safe_md.read_text()
        assert "zech_digital-twins-as-x2d-service_2024" in md_text
        assert "--service" not in md_text

        bib_text = safe_bib.read_text()
        assert "@article{zech_digital-twins-as-x2d-service_2024," in bib_text
        # The "-1" duplicate entry must be untouched, not also aliased.
        assert "@article{zech_digital-twins-as--service_2024-1," in bib_text


class TestLocalImageRefs:
    def test_extracts_local_image_paths(self):
        text = "![alt one](figure-one.png)\n\nSome text ![alt two](sub/figure-two.svg \"a title\").\n"
        assert render_output._local_image_refs(text) == ["figure-one.png", "sub/figure-two.svg"]

    def test_skips_remote_urls_and_data_uris(self):
        text = (
            "![remote](https://example.com/figure.png)\n"
            "![inline](data:image/png;base64,AAAA)\n"
            "![local](figure.png)\n"
        )
        assert render_output._local_image_refs(text) == ["figure.png"]

    def test_no_images_returns_empty_list(self):
        assert render_output._local_image_refs("Just text, no images.\n") == []


class TestCopyLocalImages:
    def test_copies_an_existing_local_image(self, tmp_path):
        src_dir = tmp_path / "drafts"
        src_dir.mkdir()
        (src_dir / "figure.png").write_bytes(b"fake png bytes")
        draft = src_dir / "draft.md"
        draft.write_text("![alt](figure.png)\n")
        dest_dir = tmp_path / "rendered"
        dest_dir.mkdir()

        render_output._copy_local_images(draft, dest_dir)

        assert (dest_dir / "figure.png").read_bytes() == b"fake png bytes"

    def test_skips_a_reference_that_does_not_resolve_to_a_real_file(self, tmp_path):
        src_dir = tmp_path / "drafts"
        src_dir.mkdir()
        draft = src_dir / "draft.md"
        draft.write_text("![alt](does-not-exist.png)\n")
        dest_dir = tmp_path / "rendered"
        dest_dir.mkdir()

        render_output._copy_local_images(draft, dest_dir)  # must not raise

        assert list(dest_dir.iterdir()) == []

    def test_skips_absolute_and_parent_escaping_paths(self, tmp_path):
        secret = tmp_path / "secret.png"
        secret.write_bytes(b"marker")
        src_dir = tmp_path / "drafts"
        src_dir.mkdir()
        draft = src_dir / "draft.md"
        draft.write_text(f"![abs]({secret})\n\n![traversal](../secret.png)\n")
        dest_dir = tmp_path / "rendered"
        dest_dir.mkdir()

        render_output._copy_local_images(draft, dest_dir)

        assert list(dest_dir.iterdir()) == []

    def test_creates_nested_destination_directories(self, tmp_path):
        src_dir = tmp_path / "drafts"
        (src_dir / "figures").mkdir(parents=True)
        (src_dir / "figures" / "figure.png").write_bytes(b"fake png bytes")
        draft = src_dir / "draft.md"
        draft.write_text("![alt](figures/figure.png)\n")
        dest_dir = tmp_path / "rendered"
        dest_dir.mkdir()

        render_output._copy_local_images(draft, dest_dir)

        assert (dest_dir / "figures" / "figure.png").read_bytes() == b"fake png bytes"


class TestLocalTexIncludeRefs:
    def test_extracts_input_and_include_paths(self):
        text = "\\input{figures/fig1.tex}\n\nSome text \\include{figures/fig2.tex}.\n"
        assert render_output._local_tex_include_refs(text) == [
            "figures/fig1.tex", "figures/fig2.tex",
        ]

    def test_matches_inside_a_raw_latex_fenced_block_too(self):
        # #222: a bare \input line and a ```{=latex} fence around the same
        # line reach pandoc's LaTeX writer identically, so this doesn't
        # special-case the fence.
        text = "```{=latex}\n\\input{figures/fig1.tex}\n```\n"
        assert render_output._local_tex_include_refs(text) == ["figures/fig1.tex"]

    def test_no_includes_returns_empty_list(self):
        assert render_output._local_tex_include_refs("Just text, no figures.\n") == []


class TestCopyLocalTexIncludes:
    def test_copies_an_existing_local_include(self, tmp_path):
        src_dir = tmp_path / "drafts"
        src_dir.mkdir()
        (src_dir / "fig1.tex").write_text("\\begin{tikzpicture}\\end{tikzpicture}\n")
        draft = src_dir / "draft.md"
        draft.write_text("\\input{fig1.tex}\n")
        dest_dir = tmp_path / "rendered"
        dest_dir.mkdir()

        render_output._copy_local_tex_includes(draft, dest_dir)

        assert (dest_dir / "fig1.tex").read_text() == "\\begin{tikzpicture}\\end{tikzpicture}\n"

    def test_skips_a_reference_that_does_not_resolve_to_a_real_file(self, tmp_path):
        src_dir = tmp_path / "drafts"
        src_dir.mkdir()
        draft = src_dir / "draft.md"
        draft.write_text("\\input{does-not-exist.tex}\n")
        dest_dir = tmp_path / "rendered"
        dest_dir.mkdir()

        render_output._copy_local_tex_includes(draft, dest_dir)  # must not raise

        assert list(dest_dir.iterdir()) == []

    def test_skips_absolute_and_parent_escaping_paths(self, tmp_path):
        secret = tmp_path / "secret.tex"
        secret.write_text("marker")
        src_dir = tmp_path / "drafts"
        src_dir.mkdir()
        draft = src_dir / "draft.md"
        draft.write_text(f"\\input{{{secret}}}\n\n\\input{{../secret.tex}}\n")
        dest_dir = tmp_path / "rendered"
        dest_dir.mkdir()

        render_output._copy_local_tex_includes(draft, dest_dir)

        assert list(dest_dir.iterdir()) == []

    def test_creates_nested_destination_directories(self, tmp_path):
        src_dir = tmp_path / "drafts"
        (src_dir / "figures").mkdir(parents=True)
        (src_dir / "figures" / "fig1.tex").write_text("\\begin{tikzpicture}\\end{tikzpicture}\n")
        draft = src_dir / "draft.md"
        draft.write_text("\\input{figures/fig1.tex}\n")
        dest_dir = tmp_path / "rendered"
        dest_dir.mkdir()

        render_output._copy_local_tex_includes(draft, dest_dir)

        assert (dest_dir / "figures" / "fig1.tex").read_text() == "\\begin{tikzpicture}\\end{tikzpicture}\n"


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


class TestRequire:
    def test_raises_missing_binary_when_not_on_path(self, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda name: None)
        with pytest.raises(render_output.MissingBinary):
            render_output._require("some-binary-that-does-not-exist")

    def test_no_raise_when_found(self, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/" + name)
        render_output._require("pandoc")  # should not raise


class TestRenderMarkdown:
    """`--format md` on a Markdown draft, which is a citation-numbering
    job rather than a format conversion and so never calls pandoc."""

    def test_produces_plain_numbered_markdown(self, isolated_config, tmp_path, monkeypatch):
        con = ledger.connect()
        for key, title in [("b_2024", "B Paper"), ("a_2023", "A Paper")]:
            ledger.upsert_reference(con, make_reference(
                citekey=key, title=title, year="2024",
                fields={"author": "Doe, Jane", "journal": "J. Things"}))
        con.close()

        draft = content_draft(isolated_config, "draft.md")
        draft.write_text("# T\n\nOne [@b_2024]. Two [@a_2023].\n")

        # Deliberately hidden: this path must not need pandoc, so a host
        # without it still gets a readable numbered draft.
        monkeypatch.setattr(shutil, "which", lambda _: None)
        out_path = render_output.render(str(draft), output_format="md")
        text = out_path.read_text()

        assert out_path == isolated_config.RENDERED_DIR / "draft.md"
        assert "One [1]. Two [2]." in text
        # None of pandoc's Markdown-writer artifacts.
        assert "\\[" not in text, "brackets must not be escaped"
        assert ":::" not in text, "no fenced-div wrappers"
        assert "csl-" not in text, "no citeproc span classes"
        assert "[@" not in text, "no citekeys left inline"

    def test_a_citekey_missing_from_the_ledger_is_reported_not_raised(
        self, isolated_config, tmp_path, capsys, monkeypatch
    ):
        # The gate would normally catch this first, but render_output is a
        # standalone CLI -- it must not answer with a traceback.
        draft = content_draft(isolated_config, "draft.md")
        draft.write_text("Body [@never_synced_2024].\n")

        monkeypatch.setattr(sys, "argv", ["render_output.py", str(draft), "--format", "md"])
        rc = render_output.main()
        out = capsys.readouterr().out

        assert rc == 1
        assert "[error]" in out
        assert "never_synced_2024" in out

    def test_leaves_the_draft_untouched(self, isolated_config, tmp_path):
        con = ledger.connect()
        ledger.upsert_reference(con, make_reference(citekey="a_2024", title="A Paper", year="2024"))
        con.close()

        draft = content_draft(isolated_config, "draft.md")
        original = "Body [@a_2024].\n"
        draft.write_text(original)
        render_output.render(str(draft), output_format="md")

        # The draft is the gated source; only content/rendered/ is derived.
        assert draft.read_text() == original

    @pytest.mark.skipif(not pandoc_available, reason="pandoc not installed")
    def test_a_latex_input_still_goes_through_pandoc(self, isolated_config, tmp_path):
        # thesis-chapter-writer renders its .tex fragment to .md as a
        # preview: that is a real conversion, and the fragment carries
        # \citep{...} rather than [@key] and no reference list of its own.
        con = ledger.connect()
        ledger.upsert_reference(con, make_reference(citekey="a_2024", title="A Paper", year="2024"))
        con.close()
        isolated_config.BIB_FILE_PATH.write_text(
            "@article{a_2024,\n  author={Doe, Jane},\n  title={A Paper},\n  year={2024},\n}\n"
        )

        fragment = content_draft(isolated_config, "chapter.tex")
        fragment.write_text("\\section{Intro}\nA claim \\citep{a_2024}.\n")
        out_path = render_output.render(str(fragment), output_format="md")

        assert out_path == isolated_config.RENDERED_DIR / "chapter.md"
        assert "Intro" in out_path.read_text()

    def test_lands_beside_the_draft_when_the_draft_is_in_a_topic_directory(
        self, isolated_config, monkeypatch
    ):
        draft = isolated_config.DRAFTS_DIR / "dt" / "survey.md"
        draft.parent.mkdir(parents=True)
        draft.write_text("# T\n\nNo citations.\n")

        monkeypatch.setattr(shutil, "which", lambda _: None)
        out_path = render_output.render(str(draft), output_format="md")

        assert out_path == isolated_config.RENDERED_DIR / "dt" / "survey.md"

    def test_two_topics_sharing_a_stem_do_not_overwrite_each_other(
        self, isolated_config, monkeypatch
    ):
        # Flat output made this silent: both drafts rendered to
        # content/rendered/survey.md, last one wins, no warning.
        for topic, body in [("dt", "First topic.\n"), ("mde", "Second topic.\n")]:
            draft = isolated_config.DRAFTS_DIR / topic / "survey.md"
            draft.parent.mkdir(parents=True)
            draft.write_text(f"# T\n\n{body}")
            monkeypatch.setattr(shutil, "which", lambda _: None)
            render_output.render(str(draft), output_format="md")

        assert "First topic." in (isolated_config.RENDERED_DIR / "dt" / "survey.md").read_text()
        assert "Second topic." in (isolated_config.RENDERED_DIR / "mde" / "survey.md").read_text()

    def test_a_local_image_is_copied_into_the_mirrored_directory(
        self, isolated_config, monkeypatch
    ):
        # An image left behind in the flat directory would break the
        # self-containment the .tex output depends on.
        draft = isolated_config.DRAFTS_DIR / "dt" / "survey.md"
        draft.parent.mkdir(parents=True)
        (draft.parent / "figure.png").write_bytes(b"fake png bytes")
        draft.write_text("# T\n\n![A caption](figure.png)\n")

        monkeypatch.setattr(shutil, "which", lambda _: None)
        render_output.render(str(draft), output_format="md")

        copied = isolated_config.RENDERED_DIR / "dt" / "figure.png"
        assert copied.read_bytes() == b"fake png bytes"


@pytest.mark.skipif(not (pandoc_available and pdflatex_available), reason="pandoc/pdflatex not installed")
class TestRenderReal:
    def test_renders_markdown_with_citation_to_pdf(self, isolated_config, tmp_path):
        con = ledger.connect()
        ledger.upsert_reference(con, make_reference(citekey="smith_2024", title="An Example Paper", year="2024"))
        con.close()

        bib = isolated_config.BIB_FILE_PATH
        bib.write_text("@article{smith_2024,\n  title={An Example Paper},\n  year={2024},\n}\n")

        draft = content_draft(isolated_config, "draft.md")
        draft.write_text("# Title\n\nSome claim [@smith_2024].\n")

        out_path = render_output.render(str(draft), output_format="pdf")
        assert out_path.exists()
        assert out_path == isolated_config.RENDERED_DIR / "draft.pdf"

    @pytest.mark.parametrize("output_format", ["tex", "pdf"])
    def test_every_pandoc_format_lands_beside_the_draft(self, isolated_config, output_format):
        # The `md` format is covered without pandoc above; these two are
        # the ones that only ever ran through pandoc, and they flattened
        # the same way.
        isolated_config.BIB_FILE_PATH.write_text("")
        draft = isolated_config.DRAFTS_DIR / "dt" / "survey.md"
        draft.parent.mkdir(parents=True)
        draft.write_text("# Title\n\nNo citations here.\n")

        out_path = render_output.render(str(draft), output_format=output_format)

        assert out_path == isolated_config.RENDERED_DIR / "dt" / f"survey.{output_format}"
        assert out_path.exists()

    def test_renders_to_tex_replacing_a_manual_refs_section_with_citeprocs(self, isolated_config, tmp_path):
        con = ledger.connect()
        ledger.upsert_reference(con, make_reference(citekey="smith_2024", title="An Example Paper", year="2024"))
        con.close()
        isolated_config.BIB_FILE_PATH.write_text(
            "@article{smith_2024,\n  author={Smith, Jane},\n  title={An Example Paper},\n"
            "  journal={J. Examples},\n  year={2024},\n}\n"
        )

        draft = content_draft(isolated_config, "draft.md")
        draft.write_text(
            "# Title\n\nSome claim [@smith_2024].\n\n"
            "## References\n\n[1] J. Smith, \"An Example Paper,\" *J. Examples*, 2024. `smith_2024`\n"
        )
        out_path = render_output.render(str(draft), output_format="tex")
        tex = out_path.read_text()

        assert "documentclass" in tex or "article" in tex
        # The draft's own section is stripped and citeproc's numbered one
        # takes its place: exactly one bibliography, with the author and
        # journal in it, and no citekey label reaching the reader (the
        # draft's `smith_2024` code span would come through as \texttt).
        # Case-insensitively: IEEE style sentence-cases titles, so
        # citeproc's own entry reads "An example paper".
        assert tex.lower().count("an example paper") == 1, "exactly one bibliography, not two"
        assert "J. Smith" in " ".join(tex.split())
        assert "J. Examples" in " ".join(tex.split())
        assert "\\texttt" not in tex
        # The draft's own heading survives, and citeproc's bibliography
        # lands under it rather than at the end of an untitled document.
        assert "References" in tex
        assert tex.index("References") < tex.index("CSLReferences}{")

    def test_the_drafts_own_reference_heading_titles_the_rendered_bibliography(
        self, isolated_config, tmp_path
    ):
        con = ledger.connect()
        ledger.upsert_reference(con, make_reference(citekey="smith_2024", title="An Example Paper", year="2024"))
        con.close()
        isolated_config.BIB_FILE_PATH.write_text(
            "@article{smith_2024,\n  author={Smith, Jane},\n  title={An Example Paper},\n"
            "  journal={J. Examples},\n  year={2024},\n}\n"
        )

        draft = content_draft(isolated_config, "draft.md")
        draft.write_text(
            "# Title\n\nSome claim [@smith_2024].\n\n"
            "## 6. References\n\n[1] J. Smith, \"An Example Paper,\" 2024. `smith_2024`\n"
        )
        out_path = render_output.render(str(draft), output_format="html")
        text = " ".join(out_path.read_text().split())

        # The numbered heading a genre skill chose, not a generic one
        # pandoc invented, and the entries sit under it. Anchored on the
        # entry's own div id rather than "csl-entry", which also appears
        # in the standalone template's stylesheet up in <head>.
        assert "6. References" in text
        assert text.index("6. References") < text.index('id="ref-smith_2024"')

    def test_ieee_numbering_and_collapsed_runs_reach_the_output(self, isolated_config, tmp_path):
        con = ledger.connect()
        keys = [f"k{i}_2024" for i in range(1, 6)]
        for key in keys:
            ledger.upsert_reference(con, make_reference(citekey=key, title=f"Paper {key}", year="2024"))
        con.close()
        isolated_config.BIB_FILE_PATH.write_text("\n".join(
            f"@article{{{key},\n  author={{Doe, Jane}},\n  title={{Paper {key}}},\n"
            f"  journal={{J. Examples}},\n  year={{2024}},\n}}" for key in keys
        ))

        draft = content_draft(isolated_config, "draft.md")
        draft.write_text(
            "# Title\n\nOne [@k1_2024]. Another [@k2_2024].\n\n"
            "A run of four [@k2_2024; @k3_2024; @k4_2024; @k5_2024].\n"
        )
        # html rather than tex/pdf so the assertions can read the markers
        # as a reader sees them, without LaTeX's {[}1{]} escaping in the way.
        out_path = render_output.render(str(draft), output_format="html")
        # Pandoc hard-wraps its output, so a name can arrive split across
        # two lines ("J.\nDoe") -- collapse whitespace before matching.
        text = " ".join(out_path.read_text().split())

        # Numbered by first appearance, not by citekey order.
        assert 'data-cites="k1_2024">[1]</span>' in text
        assert 'data-cites="k2_2024">[2]</span>' in text
        # The collapsed form is the whole reason _collapsed_csl exists:
        # upstream ieee.csl alone renders this run as "[2], [3], [4], [5]".
        assert "[2]–[5]" in text
        assert "J. Doe" in text
        assert "J. Examples" in text

    def test_no_collapse_leaves_the_style_as_published(self, isolated_config, tmp_path):
        con = ledger.connect()
        keys = [f"k{i}_2024" for i in range(1, 4)]
        for key in keys:
            ledger.upsert_reference(con, make_reference(citekey=key, title=f"Paper {key}", year="2024"))
        con.close()
        isolated_config.BIB_FILE_PATH.write_text("\n".join(
            f"@article{{{key},\n  author={{Doe, Jane}},\n  title={{Paper {key}}},\n"
            f"  journal={{J. Examples}},\n  year={{2024}},\n}}" for key in keys
        ))

        draft = content_draft(isolated_config, "draft.md")
        draft.write_text("# Title\n\nA run [@k1_2024; @k2_2024; @k3_2024].\n")
        out_path = render_output.render(str(draft), output_format="html", collapse_citations=False)

        assert "[1], [2], [3]" in out_path.read_text()

    def test_missing_csl_style_is_reported_not_passed_to_pandoc(self, isolated_config, tmp_path):
        draft = content_draft(isolated_config, "draft.md")
        draft.write_text("# Title\n\nNo citations here.\n")
        with pytest.raises(render_output.MissingBinary, match="CSL style not found"):
            render_output.render(str(draft), output_format="tex", csl=str(tmp_path / "nope.csl"))

    def test_double_hyphen_citekey_survives_render(self, isolated_config, tmp_path):
        con = ledger.connect()
        ledger.upsert_reference(
            con, make_reference(citekey="zech_digital-twins-as--service_2024", title="Zech Paper", year="2024")
        )
        con.close()
        isolated_config.BIB_FILE_PATH.write_text(
            "@article{zech_digital-twins-as--service_2024,\n  title={Zech Paper},\n  year={2024},\n}\n"
        )

        draft = content_draft(isolated_config, "draft.md")
        draft.write_text("# Title\n\nA claim [@zech_digital-twins-as--service_2024].\n")

        out_path = render_output.render(str(draft), output_format="tex")
        assert out_path.exists()

    def test_local_image_embeds_when_input_is_a_relative_path(self, isolated_config, tmp_path, monkeypatch):
        # Regression test: pandoc resolves a draft's local image references
        # (`![...](figure.png)`) relative to pandoc's own working directory,
        # not the draft's directory -- so invoking this CLI from anywhere
        # other than the draft's own directory silently dropped the image
        # (pandoc's PDF writer falls back to the alt-text caption instead of
        # erroring) unless --resource-path is passed. monkeypatch.chdir to a
        # directory that is neither tmp_path nor its parent, matching how
        # this CLI is actually invoked (from the repo root, not
        # content/drafts/).
        con = ledger.connect()
        ledger.upsert_reference(con, make_reference(citekey="smith_2024", title="An Example Paper", year="2024"))
        con.close()
        isolated_config.BIB_FILE_PATH.write_text(
            "@article{smith_2024,\n  title={An Example Paper},\n  year={2024},\n}\n"
        )

        draft_dir = tmp_path / "content" / "drafts"
        draft_dir.mkdir(parents=True)
        draft = draft_dir / "draft.md"
        # A real, valid 1x1 PNG (built from raw chunks, not a placeholder),
        # so pandoc's PDF writer can actually decode and embed it, not just
        # find the path.
        png_bytes = bytes.fromhex(
            "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
            "0000000c49444154789c63f8cfc0000003010100c9fe92ef0000000049454e44ae"
            "426082"
        )
        (draft_dir / "figure.png").write_bytes(png_bytes)
        draft.write_text("# Title\n\n![A caption](figure.png)\n\nSome claim [@smith_2024].\n")

        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)

        out_path = render_output.render(str(draft), output_format="pdf")
        pdf_bytes = out_path.read_bytes()
        assert b"/Subtype/Image" in pdf_bytes or b"/Subtype /Image" in pdf_bytes

    def test_local_image_is_copied_to_rendered_dir_so_standalone_tex_compiles(
        self, isolated_config, tmp_path, monkeypatch
    ):
        # Regression test: rendering to `tex` only asks pandoc to emit
        # \includegraphics{figure.png} into the .tex source -- it never
        # copies the actual image file anywhere, so the standalone .tex
        # landing in content/rendered/ can't find it and fails to compile
        # on its own ("File `figure.png' not found"), even though
        # --resource-path (above) lets the *pdf* format's own pandoc-driven
        # pdflatex pass embed it correctly. A .tex a user can't compile
        # isn't a real deliverable.
        con = ledger.connect()
        ledger.upsert_reference(con, make_reference(citekey="smith_2024", title="An Example Paper", year="2024"))
        con.close()
        isolated_config.BIB_FILE_PATH.write_text(
            "@article{smith_2024,\n  title={An Example Paper},\n  year={2024},\n}\n"
        )

        draft_dir = tmp_path / "content" / "drafts"
        draft_dir.mkdir(parents=True)
        draft = draft_dir / "draft.md"
        # A real, valid 1x1 PNG (built from raw chunks, not a placeholder),
        # so pdflatex can actually decode and embed it, not just find it.
        png_bytes = bytes.fromhex(
            "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
            "0000000c49444154789c63f8cfc0000003010100c9fe92ef0000000049454e44ae"
            "426082"
        )
        (draft_dir / "figure.png").write_bytes(png_bytes)
        draft.write_text("# Title\n\n![A caption](figure.png)\n\nSome claim [@smith_2024].\n")

        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)

        out_path = render_output.render(str(draft), output_format="tex")

        copied_image = out_path.parent / "figure.png"
        assert copied_image.exists()
        assert copied_image.read_bytes() == png_bytes

        # The copied image must actually make the standalone .tex
        # compilable on its own, not just "a file happens to be present".
        compile_result = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", out_path.name],
            cwd=out_path.parent, capture_output=True, text=True,
        )
        assert compile_result.returncode == 0, compile_result.stdout[-2000:]

    def test_image_reference_outside_the_draft_directory_is_not_copied(self, isolated_config, tmp_path):
        # A `../`-escaping or absolute image path must not let a draft
        # write outside content/rendered/ -- skip it and let pandoc's own
        # missing-resource handling surface the problem, same as any other
        # image path that doesn't resolve to a real file.
        secret = tmp_path / "secret.png"
        secret.write_bytes(b"not a real png, just a marker")

        draft_dir = tmp_path / "content" / "drafts"
        draft_dir.mkdir(parents=True)
        draft = draft_dir / "draft.md"
        draft.write_text("# Title\n\n![traversal](../../secret.png)\n\nNo citations.\n")
        isolated_config.BIB_FILE_PATH.write_text("")

        render_output.render(str(draft), output_format="tex")

        assert not (isolated_config.RENDERED_DIR / "secret.png").exists()
        assert not (isolated_config.RENDERED_DIR.parent / "secret.png").exists()

    @pytest.mark.skipif(
        not (pandoc_available and pdflatex_available and tikz_available),
        reason="pandoc/pdflatex/tikz.sty not installed",
    )
    def test_a_tikz_figure_renders_to_pdf(self, isolated_config, tmp_path, monkeypatch):
        # #222: a bare tikzpicture environment fails pandoc's default LaTeX
        # template ("Environment tikzpicture undefined") without
        # \usepackage{tikz}, and \input{figures/fig1.tex} doesn't resolve
        # at all without TEXINPUTS -- render() succeeding (subprocess.run's
        # check=True would raise otherwise) is the real assertion here, not
        # a mocked call.
        isolated_config.BIB_FILE_PATH.write_text("")
        draft_dir = tmp_path / "content" / "drafts"
        (draft_dir / "figures").mkdir(parents=True)
        (draft_dir / "figures" / "fig1.tex").write_text(
            "\\begin{tikzpicture}\\draw[blue] (0,0) circle (1);\\end{tikzpicture}\n"
        )
        draft = draft_dir / "draft.md"
        draft.write_text("# Title\n\n\\input{figures/fig1.tex}\n\nNo citations.\n")

        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)

        out_path = render_output.render(str(draft), output_format="pdf")
        assert out_path.exists()
        assert out_path.stat().st_size > 0

    @pytest.mark.skipif(
        not (pandoc_available and pdflatex_available and tikz_available),
        reason="pandoc/pdflatex/tikz.sty not installed",
    )
    def test_a_tikz_figure_is_copied_so_standalone_tex_compiles(
        self, isolated_config, tmp_path, monkeypatch
    ):
        # Mirrors test_local_image_is_copied_to_rendered_dir_so_standalone_
        # tex_compiles: rendering to `tex` only asks pandoc to emit
        # \input{figures/fig1.tex} into the .tex source -- without
        # _copy_local_tex_includes the standalone .tex landing in
        # content/rendered/ can't find the figure and fails to compile on
        # its own, even though TEXINPUTS (above) lets the *pdf* format's
        # own pandoc-driven pdflatex pass find it.
        isolated_config.BIB_FILE_PATH.write_text("")
        draft_dir = tmp_path / "content" / "drafts"
        (draft_dir / "figures").mkdir(parents=True)
        fig_source = "\\begin{tikzpicture}\\draw[blue] (0,0) circle (1);\\end{tikzpicture}\n"
        (draft_dir / "figures" / "fig1.tex").write_text(fig_source)
        draft = draft_dir / "draft.md"
        draft.write_text("# Title\n\n\\input{figures/fig1.tex}\n\nNo citations.\n")

        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)

        out_path = render_output.render(str(draft), output_format="tex")

        copied_fig = out_path.parent / "figures" / "fig1.tex"
        assert copied_fig.exists()
        assert copied_fig.read_text() == fig_source

        compile_result = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", out_path.name],
            cwd=out_path.parent, capture_output=True, text=True,
        )
        assert compile_result.returncode == 0, compile_result.stdout[-2000:]

    def test_missing_binary_path(self, isolated_config, tmp_path, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda name: None)
        draft = content_draft(isolated_config, "draft.md")
        draft.write_text("No citations here.\n")
        with pytest.raises(render_output.MissingBinary):
            render_output.render(str(draft))


class TestMainCli:
    def test_missing_binary_prints_and_returns_1(self, isolated_config, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(shutil, "which", lambda name: None)
        draft = content_draft(isolated_config, "draft.md")
        draft.write_text("text\n")
        monkeypatch.setattr(sys, "argv", ["render_output.py", str(draft)])
        rc = render_output.main()
        out = capsys.readouterr().out
        assert rc == 1
        assert "[missing-binary]" in out

    @pytest.mark.skipif(not (pandoc_available and pdflatex_available), reason="pandoc/pdflatex not installed")
    def test_called_process_error_prints_and_returns_1(self, isolated_config, tmp_path, monkeypatch, capsys):
        isolated_config.BIB_FILE_PATH.write_text("")
        draft = content_draft(isolated_config, "draft.md")
        # Malformed LaTeX documentclass argument to force pandoc to fail.
        monkeypatch.setattr(sys, "argv", ["render_output.py", str(draft), "--documentclass", "this is not valid \\"])
        draft.write_text("text\n")
        rc = render_output.main()
        out = capsys.readouterr().out
        assert rc == 1
        assert "[error]" in out

    @pytest.mark.skipif(not (pandoc_available and pdflatex_available), reason="pandoc/pdflatex not installed")
    def test_success_prints_output_path_and_returns_0(self, isolated_config, tmp_path, monkeypatch, capsys):
        isolated_config.BIB_FILE_PATH.write_text("")
        draft = content_draft(isolated_config, "draft.md")
        draft.write_text("# Title\n\nNo citations here.\n")
        monkeypatch.setattr(sys, "argv", ["render_output.py", str(draft), "--format", "tex"])
        rc = render_output.main()
        out = capsys.readouterr().out
        assert rc == 0
        assert str(isolated_config.RENDERED_DIR / "draft.tex") in out


class TestInputsAreConfinedToContent:
    """#113: reading is confined to content/ too, not just writing."""

    def test_a_draft_outside_the_content_directory_is_refused(self, isolated_config, tmp_path):
        loose = tmp_path / "loose.md"
        loose.write_text("# T\n\nNo citations.\n")
        with pytest.raises(render_output.config.OutsideContentDir, match="outside the content"):
            render_output.render(str(loose), output_format="md")

    def test_a_parent_escaping_argument_is_refused(self, isolated_config):
        escaping = isolated_config.DRAFTS_DIR / ".." / ".." / "outside" / "draft.md"
        with pytest.raises(render_output.config.OutsideContentDir):
            render_output.render(str(escaping), output_format="md")

    def test_a_symlinked_draft_is_judged_by_where_it_really_lives(
        self, isolated_config, tmp_path
    ):
        # The path says content/drafts/dt/, the file is elsewhere on disk.
        real = tmp_path / "outside" / "survey.md"
        real.parent.mkdir(parents=True)
        real.write_text("# T\n")
        link_dir = isolated_config.DRAFTS_DIR / "dt"
        link_dir.mkdir(parents=True)
        (link_dir / "survey.md").symlink_to(real)

        with pytest.raises(render_output.config.OutsideContentDir):
            render_output.render(str(link_dir / "survey.md"), output_format="md")

    def test_a_draft_under_content_but_not_under_drafts_renders_flat(
        self, isolated_config, monkeypatch
    ):
        # The one remaining flat case: in-content, so accepted, but with
        # no path under content/drafts/ to mirror.
        scratch = isolated_config.CONTENT_DIR / "scratch" / "notes.md"
        scratch.parent.mkdir(parents=True)
        scratch.write_text("# T\n\nNo citations.\n")

        monkeypatch.setattr(shutil, "which", lambda _: None)
        out_path = render_output.render(str(scratch), output_format="md")

        assert out_path == isolated_config.RENDERED_DIR / "notes.md"


class TestOutputDirOverride:
    """`render(output_dir=...)` -- how src/review/__init__.py lands a report's
    renders beside the report instead of in content/rendered/."""

    def test_the_caller_s_directory_is_used_verbatim(self, isolated_config, monkeypatch):
        report = isolated_config.REVIEW_DIR / "dt" / "survey.provenance.md"
        report.parent.mkdir(parents=True)
        report.write_text("# T\n\nNo citations.\n")

        monkeypatch.setattr(shutil, "which", lambda _: None)
        out_path = render_output.render(
            str(report), output_format="md", output_dir=report.parent
        )

        # Beside the report, and nothing mirrored into it: the caller has
        # already decided the whole path.
        assert out_path == report.parent / "survey.provenance.md"

    def test_omitting_it_keeps_the_mirroring_behaviour(self, isolated_config, monkeypatch):
        draft = isolated_config.DRAFTS_DIR / "dt" / "survey.md"
        draft.parent.mkdir(parents=True)
        draft.write_text("# T\n\nNo citations.\n")

        monkeypatch.setattr(shutil, "which", lambda _: None)
        out_path = render_output.render(str(draft), output_format="md")

        assert out_path == isolated_config.RENDERED_DIR / "dt" / "survey.md"

    def test_a_directory_outside_content_is_refused(self, isolated_config, tmp_path):
        """Naming an output directory does not widen where the pipeline
        may write -- the same rule the input side has had since 3.17.0."""
        draft = isolated_config.DRAFTS_DIR / "survey.md"
        draft.parent.mkdir(parents=True)
        draft.write_text("# T\n")

        with pytest.raises(render_output.OutsideContentDir):
            render_output.render(
                str(draft), output_format="md", output_dir=tmp_path / "outside"
            )

    def test_a_parent_escaping_output_dir_is_refused(self, isolated_config):
        draft = isolated_config.DRAFTS_DIR / "survey.md"
        draft.parent.mkdir(parents=True)
        draft.write_text("# T\n")

        with pytest.raises(render_output.OutsideContentDir):
            render_output.render(
                str(draft), output_format="md",
                output_dir=isolated_config.REVIEW_DIR / ".." / ".." / "outside",
            )


# A figure is a pair of sibling files -- figures/<name>.tex holding the
# TikZ picture and figures/<name>.txt holding the same diagram in
# WRITING-STANDARDS.md §10's plain ASCII -- and each draft carries
# whichever form is native to it inline, naming the other in a marker.
ASCII_FIGURE = "  +-------+  read   +--------+\n  | model | ------> | solver |\n  +-------+         +--------+\n"
TIKZ_FIGURE = "\\begin{tikzpicture}\\draw[blue] (0,0) circle (1);\\end{tikzpicture}\n"


def figure_pair(draft_dir, name="fig1"):
    """Both halves of a figure on disk, returning the draft's directory."""
    (draft_dir / "figures").mkdir(parents=True, exist_ok=True)
    (draft_dir / "figures" / f"{name}.tex").write_text(TIKZ_FIGURE)
    (draft_dir / "figures" / f"{name}.txt").write_text(ASCII_FIGURE)
    return draft_dir


MARKED_FENCE = (
    "Before.\n\n<!-- figure: figures/fig1 -->\n\n```\n" + ASCII_FIGURE + "```\n\nAfter.\n"
)
MARKED_INPUT = "Before.\n\n\\input{figures/fig1.tex}\n%figure: figures/fig1\n\nAfter.\n"


class TestFigureRefs:
    def test_a_markdown_marker_is_a_figure_reference(self):
        # The marker is what makes the figure file visible to the copy
        # step and the \usepackage{tikz} gate, both of which read the
        # draft on disk rather than the substituted temp copy.
        assert render_output._figure_refs(MARKED_FENCE) == ["figures/fig1.tex"]

    def test_a_latex_input_is_a_figure_reference(self):
        assert render_output._figure_refs(MARKED_INPUT) == ["figures/fig1.tex"]

    def test_an_ascii_alt_marker_names_the_twin(self):
        assert render_output._ascii_alt_refs(MARKED_INPUT) == ["figures/fig1.txt"]

    def test_a_draft_with_no_figure_references_nothing(self):
        assert render_output._figure_refs("Just prose.\n") == []
        assert render_output._ascii_alt_refs("Just prose.\n") == []


class TestResolveSibling:
    def test_resolves_a_real_file_under_the_draft_directory(self, tmp_path):
        figure_pair(tmp_path)
        resolved = render_output._resolve_sibling(tmp_path, "figures/fig1.tex")
        assert resolved == tmp_path / "figures" / "fig1.tex"

    def test_refuses_absolute_and_parent_escaping_references(self, tmp_path):
        secret = tmp_path / "secret.tex"
        secret.write_text("marker")
        draft_dir = tmp_path / "drafts"
        draft_dir.mkdir()
        assert render_output._resolve_sibling(draft_dir, str(secret)) is None
        assert render_output._resolve_sibling(draft_dir, "../secret.tex") is None

    def test_returns_none_for_a_reference_that_is_not_a_file(self, tmp_path):
        assert render_output._resolve_sibling(tmp_path, "figures/absent.tex") is None


class TestSubstituteTikzForAscii:
    def test_a_marked_fence_becomes_an_input(self, tmp_path):
        figure_pair(tmp_path)
        out = render_output._substitute_tikz_for_ascii(MARKED_FENCE, tmp_path)
        assert "\\input{figures/fig1.tex}" in out
        # The fence goes too: leaving it in puts the ASCII diagram and the
        # TikZ picture in the same PDF, one under the other.
        assert "+-------+" not in out
        assert "```" not in out

    def test_a_marker_naming_a_missing_file_is_left_alone(self, tmp_path):
        out = render_output._substitute_tikz_for_ascii(MARKED_FENCE, tmp_path)
        assert out == MARKED_FENCE

    def test_a_tilde_fence_is_matched_too(self, tmp_path):
        figure_pair(tmp_path)
        text = "<!-- figure: figures/fig1 -->\n~~~\n" + ASCII_FIGURE + "~~~\n"
        assert "\\input{figures/fig1.tex}" in render_output._substitute_tikz_for_ascii(
            text, tmp_path
        )


class TestSubstituteAsciiForTikz:
    def test_an_input_with_a_twin_becomes_a_verbatim_block(self, tmp_path):
        figure_pair(tmp_path)
        out = render_output._substitute_ascii_for_tikz(MARKED_INPUT, tmp_path)
        assert "\\begin{verbatim}" in out
        assert "| model | ------> | solver |" in out
        assert "\\input{figures/fig1.tex}" not in out

    def test_a_twin_that_is_not_there_is_left_alone(self, tmp_path):
        out = render_output._substitute_ascii_for_tikz(MARKED_INPUT, tmp_path)
        assert out == MARKED_INPUT


class TestWithFiguresFor:
    def test_markdown_draft_to_pdf_takes_the_tikz_form(self, tmp_path):
        figure_pair(tmp_path)
        draft = tmp_path / "draft.md"
        out = render_output._with_figures_for(MARKED_FENCE, draft, "pdf")
        assert "\\input{figures/fig1.tex}" in out

    def test_markdown_draft_to_docx_keeps_the_ascii(self, tmp_path):
        # pandoc cannot turn a tikzpicture into a Word drawing -- it drops
        # the environment, so substituting there loses the figure entirely.
        figure_pair(tmp_path)
        draft = tmp_path / "draft.md"
        assert render_output._with_figures_for(MARKED_FENCE, draft, "docx") == MARKED_FENCE

    def test_latex_draft_to_md_takes_the_ascii_form(self, tmp_path):
        figure_pair(tmp_path)
        draft = tmp_path / "draft.tex"
        out = render_output._with_figures_for(MARKED_INPUT, draft, "md")
        assert "\\begin{verbatim}" in out

    def test_latex_draft_to_pdf_keeps_its_input(self, tmp_path):
        figure_pair(tmp_path)
        draft = tmp_path / "draft.tex"
        assert render_output._with_figures_for(MARKED_INPUT, draft, "pdf") == MARKED_INPUT


class TestFigureHasCitekey:
    def test_detects_a_pandoc_citekey(self, tmp_path):
        fig = tmp_path / "fig.tex"
        fig.write_text("\\node {see [@smith_thing_2020]};\n")
        assert render_output._figure_has_citekey(fig) is True

    def test_detects_a_latex_cite(self, tmp_path):
        fig = tmp_path / "fig.tex"
        fig.write_text("\\node {see \\citep{smith_thing_2020}};\n")
        assert render_output._figure_has_citekey(fig) is True

    def test_a_clean_figure_has_none(self, tmp_path):
        fig = tmp_path / "fig.tex"
        fig.write_text(TIKZ_FIGURE)
        assert render_output._figure_has_citekey(fig) is False


class TestFigureWarnings:
    def test_a_clean_markdown_pair_warns_about_nothing(self, tmp_path):
        figure_pair(tmp_path)
        draft = tmp_path / "draft.md"
        assert render_output._figure_warnings(MARKED_FENCE, draft) == []

    def test_a_clean_latex_pair_warns_about_nothing(self, tmp_path):
        figure_pair(tmp_path)
        draft = tmp_path / "draft.tex"
        assert render_output._figure_warnings(MARKED_INPUT, draft) == []

    def test_the_wrong_marker_for_the_draft_language_is_flagged(self, tmp_path):
        figure_pair(tmp_path)
        draft = tmp_path / "draft.md"
        warnings = render_output._figure_warnings(MARKED_INPUT, draft)
        assert any("wrong kind for a Markdown draft" in w for w in warnings)

    def test_a_missing_figure_file_is_flagged(self, tmp_path):
        draft = tmp_path / "draft.md"
        warnings = render_output._figure_warnings(MARKED_FENCE, draft)
        assert any("not a readable file" in w for w in warnings)

    def test_a_citekey_in_a_figure_file_is_flagged(self, tmp_path):
        figure_pair(tmp_path)
        (tmp_path / "figures" / "fig1.tex").write_text("\\citep{smith_thing_2020}\n")
        draft = tmp_path / "draft.md"
        warnings = render_output._figure_warnings(MARKED_FENCE, draft)
        # The gate does not follow \input, so a citekey here is ungated --
        # forbidden by convention, warned about, deliberately not gated.
        assert any("ungated" in w for w in warnings)

    def test_an_input_with_no_ascii_twin_is_flagged(self, tmp_path):
        figure_pair(tmp_path)
        draft = tmp_path / "draft.tex"
        warnings = render_output._figure_warnings("\\input{figures/fig1.tex}\n", draft)
        assert any("no `%figure:` marker" in w for w in warnings)


class TestRequireTikz:
    def test_says_nothing_when_kpsewhich_is_absent(self, monkeypatch):
        # Cannot be probed, so it is not guessed: a TeX installation that
        # ships its own tooling would otherwise be refused a render.
        monkeypatch.setattr(shutil, "which", lambda name: None)
        render_output._require_tikz()

    def test_raises_when_the_probe_reports_tikz_missing(self, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/kpsewhich")
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **k: subprocess.CompletedProcess(a[0] if a else [], 1, b"", b""),
        )
        with pytest.raises(render_output.MissingBinary, match="texlive-pictures"):
            render_output._require_tikz()

    def test_says_nothing_when_the_probe_finds_tikz(self, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/kpsewhich")
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **k: subprocess.CompletedProcess(a[0] if a else [], 0, b"ok", b""),
        )
        render_output._require_tikz()


class TestCopyLocalTexIncludesFollowsMarkers:
    def test_a_markdown_marker_gets_its_figure_copied(self, tmp_path):
        # Without this the standalone .tex in content/rendered/ emits an
        # \input for a file that was never copied beside it, and fails to
        # compile on its own -- the exact regression #226's own copy test
        # exists to catch, reintroduced through the marker path.
        figure_pair(tmp_path)
        draft = tmp_path / "draft.md"
        draft.write_text(MARKED_FENCE)
        dest = tmp_path / "rendered"
        dest.mkdir()

        render_output._copy_local_tex_includes(draft, dest)

        assert (dest / "figures" / "fig1.tex").read_text() == TIKZ_FIGURE


class TestFigurePairRenderReal:
    """Both directions through the real toolchain, no mocking: the whole
    point of the pair is that each output format gets the form it can
    actually draw, and only a real render proves that."""

    @pytest.mark.skipif(
        not (pandoc_available and pdflatex_available and tikz_available),
        reason="pandoc/pdflatex/tikz.sty not installed",
    )
    def test_a_markdown_draft_renders_tikz_to_pdf(self, isolated_config, tmp_path, monkeypatch):
        isolated_config.BIB_FILE_PATH.write_text("")
        draft_dir = tmp_path / "content" / "drafts" / "dt"
        draft_dir.mkdir(parents=True)
        figure_pair(draft_dir)
        draft = draft_dir / "tutorial.md"
        draft.write_text("# Title\n\n" + MARKED_FENCE)
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)

        out_path = render_output.render(str(draft), output_format="pdf")

        assert out_path.exists()
        assert out_path.stat().st_size > 0

    @pytest.mark.skipif(
        not (pandoc_available and pdflatex_available and tikz_available),
        reason="pandoc/pdflatex/tikz.sty not installed",
    )
    def test_a_markdown_drafts_standalone_tex_compiles_on_its_own(
        self, isolated_config, tmp_path, monkeypatch
    ):
        isolated_config.BIB_FILE_PATH.write_text("")
        draft_dir = tmp_path / "content" / "drafts" / "dt"
        draft_dir.mkdir(parents=True)
        figure_pair(draft_dir)
        draft = draft_dir / "tutorial.md"
        draft.write_text("# Title\n\n" + MARKED_FENCE)
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)

        out_path = render_output.render(str(draft), output_format="tex")

        source = out_path.read_text()
        assert "\\input{figures/fig1.tex}" in source
        assert "| model | ------> | solver |" not in source
        assert (out_path.parent / "figures" / "fig1.tex").exists()
        compiled = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", out_path.name],
            cwd=out_path.parent, capture_output=True, text=True,
        )
        assert compiled.returncode == 0, compiled.stdout[-2000:]

    @pytest.mark.skipif(
        not pandoc_available, reason="pandoc not installed",
    )
    def test_a_tex_fragment_renders_its_ascii_twin_to_md(
        self, isolated_config, tmp_path, monkeypatch
    ):
        # The row this whole feature exists for: pandoc resolves the
        # \input but drops the tikzpicture, so without the substitution
        # the .md preview shows no figure at all.
        isolated_config.BIB_FILE_PATH.write_text("")
        draft_dir = tmp_path / "content" / "drafts" / "dt"
        draft_dir.mkdir(parents=True)
        figure_pair(draft_dir)
        draft = draft_dir / "chapter.tex"
        draft.write_text("\\section{Title}\n\n" + MARKED_INPUT)
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)

        out_path = render_output.render(str(draft), output_format="md")

        rendered = out_path.read_text()
        assert "| model | ------> | solver |" in rendered

    def test_a_markdown_draft_to_md_keeps_its_ascii_fence(self, isolated_config, tmp_path):
        # No pandoc on this path at all, so the fence passes straight
        # through and the marker stays as an invisible HTML comment.
        isolated_config.BIB_FILE_PATH.write_text("")
        draft_dir = isolated_config.DRAFTS_DIR / "dt"
        draft_dir.mkdir(parents=True)
        figure_pair(draft_dir)
        draft = draft_dir / "tutorial.md"
        draft.write_text("# Title\n\n" + MARKED_FENCE)

        out_path = render_output.render(str(draft), output_format="md")

        assert "| model | ------> | solver |" in out_path.read_text()

    def test_a_figure_problem_is_warned_about_not_raised(
        self, isolated_config, tmp_path, capsys
    ):
        isolated_config.BIB_FILE_PATH.write_text("")
        draft_dir = isolated_config.DRAFTS_DIR / "dt"
        draft_dir.mkdir(parents=True)
        draft = draft_dir / "tutorial.md"
        draft.write_text("# Title\n\n" + MARKED_FENCE)

        out_path = render_output.render(str(draft), output_format="md")

        assert out_path.exists()
        assert "[figure]" in capsys.readouterr().err


class TestFigureRepairHint:
    """A malformed TikZ figure fails the whole pdf, and pdflatex's error
    names a file without saying what to do about it."""

    def test_names_the_figure_and_points_at_draft_reviser(self, tmp_path):
        draft = tmp_path / "draft.md"
        draft.write_text(MARKED_FENCE)
        hint = render_output._cli._figure_repair_hint(str(draft))
        assert "figures/fig1.tex" in hint
        assert "draft-reviser" in hint

    def test_a_draft_with_no_figure_gets_no_hint(self, tmp_path):
        # An unrelated pandoc failure must not send the user chasing a
        # figure that isn't there.
        draft = tmp_path / "draft.md"
        draft.write_text("# Title\n\nJust prose.\n")
        assert render_output._cli._figure_repair_hint(str(draft)) == ""

    def test_an_unreadable_input_gets_no_hint(self, tmp_path):
        assert render_output._cli._figure_repair_hint(str(tmp_path / "absent.md")) == ""
