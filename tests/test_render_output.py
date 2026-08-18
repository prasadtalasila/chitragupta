"""src/render_output/__init__.py: render() itself, end to end.

Split from one test module to mirror `src/render_output/`'s own split,
the way `tests/test_enrich_*.py` mirrors `src/enrich/`. Shared setup --
the binary probes and the figure fixtures -- lives in `tests/conftest.py`
so the eight modules do not each re-run a `kpsewhich` subprocess at
import.
"""

import shutil
import subprocess
import sys
import pytest
from src import ledger
from src import render_output
from tests.conftest import content_draft
from tests.conftest import make_reference
from tests.conftest import ASCII_FIGURE, MARKED_MD, MARKED_INPUT, TIKZ_FIGURE, figure_pair
from tests.conftest import pandoc_available, pdflatex_available, tikz_available


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
        draft.write_text("# Title\n\n" + MARKED_MD)
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
        draft.write_text("# Title\n\n" + MARKED_MD)
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

    def test_a_markdown_draft_to_md_takes_the_ascii_form(self, isolated_config, tmp_path):
        # No pandoc on this path at all -- render()'s early return never
        # reaches the substitution `_safe_render_inputs` normally threads
        # in, so this is the one place that has to inject the figure
        # itself before writing the numbered copy.
        isolated_config.BIB_FILE_PATH.write_text("")
        draft_dir = isolated_config.DRAFTS_DIR / "dt"
        draft_dir.mkdir(parents=True)
        figure_pair(draft_dir)
        draft = draft_dir / "tutorial.md"
        draft.write_text("# Title\n\n" + MARKED_MD)

        out_path = render_output.render(str(draft), output_format="md")

        rendered = out_path.read_text()
        assert "| model | ------> | solver |" in rendered
        assert "<!-- figure:" not in rendered

    def test_a_figure_problem_is_warned_about_not_raised(
        self, isolated_config, tmp_path, capsys
    ):
        isolated_config.BIB_FILE_PATH.write_text("")
        draft_dir = isolated_config.DRAFTS_DIR / "dt"
        draft_dir.mkdir(parents=True)
        draft = draft_dir / "tutorial.md"
        draft.write_text("# Title\n\n" + MARKED_MD)

        out_path = render_output.render(str(draft), output_format="md")

        assert out_path.exists()
        assert "[figure]" in capsys.readouterr().err
