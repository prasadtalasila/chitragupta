"""`chitragupta figure sync`: the walk, the writes, and the exit codes."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from chitragupta import figure
from chitragupta.figure import __main__ as cli
from tests.conftest import needs_tikz, run_python

REPO_ROOT = Path(__file__).resolve().parent.parent
PICTURE = (
    "\\usetikzlibrary{arrows.meta,positioning,fit,backgrounds,calc,shadows.blur}%\n"
    "\\begin{tikzpicture}[cg]\n"
    "  \\node[cgbox] (a) {\\cglab{Parse}{text out}};\n"
    "\\end{tikzpicture}%\n"
)


@pytest.fixture(scope="module")
def house():
    return figure.load_house()


@pytest.fixture
def figures(tmp_path):
    directory = tmp_path / "drafts" / "topic" / "figures"
    directory.mkdir(parents=True)
    return directory


def write(path: Path, text: str) -> Path:
    path.write_bytes(text.encode("utf-8"))
    return path


class TestSync:
    def test_a_bare_figure_is_stamped(self, figures, house):
        path = write(figures / "a.tex", PICTURE)
        [outcome] = figure.run([figures], house, check=False)
        assert outcome.action == "stamped"
        assert path.read_text(encoding="utf-8") == house.text + PICTURE

    def test_running_it_twice_changes_nothing_the_second_time(self, figures, house):
        path = write(figures / "a.tex", PICTURE)
        figure.run([figures], house, check=False)
        first = path.read_bytes()
        [outcome] = figure.run([figures], house, check=False)
        assert outcome.action == "current" and path.read_bytes() == first

    def test_a_modified_region_is_reported_with_a_diff_and_not_touched(self, figures, house):
        edited = house.text.replace("0.95pt", "0.9pt", 1) + PICTURE
        path = write(figures / "a.tex", edited)
        [outcome] = figure.run([figures], house, check=False)
        assert outcome.action == "modified"
        assert "-" in outcome.detail and "0.9pt" in outcome.detail
        assert path.read_text(encoding="utf-8") == edited

    def test_a_region_from_a_newer_install_says_so_and_is_not_touched(self, figures, house):
        newer = house.text.replace(f" v{house.version} ", " v9 ", 1) + PICTURE
        path = write(figures / "a.tex", newer)
        [outcome] = figure.run([figures], house, check=False)
        assert outcome.action == "modified" and "newer than this install" in outcome.detail
        assert path.read_text(encoding="utf-8") == newer

    def test_check_writes_nothing(self, figures, house):
        path = write(figures / "a.tex", PICTURE)
        [outcome] = figure.run([figures], house, check=True)
        assert outcome.action == "missing" and path.read_text(encoding="utf-8") == PICTURE

    def test_crlf_survives_a_stamp(self, figures, house):
        path = write(figures / "a.tex", PICTURE.replace("\n", "\r\n"))
        figure.run([figures], house, check=False)
        assert path.read_bytes() == (house.text + PICTURE).replace("\n", "\r\n").encode()

    def test_not_utf8_is_skipped_and_the_walk_goes_on(self, figures, house):
        (figures / "a.tex").write_bytes(b"\xff\xfe junk")
        write(figures / "b.tex", PICTURE)
        outcomes = figure.run([figures], house, check=False)
        assert [o.action for o in outcomes] == ["skipped", "stamped"]

    @pytest.mark.skipif(os.name == "nt", reason="symlinks need privileges on Windows")
    def test_a_symlink_is_never_written_through(self, figures, house, tmp_path):
        target = write(tmp_path / "elsewhere.tex", PICTURE)
        (figures / "a.tex").symlink_to(target)
        [outcome] = figure.run([figures], house, check=False)
        assert outcome.action == "skipped" and target.read_text(encoding="utf-8") == PICTURE

    @pytest.mark.skipif(os.name == "nt" or os.geteuid() == 0, reason="chmod is not enforced")
    def test_an_unwritable_file_is_reported_not_raised(self, figures, house):
        path = write(figures / "a.tex", PICTURE)
        # write_atomically creates a temp sibling, so the *directory* is
        # what has to refuse the write.
        figures.chmod(0o500)
        try:
            [outcome] = figure.run([figures], house, check=False)
        finally:
            figures.chmod(0o700)
        assert outcome.action == "skipped" and outcome.path == path
        assert path.read_text(encoding="utf-8") == PICTURE

    def test_a_read_only_file_is_reported_and_not_replaced(self, figures, house):
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            pytest.skip("root writes through a read-only mode")
        path = write(figures / "a.tex", PICTURE)
        path.chmod(0o444)
        try:
            [outcome] = figure.run([figures], house, check=False)
        finally:
            path.chmod(0o644)
        assert (outcome.action, outcome.detail) == ("skipped", "read-only")
        assert path.read_text(encoding="utf-8") == PICTURE

    def test_a_symlink_is_reported_on_every_platform(self, figures, house, monkeypatch):
        write(figures / "a.tex", PICTURE)
        monkeypatch.setattr(Path, "is_symlink", lambda self: True)
        [outcome] = figure.run([figures], house, check=False)
        assert outcome.action == "skipped" and "symlink" in outcome.detail

    def test_a_failed_write_is_reported_on_every_platform(self, figures, house, monkeypatch):
        path = write(figures / "a.tex", PICTURE)

        def refuse(*_args):
            raise OSError("disk full")

        monkeypatch.setattr("chitragupta.figure._sync.write_atomically", refuse)
        [outcome] = figure.run([figures], house, check=False)
        assert (outcome.action, outcome.detail) == ("skipped", "disk full")
        assert path.read_text(encoding="utf-8") == PICTURE

    def test_a_path_that_cannot_be_read_is_reported(self, tmp_path, house):
        [outcome] = figure.run([tmp_path / "absent.tex"], house, check=False)
        assert outcome.action == "skipped"

    def test_malformed_markers_are_reported_and_not_touched(self, figures, house):
        text = house.text + house.text + PICTURE
        path = write(figures / "a.tex", text)
        [outcome] = figure.run([figures], house, check=False)
        assert outcome.action == "malformed" and path.read_text(encoding="utf-8") == text

    def test_no_picture_is_reported(self, figures, house):
        write(figures / "a.tex", "% nothing drawn\n")
        [outcome] = figure.run([figures], house, check=False)
        assert outcome.action == "no-picture"


class TestFigureFiles:
    def test_a_directory_contributes_only_its_figures_dirs(self, tmp_path):
        """A draft's own `.tex` under a named directory is not a figure: a
        `tikzpicture` inside its `verbatim` would otherwise be an anchor."""
        for rel in ["t/figures/a.tex", "t/t.tex", "t/figures/sub/b.tex"]:
            (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / rel).write_text("x", encoding="utf-8")
        found = figure.figure_files([tmp_path / "t"])
        assert [p.relative_to(tmp_path).as_posix() for p in found] == ["t/figures/a.tex"]

    def test_no_drafts_directory_is_no_figures(self, tmp_path, monkeypatch):
        monkeypatch.setattr("chitragupta.config.DRAFTS_DIR", tmp_path / "absent")
        assert figure.figure_files([]) == []

    def test_a_file_named_explicitly_is_taken_as_given(self, tmp_path):
        path = tmp_path / "anywhere.tex"
        assert figure.figure_files([path]) == [path]

    def test_the_default_walk_is_every_figures_dir_under_drafts(self, tmp_path, monkeypatch):
        drafts = tmp_path / "drafts"
        for rel in [
            "t/figures/a.tex",
            "book/unit/figures/b.tex",
            "t/chapter.tex",
            "t/figures/a.txt",
        ]:
            (drafts / rel).parent.mkdir(parents=True, exist_ok=True)
            (drafts / rel).write_text("x", encoding="utf-8")
        monkeypatch.setattr("chitragupta.config.DRAFTS_DIR", drafts)
        found = figure.figure_files([])
        assert [p.relative_to(drafts).as_posix() for p in found] == [
            "book/unit/figures/b.tex",
            "t/figures/a.tex",
        ]


class TestCli:
    def test_sync_exits_zero_even_with_a_modified_file(self, figures, house, capsys):
        write(figures / "a.tex", house.text.replace("0.95pt", "0.9pt", 1) + PICTURE)
        assert cli.main(["sync", str(figures)]) == 0
        assert "modified" in capsys.readouterr().out

    def test_check_exits_one_when_anything_is_not_current(self, figures):
        write(figures / "a.tex", PICTURE)
        assert cli.main(["sync", "--check", str(figures)]) == 1

    def test_check_exits_zero_when_everything_is_current(self, figures, house):
        write(figures / "a.tex", house.text + PICTURE)
        assert cli.main(["sync", "--check", str(figures)]) == 0

    def test_no_figure_files_says_so_and_exits_zero(self, tmp_path, capsys):
        assert cli.main(["sync", str(tmp_path)]) == 0
        assert "no figure files" in capsys.readouterr().out

    def test_a_broken_install_exits_two(self, figures, monkeypatch, capsys):
        def broken():
            raise OSError("cg-figstyle.tex: not found")

        monkeypatch.setattr(cli, "load_house", broken)
        assert cli.main(["sync", str(figures)]) == 2
        assert "cg-figstyle.tex" in capsys.readouterr().err

    def test_the_top_level_entry_point_reaches_it(self):
        result = run_python("-m", "chitragupta", "figure", "sync", "--help", check=False)
        assert result.returncode == 0 and "--check" in result.stdout


class TestThisRepositorysOwnFigures:
    def test_every_shipped_scaffold_and_exemplar_is_current(self, house):
        tikz = REPO_ROOT / "assets" / "tikz"
        files = sorted(tikz.glob("*.tex")) + sorted((tikz / "exemplars").glob("*.tex"))
        outcomes = figure.run(files, house, check=True)
        assert len(outcomes) > 1
        assert {o.action for o in outcomes} == {"current"}


@needs_tikz
class TestRoundTrip:
    def test_a_stamped_figure_compiles_under_tikz_alone(self, figures, house, tmp_path):
        """The property the travel rule exists for (#1013's acceptance)."""
        path = write(figures / "a.tex", PICTURE)
        figure.run([figures], house, check=False)
        doc = tmp_path / "probe.tex"
        doc.write_text(
            "\\documentclass{article}\n\\usepackage{tikz}\n\\begin{document}\n"
            f"\\input{{{path.as_posix()}}}\n\\end{{document}}\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [shutil.which("pdflatex"), "-interaction=nonstopmode", "-halt-on-error", doc.name],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout[-2000:]
