import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
import pytest
from chitragupta import ledger
from chitragupta import render_output
from tests.conftest import content_draft, pdf_text
from tests.conftest import (
    add_citable,
    CAPTIONED_MD,
    MARKED_MD,
    MARKED_INPUT,
    figure_pair,
)
from tests.conftest import (
    lualatex_available,
    pandoc_available,
    pdflatex_available,
    pdftotext_available,
    tikz_available,
)


@pytest.mark.usefixtures("programs_on_path")
class TestRunPandoc:
    def _fake_completed(self, stdout="", stderr=""):
        return subprocess.CompletedProcess(
            args=["pandoc"], returncode=0, stdout=stdout, stderr=stderr
        )

    def test_forwards_stderr_on_a_successful_exit(self, monkeypatch, capsys):
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **k: self._fake_completed(
                stderr="[WARNING] Citeproc: citation X not found\n"
            ),
        )
        render_output._run_pandoc(["pandoc"], {})
        err = capsys.readouterr().err
        assert "[pandoc] [WARNING] Citeproc: citation X not found" in err

    def test_multiple_stderr_lines_are_each_prefixed(self, monkeypatch, capsys):
        monkeypatch.setattr(
            subprocess, "run", lambda *a, **k: self._fake_completed(stderr="line one\nline two\n")
        )
        render_output._run_pandoc(["pandoc"], {})
        err = capsys.readouterr().err
        assert "[pandoc] line one" in err
        assert "[pandoc] line two" in err

    def test_empty_stderr_prints_nothing(self, monkeypatch, capsys):
        monkeypatch.setattr(subprocess, "run", lambda *a, **k: self._fake_completed(stderr=""))
        render_output._run_pandoc(["pandoc"], {})
        assert capsys.readouterr().err == ""

    def test_a_nonzero_exit_still_raises(self, monkeypatch):
        def fake_run(*a, **k):
            raise subprocess.CalledProcessError(1, ["pandoc"], stderr="fatal error")

        monkeypatch.setattr(subprocess, "run", fake_run)
        with pytest.raises(subprocess.CalledProcessError):
            render_output._run_pandoc(["pandoc"], {})

    def test_pandoc_and_its_engine_are_launched_by_absolute_path(self, monkeypatch, tmp_path):
        launched = []
        pdf = tmp_path / "out.pdf"
        pdf.write_bytes(b"")

        def fake_run(argv, **kwargs):  # pylint: disable=unused-argument
            launched.append(argv)
            return self._fake_completed()

        monkeypatch.setattr(subprocess, "run", fake_run)
        render_output._run_pandoc(
            ["pandoc", "in.md", "--pdf-engine", "lualatex", "-o", str(pdf)], {}
        )
        assert launched == [
            ["/usr/bin/pandoc", "in.md", "--pdf-engine", "/usr/bin/lualatex", "-o", str(pdf)]
        ]


class TestRenderMarkdown:
    def test_produces_plain_numbered_markdown(self, isolated_config, tmp_path, monkeypatch):
        con = ledger.connect()
        for key, title in [("b_2024", "B Paper"), ("a_2023", "A Paper")]:
            add_citable(
                con,
                key,
                title=title,
                year="2024",
                fields={"author": "Doe, Jane", "journal": "J. Things"},
            )
        con.close()

        draft = content_draft(isolated_config, "draft.md")
        draft.write_text("# T\n\nOne [@b_2024]. Two [@a_2023].\n")

        monkeypatch.setattr(shutil, "which", lambda _: None)
        out_path = render_output.render(str(draft), output_format="md")
        text = out_path.read_text()

        assert out_path == isolated_config.RENDERED_DIR / "draft.md"
        assert "One [1]. Two [2]." in text
        assert "\\[" not in text, "brackets must not be escaped"
        assert ":::" not in text, "no fenced-div wrappers"
        assert "csl-" not in text, "no citeproc span classes"
        assert "[@" not in text, "no citekeys left inline"

    def test_a_citekey_missing_from_the_ledger_is_reported_not_raised(
        self, isolated_config, ledger_con, tmp_path, capsys, monkeypatch
    ):
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
        add_citable(con, "a_2024", title="A Paper", year="2024")
        con.close()

        draft = content_draft(isolated_config, "draft.md")
        original = "Body [@a_2024].\n"
        draft.write_text(original)
        render_output.render(str(draft), output_format="md")

        assert draft.read_text() == original

    @pytest.mark.skipif(not pandoc_available, reason="pandoc not installed")
    def test_a_latex_input_still_goes_through_pandoc(self, isolated_config, tmp_path):
        con = ledger.connect()
        add_citable(con, "a_2024", title="A Paper", year="2024")
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
        draft = isolated_config.DRAFTS_DIR / "dt" / "survey.md"
        draft.parent.mkdir(parents=True)
        (draft.parent / "figure.png").write_bytes(b"fake png bytes")
        draft.write_text("# T\n\n![A caption](figure.png)\n")

        monkeypatch.setattr(shutil, "which", lambda _: None)
        render_output.render(str(draft), output_format="md")

        copied = isolated_config.RENDERED_DIR / "dt" / "figure.png"
        assert copied.read_bytes() == b"fake png bytes"


@pytest.mark.skipif(
    not (pandoc_available and lualatex_available), reason="pandoc/lualatex not installed"
)
class TestRenderReal:
    @pytest.mark.slow
    def test_renders_markdown_with_citation_to_pdf(self, isolated_config, tmp_path):
        con = ledger.connect()
        add_citable(con, "smith_2024", title="An Example Paper", year="2024")
        con.close()

        bib = isolated_config.BIB_FILE_PATH
        bib.write_text("@article{smith_2024,\n  title={An Example Paper},\n  year={2024},\n}\n")

        draft = content_draft(isolated_config, "draft.md")
        draft.write_text("# Title\n\nSome claim [@smith_2024].\n")

        out_path = render_output.render(str(draft), output_format="pdf")
        assert out_path.exists()
        assert out_path == isolated_config.RENDERED_DIR / "draft.pdf"

    @pytest.mark.slow
    def test_a_bib_field_cannot_make_the_engine_read_outside_the_draft(
        self, isolated_config, tmp_path
    ):
        secret = tmp_path / "outside" / "secret.txt"
        secret.parent.mkdir()
        secret.write_text("NOT-FOR-THE-PDF\n")
        con = ledger.connect()
        add_citable(con, "smith_2024", title="An Example Paper", year="2024")
        con.close()
        isolated_config.BIB_FILE_PATH.write_text(
            "@article{smith_2024,\n"
            f"  title={{See \\input{{{secret}}} here}},\n"
            "  year={2024},\n}\n"
        )
        draft = content_draft(isolated_config, "draft.md")
        draft.write_text("# Title\n\nSome claim [@smith_2024].\n")

        pdf = render_output.render(str(draft), output_format="pdf")

        text = pdf_text(pdf)
        assert "NOT-FOR-THE-PDF" not in text
        assert "\\input{" in text

    @pytest.mark.slow
    def test_tex_in_the_draft_still_cannot_input_a_file_outside_it(self, isolated_config, tmp_path):
        secret = tmp_path / "outside" / "secret.txt"
        secret.parent.mkdir()
        secret.write_text("NOT-FOR-THE-PDF\n")
        isolated_config.BIB_FILE_PATH.write_text("")
        draft = content_draft(isolated_config, "draft.md")
        draft.write_text(f"# Title\n\n```{{=latex}}\n\\input{{{secret}}}\n```\n")

        with pytest.raises(subprocess.CalledProcessError) as raised:
            render_output.render(str(draft), output_format="pdf")

        assert f"I can't find file `{secret}" in raised.value.stderr
        assert not (isolated_config.RENDERED_DIR / "draft.pdf").exists()

    def test_a_dotted_tmpdir_is_reported_not_run_into(self, isolated_config, tmp_path, monkeypatch):
        dotted = tmp_path / ".cache" / "tmp"
        dotted.mkdir(parents=True)
        monkeypatch.setenv("TMPDIR", str(dotted))
        monkeypatch.setattr(tempfile, "tempdir", None)
        isolated_config.BIB_FILE_PATH.write_text("")
        draft = content_draft(isolated_config, "draft.md")
        draft.write_text("# Title\n\nNo citations here.\n")

        with pytest.raises(render_output.MissingBinary, match="TMPDIR"):
            render_output.render(str(draft), output_format="pdf")

    @pytest.mark.slow
    @pytest.mark.parametrize("output_format", ["tex", "pdf"])
    def test_every_pandoc_format_lands_beside_the_draft(self, isolated_config, output_format):
        isolated_config.BIB_FILE_PATH.write_text("")
        draft = isolated_config.DRAFTS_DIR / "dt" / "survey.md"
        draft.parent.mkdir(parents=True)
        draft.write_text("# Title\n\nNo citations here.\n")

        out_path = render_output.render(str(draft), output_format=output_format)

        assert out_path == isolated_config.RENDERED_DIR / "dt" / f"survey.{output_format}"
        assert out_path.exists()

    def test_renders_to_tex_replacing_a_manual_refs_section_with_citeprocs(
        self, isolated_config, tmp_path
    ):
        con = ledger.connect()
        add_citable(con, "smith_2024", title="An Example Paper", year="2024")
        con.close()
        isolated_config.BIB_FILE_PATH.write_text(
            "@article{smith_2024,\n  author={Smith, Jane},\n  title={An Example Paper},\n"
            "  journal={J. Examples},\n  year={2024},\n}\n"
        )

        draft = content_draft(isolated_config, "draft.md")
        draft.write_text(
            "# Title\n\nSome claim [@smith_2024].\n\n"
            '## References\n\n[1] J. Smith, "An Example Paper," *J. Examples*, 2024. `smith_2024`\n'
        )
        out_path = render_output.render(str(draft), output_format="tex")
        tex = out_path.read_text()

        assert "documentclass" in tex or "article" in tex
        assert tex.lower().count("an example paper") == 1, "exactly one bibliography, not two"
        assert "J. Smith" in " ".join(tex.split())
        assert "J. Examples" in " ".join(tex.split())
        assert "\\texttt" not in tex
        assert "References" in tex
        assert tex.index("References") < tex.index("CSLReferences}{")

    def test_the_drafts_own_reference_heading_titles_the_rendered_bibliography(
        self, isolated_config, tmp_path
    ):
        con = ledger.connect()
        add_citable(con, "smith_2024", title="An Example Paper", year="2024")
        con.close()
        isolated_config.BIB_FILE_PATH.write_text(
            "@article{smith_2024,\n  author={Smith, Jane},\n  title={An Example Paper},\n"
            "  journal={J. Examples},\n  year={2024},\n}\n"
        )

        draft = content_draft(isolated_config, "draft.md")
        draft.write_text(
            "# Title\n\nSome claim [@smith_2024].\n\n"
            '## 6. References\n\n[1] J. Smith, "An Example Paper," 2024. `smith_2024`\n'
        )
        out_path = render_output.render(str(draft), output_format="html")
        text = " ".join(out_path.read_text().split())

        assert "6. References" in text
        assert text.index("6. References") < text.index('id="ref-smith_2024"')

    def test_ieee_numbering_and_collapsed_runs_reach_the_output(self, isolated_config, tmp_path):
        con = ledger.connect()
        keys = [f"k{i}_2024" for i in range(1, 6)]
        for key in keys:
            add_citable(con, key, title=f"Paper {key}", year="2024")
        con.close()
        isolated_config.BIB_FILE_PATH.write_text(
            "\n".join(
                f"@article{{{key},\n  author={{Doe, Jane}},\n  title={{Paper {key}}},\n"
                f"  journal={{J. Examples}},\n  year={{2024}},\n}}"
                for key in keys
            )
        )

        draft = content_draft(isolated_config, "draft.md")
        draft.write_text(
            "# Title\n\nOne [@k1_2024]. Another [@k2_2024].\n\n"
            "A run of four [@k2_2024; @k3_2024; @k4_2024; @k5_2024].\n"
        )
        out_path = render_output.render(str(draft), output_format="html")
        text = " ".join(out_path.read_text().split())

        assert 'data-cites="k1_2024">[1]</span>' in text
        assert 'data-cites="k2_2024">[2]</span>' in text
        assert "[2]–[5]" in text
        assert "J. Doe" in text
        assert "J. Examples" in text

    def test_no_collapse_leaves_the_style_as_published(self, isolated_config, tmp_path):
        con = ledger.connect()
        keys = [f"k{i}_2024" for i in range(1, 4)]
        for key in keys:
            add_citable(con, key, title=f"Paper {key}", year="2024")
        con.close()
        isolated_config.BIB_FILE_PATH.write_text(
            "\n".join(
                f"@article{{{key},\n  author={{Doe, Jane}},\n  title={{Paper {key}}},\n"
                f"  journal={{J. Examples}},\n  year={{2024}},\n}}"
                for key in keys
            )
        )

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
        add_citable(con, "zech_digital-twins-as--service_2024", title="Zech Paper", year="2024")
        con.close()
        isolated_config.BIB_FILE_PATH.write_text(
            "@article{zech_digital-twins-as--service_2024,\n"
            "  title={Zech Paper},\n  year={2024},\n}\n"
        )

        draft = content_draft(isolated_config, "draft.md")
        draft.write_text("# Title\n\nA claim [@zech_digital-twins-as--service_2024].\n")

        out_path = render_output.render(str(draft), output_format="tex")
        assert out_path.exists()

    @pytest.mark.slow
    def test_local_image_embeds_when_input_is_a_relative_path(
        self, isolated_config, tmp_path, monkeypatch
    ):
        con = ledger.connect()
        add_citable(con, "smith_2024", title="An Example Paper", year="2024")
        con.close()
        isolated_config.BIB_FILE_PATH.write_text(
            "@article{smith_2024,\n  title={An Example Paper},\n  year={2024},\n}\n"
        )

        draft_dir = tmp_path / "content" / "drafts"
        draft_dir.mkdir(parents=True)
        draft = draft_dir / "draft.md"
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
        con = ledger.connect()
        add_citable(con, "smith_2024", title="An Example Paper", year="2024")
        con.close()
        isolated_config.BIB_FILE_PATH.write_text(
            "@article{smith_2024,\n  title={An Example Paper},\n  year={2024},\n}\n"
        )

        draft_dir = tmp_path / "content" / "drafts"
        draft_dir.mkdir(parents=True)
        draft = draft_dir / "draft.md"
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

        compile_result = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", out_path.name],
            cwd=out_path.parent,
            capture_output=True,
            text=True,
        )
        assert compile_result.returncode == 0, compile_result.stdout[-2000:]

    def test_image_reference_outside_the_draft_directory_is_not_copied(
        self, isolated_config, tmp_path
    ):
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

    @pytest.mark.slow
    @pytest.mark.skipif(
        not (pandoc_available and lualatex_available and tikz_available),
        reason="pandoc/lualatex/tikz.sty not installed",
    )
    def test_a_tikz_figure_renders_to_pdf(self, isolated_config, tmp_path, monkeypatch):
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
            cwd=out_path.parent,
            capture_output=True,
            text=True,
        )
        assert compile_result.returncode == 0, compile_result.stdout[-2000:]

    def test_missing_binary_path(self, isolated_config, tmp_path, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda name: None)
        draft = content_draft(isolated_config, "draft.md")
        draft.write_text("No citations here.\n")
        with pytest.raises(render_output.MissingBinary):
            render_output.render(str(draft))


class TestInputsAreConfinedToContent:
    def test_a_draft_outside_the_content_directory_is_refused(self, isolated_config, tmp_path):
        loose = tmp_path / "loose.md"
        loose.write_text("# T\n\nNo citations.\n")
        with pytest.raises(render_output.config.OutsideContentDir, match="outside the content"):
            render_output.render(str(loose), output_format="md")

    def test_a_parent_escaping_argument_is_refused(self, isolated_config):
        escaping = isolated_config.DRAFTS_DIR / ".." / ".." / "outside" / "draft.md"
        with pytest.raises(render_output.config.OutsideContentDir):
            render_output.render(str(escaping), output_format="md")

    def test_a_symlinked_draft_is_judged_by_where_it_really_lives(self, isolated_config, tmp_path):
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
        scratch = isolated_config.CONTENT_DIR / "scratch" / "notes.md"
        scratch.parent.mkdir(parents=True)
        scratch.write_text("# T\n\nNo citations.\n")

        monkeypatch.setattr(shutil, "which", lambda _: None)
        out_path = render_output.render(str(scratch), output_format="md")

        assert out_path == isolated_config.RENDERED_DIR / "notes.md"


class TestOutputDirOverride:
    def test_the_caller_s_directory_is_used_verbatim(self, isolated_config, monkeypatch):
        report = isolated_config.REVIEW_DIR / "dt" / "survey.provenance.md"
        report.parent.mkdir(parents=True)
        report.write_text("# T\n\nNo citations.\n")

        monkeypatch.setattr(shutil, "which", lambda _: None)
        out_path = render_output.render(str(report), output_format="md", output_dir=report.parent)

        assert out_path == report.parent / "survey.provenance.md"

    def test_omitting_it_keeps_the_mirroring_behaviour(self, isolated_config, monkeypatch):
        draft = isolated_config.DRAFTS_DIR / "dt" / "survey.md"
        draft.parent.mkdir(parents=True)
        draft.write_text("# T\n\nNo citations.\n")

        monkeypatch.setattr(shutil, "which", lambda _: None)
        out_path = render_output.render(str(draft), output_format="md")

        assert out_path == isolated_config.RENDERED_DIR / "dt" / "survey.md"

    def test_a_directory_outside_content_is_refused(self, isolated_config, tmp_path):
        draft = isolated_config.DRAFTS_DIR / "survey.md"
        draft.parent.mkdir(parents=True)
        draft.write_text("# T\n")

        with pytest.raises(render_output.OutsideContentDir):
            render_output.render(str(draft), output_format="md", output_dir=tmp_path / "outside")

    def test_a_parent_escaping_output_dir_is_refused(self, isolated_config):
        draft = isolated_config.DRAFTS_DIR / "survey.md"
        draft.parent.mkdir(parents=True)
        draft.write_text("# T\n")

        with pytest.raises(render_output.OutsideContentDir):
            render_output.render(
                str(draft),
                output_format="md",
                output_dir=isolated_config.REVIEW_DIR / ".." / ".." / "outside",
            )


class TestFigurePairRenderReal:
    @pytest.mark.slow
    @pytest.mark.skipif(
        not (pandoc_available and lualatex_available and tikz_available),
        reason="pandoc/lualatex/tikz.sty not installed",
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
            cwd=out_path.parent,
            capture_output=True,
            text=True,
        )
        assert compiled.returncode == 0, compiled.stdout[-2000:]

    @pytest.mark.skipif(
        not pandoc_available,
        reason="pandoc not installed",
    )
    def test_a_tex_fragment_renders_its_ascii_twin_to_md(
        self, isolated_config, tmp_path, monkeypatch
    ):
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

    def test_a_figure_problem_is_warned_about_not_raised(self, isolated_config, tmp_path, capsys):
        isolated_config.BIB_FILE_PATH.write_text("")
        draft_dir = isolated_config.DRAFTS_DIR / "dt"
        draft_dir.mkdir(parents=True)
        draft = draft_dir / "tutorial.md"
        draft.write_text("# Title\n\n" + MARKED_MD)

        out_path = render_output.render(str(draft), output_format="md")

        assert out_path.exists()
        assert "[figure]" in capsys.readouterr().err


class TestBreakableInlineCode:
    _LONG_CODE = "https://github.com/INTO-CPS-Association/plant-controller"
    _HEADING_CODE = "update_schedule"
    _QUOTED_CODE = "--format='json'"

    def _draft_text(self):
        return (
            f"# The `{self._HEADING_CODE}` guard\n\n"
            f"Run `{self._QUOTED_CODE}`.\n\n"
            f"Before Chapter 2, see `{self._LONG_CODE}`.\n"
        )

    @pytest.mark.skipif(not pandoc_available, reason="pandoc not installed")
    def test_the_rendered_tex_has_break_points_not_a_bare_span(self, isolated_config, tmp_path):
        isolated_config.BIB_FILE_PATH.write_text("")
        draft = content_draft(isolated_config, "draft.md")
        draft.write_text(self._draft_text())

        out_path = render_output.render(str(draft), output_format="tex")

        source = out_path.read_text()
        assert f"\\texttt{{{self._LONG_CODE}}}" not in source
        assert f"\\texttt{{{self._HEADING_CODE}}}" not in source
        assert "\\penalty0" in source
        assert "\\textquotesingle{}json\\textquotesingle{}" in source
        assert "{The update\\_schedule guard}" in source

    @pytest.mark.skipif(
        not (pandoc_available and pdflatex_available),
        reason="pandoc/pdflatex not installed",
    )
    def test_a_markdown_drafts_long_code_span_compiles(
        self, isolated_config, tmp_path, monkeypatch
    ):
        isolated_config.BIB_FILE_PATH.write_text("")
        draft_dir = tmp_path / "content" / "drafts" / "dt"
        draft_dir.mkdir(parents=True)
        draft = draft_dir / "tutorial.md"
        draft.write_text(self._draft_text())
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)

        out_path = render_output.render(str(draft), output_format="tex")

        compiled = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", out_path.name],
            cwd=out_path.parent,
            capture_output=True,
            text=True,
        )
        assert compiled.returncode == 0, compiled.stdout[-2000:]


class TestWideCodeBlockRenderReal:
    _WIDE = "GET /sensing/{unit}/{parameter}   measurements, with limit and since_timestamp too"

    @pytest.mark.skipif(
        not (pandoc_available and pdflatex_available),
        reason="pandoc/pdflatex not installed",
    )
    def test_an_over_wide_fenced_line_wraps_instead_of_overflowing(
        self, isolated_config, tmp_path, monkeypatch
    ):
        isolated_config.BIB_FILE_PATH.write_text("")
        draft_dir = tmp_path / "content" / "drafts" / "dt"
        draft_dir.mkdir(parents=True)
        draft = draft_dir / "tutorial.md"
        draft.write_text(f"# Title\n\n```\n{self._WIDE}\n```\n")
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)

        out_path = render_output.render(str(draft), output_format="tex")

        assert "fvextra" in out_path.read_text()
        compiled = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", out_path.name],
            cwd=out_path.parent,
            capture_output=True,
            text=True,
        )
        assert compiled.returncode == 0, compiled.stdout[-2000:]
        assert "Overfull \\hbox" not in compiled.stdout


@pytest.mark.slow
class TestWideTableCaptionRenderReal:
    _CAPTION = (
        "A rather long caption that should really span the whole width of the "
        "text block on the page, not merely the four inches longtable defaults to."
    )
    _TABLE = (
        "| Starting point | Core idea |\n"
        "|---|---|\n"
        "| DTaaS | One tenant-facing platform |\n"
        "\n"
        f": {_CAPTION}\n"
        "<!-- table: start-here -->\n"
    )

    @pytest.mark.skipif(
        not (pandoc_available and lualatex_available and pdftotext_available),
        reason="pandoc/lualatex/pdftotext not installed",
    )
    def test_a_long_table_caption_wraps_at_the_text_width(
        self, isolated_config, tmp_path, monkeypatch
    ):
        isolated_config.BIB_FILE_PATH.write_text("")
        draft_dir = tmp_path / "content" / "drafts" / "dt"
        draft_dir.mkdir(parents=True)
        draft = draft_dir / "survey.md"
        draft.write_text(f"# Title\n\n{self._TABLE}")
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)

        out_path = render_output.render(str(draft), output_format="pdf")

        text = subprocess.run(
            ["pdftotext", "-layout", str(out_path), "-"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        lines = [line.strip() for line in text.splitlines()]
        numbered = next(line for line in lines if line.startswith("Table 1:"))
        rest = lines[lines.index(numbered) :]
        caption = rest[: rest.index("")]
        assert max(len(line) for line in caption) > 70, caption


class TestCaptionedFigureRenderReal:
    @pytest.mark.skipif(
        not (pandoc_available and pdflatex_available and tikz_available),
        reason="pandoc/pdflatex/tikz.sty not installed",
    )
    def test_a_captioned_figure_compiles_to_a_numbered_pdf_float(
        self, isolated_config, tmp_path, monkeypatch
    ):
        isolated_config.BIB_FILE_PATH.write_text("")
        draft_dir = tmp_path / "content" / "drafts" / "dt"
        draft_dir.mkdir(parents=True)
        figure_pair(draft_dir)
        draft = draft_dir / "tutorial.md"
        draft.write_text(
            "# Title\n\n" + CAPTIONED_MD + "\n<!-- figureref: fig1 --> shows the flow.\n"
        )
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)

        out_path = render_output.render(str(draft), output_format="tex")

        source = out_path.read_text()
        assert "\\begin{figure}" in source
        assert "\\input{figures/fig1.tex}" in source
        assert "\\caption{One reading path.}" in source
        assert "\\label{fig:fig1}" in source
        assert "Figure~\\ref{fig:fig1} shows the flow." in source
        compiled = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", out_path.name],
            cwd=out_path.parent,
            capture_output=True,
            text=True,
        )
        assert compiled.returncode == 0, compiled.stdout[-2000:]

    @pytest.mark.skipif(
        not (pandoc_available and pdflatex_available and tikz_available),
        reason="pandoc/pdflatex/tikz.sty not installed",
    )
    def test_a_caption_with_ampersand_and_percent_still_compiles(
        self, isolated_config, tmp_path, monkeypatch
    ):
        isolated_config.BIB_FILE_PATH.write_text("")
        draft_dir = tmp_path / "content" / "drafts" / "dt"
        draft_dir.mkdir(parents=True)
        figure_pair(draft_dir)
        draft = draft_dir / "tutorial.md"
        draft.write_text(
            "# Title\n\n<!-- figure: figures/fig1 -->\nCost & throughput rose 5%, see below.\n"
        )
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)

        out_path = render_output.render(str(draft), output_format="tex")

        source = out_path.read_text()
        unwrapped = source.replace("\n", " ")
        assert "Cost \\& throughput" in unwrapped, "the & must be LaTeX-escaped by pandoc"
        assert "5\\%," in unwrapped, "the % must be LaTeX-escaped by pandoc, not left raw"
        assert "Cost & throughput" not in unwrapped, "an unescaped & must not survive into the .tex"
        assert "5%," not in unwrapped, "an unescaped % must not survive into the .tex source"
        assert "\\label{fig:fig1}" in source
        compiled = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", out_path.name],
            cwd=out_path.parent,
            capture_output=True,
            text=True,
        )
        assert compiled.returncode == 0, compiled.stdout[-2000:]

    @pytest.mark.skipif(not pandoc_available, reason="pandoc not installed")
    def test_a_caption_citing_a_real_key_resolves_through_citeproc(self, isolated_config, tmp_path):
        con = ledger.connect()
        add_citable(con, "a_2024", title="A Paper", year="2024")
        con.close()
        isolated_config.BIB_FILE_PATH.write_text(
            "@article{a_2024,\n  author={Doe, Jane},\n  title={A Paper},\n  year={2024},\n}\n"
        )
        draft_dir = isolated_config.DRAFTS_DIR / "dt"
        draft_dir.mkdir(parents=True)
        figure_pair(draft_dir)
        draft = draft_dir / "tutorial.md"
        draft.write_text("# Title\n\n<!-- figure: figures/fig1 -->\nAs reported [@a_2024].\n")

        out_path = render_output.render(str(draft), output_format="tex")

        source = out_path.read_text()
        assert "[@a_2024]" not in source, "the citekey must resolve, not survive literally"
        assert "\\label{fig:fig1}" in source

    @pytest.mark.skipif(not pandoc_available, reason="pandoc not installed")
    def test_a_captioned_figure_to_md_gets_a_bold_numbered_caption(self, isolated_config, tmp_path):
        isolated_config.BIB_FILE_PATH.write_text("")
        draft_dir = isolated_config.DRAFTS_DIR / "dt"
        draft_dir.mkdir(parents=True)
        figure_pair(draft_dir)
        draft = draft_dir / "tutorial.md"
        draft.write_text(
            "# Title\n\n" + CAPTIONED_MD + "\n<!-- figureref: fig1 --> shows the flow.\n"
        )

        out_path = render_output.render(str(draft), output_format="md")

        rendered = out_path.read_text()
        assert "**Figure 1:** One reading path." in rendered
        assert "Figure 1 shows the flow." in rendered
        assert "<!-- figure:" not in rendered

    def test_a_figureref_right_after_an_uncaptioned_marker_is_not_swallowed(
        self, isolated_config, tmp_path
    ):
        isolated_config.BIB_FILE_PATH.write_text("")
        draft_dir = isolated_config.DRAFTS_DIR / "dt"
        draft_dir.mkdir(parents=True)
        figure_pair(draft_dir, name="fig1")
        figure_pair(draft_dir, name="fig2")
        draft = draft_dir / "tutorial.md"
        draft.write_text(
            "# Title\n\n"
            + CAPTIONED_MD
            + "\n<!-- figure: figures/fig2 -->\n"
            + "<!-- figureref: fig1 --> is the one to compare against.\n"
        )

        out_path = render_output.render(str(draft), output_format="md")

        rendered = out_path.read_text()
        assert "**Figure 2:**" not in rendered
        assert "Figure 1 is the one to compare against." in rendered


class TestDeferredCitations:
    @staticmethod
    def _argv(fragment=False, defer_citations=False):
        cmd, _ = render_output._pandoc_command(
            Path("in.md"),
            Path("bib.bib"),
            Path("ieee.csl"),
            Path("out.tex"),
            Path("in.md"),
            "tex",
            "article",
            "12pt",
            "a4",
            "1in",
            [],
            fragment,
            defer_citations=defer_citations,
        )
        return cmd

    def test_defer_citations_argv_is_standalone_natbib(self):
        cmd = self._argv(defer_citations=True)

        assert "--standalone" in cmd and "--natbib" in cmd
        assert "--citeproc" not in cmd and "--csl" not in cmd
        assert "biblio-style=IEEEtran" in cmd
        assert "natbiboptions=numbers,sort&compress" in cmd
        assert "--top-level-division=chapter" not in cmd
        assert not any("chitragupta-label-prefix" in arg for arg in cmd)
        assert not any("bib_raw_tex_as_text.lua" in arg for arg in cmd)

    def test_a_plain_render_takes_none_of_it(self):
        cmd = self._argv()

        assert "--citeproc" in cmd
        assert "biblio-style=IEEEtran" not in cmd
        assert any("bib_raw_tex_as_text.lua" in arg for arg in cmd)

    def test_defer_citations_with_fragment_refused(self, isolated_config):
        draft = content_draft(isolated_config, "drafts/survey.md")
        draft.write_text("# T\n\nNo citations.\n")

        with pytest.raises(ValueError, match="fragment"):
            render_output.render(
                str(draft), output_format="tex", fragment=True, defer_citations=True
            )

    @pytest.mark.parametrize("fmt", ["pdf", "md", "docx"])
    def test_defer_citations_is_tex_only(self, isolated_config, fmt):
        draft = content_draft(isolated_config, "drafts/survey.md")
        draft.write_text("# T\n\nNo citations.\n")

        with pytest.raises(ValueError, match="tex"):
            render_output.render(str(draft), output_format=fmt, defer_citations=True)

    @pytest.mark.skipif(not pandoc_available, reason="pandoc not installed")
    def test_a_deferred_render_keeps_citekeys_and_one_references_list(
        self, isolated_config, ledger_con
    ):
        add_citable(ledger_con, "sample_dt_sync_2023", title="Sync", year="2023")
        isolated_config.BIB_FILE_PATH.write_text(
            "@article{sample_dt_sync_2023,\n  title={Sync},\n  year={2023},\n}\n"
        )
        draft = content_draft(isolated_config, "drafts/dt/survey.md")
        draft.write_text(
            "# T\n\n## Background\n\nTwins synchronise [@sample_dt_sync_2023].\n\n"
            "## References\n\n- [@sample_dt_sync_2023] Sync, 2023.\n"
        )
        out_dir = isolated_config.REVIEW_DIR / "dt" / "survey.diff" / "rendered"

        out = render_output.render(
            str(draft), output_format="tex", output_dir=out_dir, defer_citations=True
        )

        tex = out.read_text()
        assert "\\citep{sample_dt_sync_2023}" in tex
        assert "\\citeproc" not in tex
        assert "\\bibliographystyle{IEEEtran}" in tex
        assert "numbers,sort&compress" in tex
        assert "\\documentclass" in tex
        assert "{References}" not in tex
        assert (out_dir / isolated_config.BIB_FILE_PATH.name).is_file()
