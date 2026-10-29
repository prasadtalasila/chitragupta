"""`chitragupta figure new`: a figure started from a scaffold (#1052)."""

import pytest

from chitragupta import config, figure
from chitragupta.figure import _new
from chitragupta.figure import __main__ as cli
from chitragupta.figure._layout import declared_layout

SHIPPED = config.shipped("assets", "tikz")


@pytest.fixture(scope="module")
def house():
    return figure.load_house()


@pytest.fixture
def with_twin(tmp_path, monkeypatch):
    """A scaffold directory where one layout ships a twin of its own."""
    directory = tmp_path / "scaffolds"
    directory.mkdir()
    (directory / "pipeline.tex").write_bytes((SHIPPED / "pipeline.tex").read_bytes())
    (directory / "pipeline.txt").write_text("[ Parse ] --> [ Index ]\n", encoding="utf-8")
    monkeypatch.setattr(_new, "SCAFFOLD_DIR", directory)
    return directory


@pytest.fixture
def without_twin(tmp_path, monkeypatch):
    """A scaffold directory where a layout ships no twin. Every shipped
    layout has had one since #1056, so only a directory like this one
    still reaches the "no twin" path."""
    directory = tmp_path / "scaffolds"
    directory.mkdir()
    (directory / "zoned-spine.tex").write_bytes((SHIPPED / "zoned-spine.tex").read_bytes())
    monkeypatch.setattr(_new, "SCAFFOLD_DIR", directory)
    return directory


class TestLayouts:
    def test_the_ids_are_the_scaffolds_that_declare_their_own_stem(self):
        ids = _new.layouts()
        assert "zoned-spine" in ids and "hub-and-spoke-network" in ids
        assert "cg-figstyle" not in ids
        for name, path in ids.items():
            assert declared_layout(path.read_text(encoding="utf-8")) == name

    def test_a_file_declaring_another_layout_is_not_an_id(self, tmp_path, monkeypatch):
        (tmp_path / "copy.tex").write_text("% cg-layout: map\n", encoding="utf-8")
        monkeypatch.setattr(_new, "SCAFFOLD_DIR", tmp_path)
        assert _new.layouts() == {}


class TestNew:
    @pytest.mark.parametrize("layout", sorted(_new.layouts()))
    def test_every_layout_copies_and_is_current_after_sync(self, figures, house, layout):
        created = _new.new_figure(figures, "flow", layout, house)
        text = created.figure.read_text(encoding="utf-8")
        assert created.figure == figures / "flow.tex"
        assert declared_layout(text) == layout
        assert created.sync.action in {"current", "refreshed"}
        assert figure.classify(text, house).state is figure.State.CURRENT
        # #1056: every shipped layout ships its twin, and it is copied.
        assert created.twin.read_bytes() == (SHIPPED / f"{layout}.txt").read_bytes()

    def test_no_twin_is_written_when_the_layout_ships_none(self, figures, house, without_twin):
        created = _new.new_figure(figures, "flow", "zoned-spine", house)
        assert created.twin is None and not (figures / "flow.txt").exists()

    def test_a_shipped_twin_is_copied(self, figures, house, with_twin):
        created = _new.new_figure(figures, "flow", "pipeline", house)
        assert created.twin == figures / "flow.txt"
        assert created.twin.read_text(encoding="utf-8") == "[ Parse ] --> [ Index ]\n"

    @pytest.mark.parametrize("existing", ["flow.tex", "flow.txt"])
    def test_an_existing_half_is_never_overwritten(self, figures, house, existing):
        (figures / existing).write_text("mine", encoding="utf-8")
        with pytest.raises(_new.Refused, match="already exists"):
            _new.new_figure(figures, "flow", "pipeline", house)
        assert (figures / existing).read_text(encoding="utf-8") == "mine"
        assert sorted(p.name for p in figures.iterdir()) == [existing]

    def test_a_symlink_is_never_written_through(self, figures, house, tmp_path):
        outside = tmp_path / "outside.tex"
        (figures / "flow.tex").symlink_to(outside)
        with pytest.raises(_new.Refused, match="already exists"):
            _new.new_figure(figures, "flow", "pipeline", house)
        assert not outside.exists()

    @pytest.mark.parametrize("name", ["../flow", "sub/flow", "flow.tex", "", "a b"])
    def test_a_name_that_is_not_a_bare_stem_is_refused(self, figures, house, name):
        with pytest.raises(_new.Refused, match="bare file name"):
            _new.new_figure(figures, name, "pipeline", house)

    def test_a_directory_not_named_figures_is_refused(self, tmp_path, house):
        with pytest.raises(_new.Refused, match="named `figures`"):
            _new.new_figure(tmp_path, "flow", "pipeline", house)

    def test_a_missing_figures_directory_is_created_under_an_existing_parent(self, tmp_path, house):
        created = _new.new_figure(tmp_path / "figures", "flow", "pipeline", house)
        assert created.figure.is_file()

    def test_a_figures_directory_whose_parent_is_missing_is_refused(self, tmp_path, house):
        with pytest.raises(_new.Refused, match="does not exist"):
            _new.new_figure(tmp_path / "absent" / "figures", "flow", "pipeline", house)

    def test_an_unknown_layout_lists_the_ids(self, figures, house):
        with pytest.raises(_new.Refused, match="zoned-spine"):
            _new.new_figure(figures, "flow", "spiral", house)


class TestCopy:
    def test_a_file_that_appears_after_the_check_is_refused_not_replaced(self, tmp_path):
        source = tmp_path / "source.tex"
        source.write_text("scaffold", encoding="utf-8")
        target = tmp_path / "flow.tex"
        target.write_text("mine", encoding="utf-8")
        with pytest.raises(_new.Refused, match="already exists"):
            _new._copy(source, target)
        assert target.read_text(encoding="utf-8") == "mine"


class TestCli:
    def test_it_reports_what_it_created_and_the_missing_twin(self, figures, capsys, without_twin):
        args = ["new", str(figures), "flow", "--layout", "zoned-spine"]
        assert cli.main(args) == 0
        out = capsys.readouterr().out
        assert f"created  {figures / 'flow.tex'}   (from zoned-spine)" in out
        assert f"no twin  zoned-spine ships no .txt twin; write {figures / 'flow.txt'}" in out
        assert "figure sync: 1 " in out

    def test_it_reports_a_copied_twin(self, figures, capsys, with_twin):
        assert cli.main(["new", str(figures), "flow", "--layout", "pipeline"]) == 0
        assert f"created  {figures / 'flow.txt'}   (from pipeline)" in capsys.readouterr().out

    def test_a_refusal_exits_two_and_writes_nothing(self, figures, capsys):
        (figures / "flow.tex").write_text("mine", encoding="utf-8")
        assert cli.main(["new", str(figures), "flow", "--layout", "pipeline"]) == 2
        assert "already exists" in capsys.readouterr().err

    def test_a_broken_install_exits_two(self, figures, monkeypatch, capsys):
        def broken():
            raise OSError("cg-figstyle.tex: gone")

        monkeypatch.setattr(cli, "load_house", broken)
        assert cli.main(["new", str(figures), "flow", "--layout", "pipeline"]) == 2
        assert "chitragupta doctor" in capsys.readouterr().err

    def test_an_unreadable_scaffold_exits_two(self, figures, monkeypatch, capsys):
        def unreadable(*_args, **_kwargs):
            raise OSError("pipeline.tex: gone")

        monkeypatch.setattr(_new, "_copy", unreadable)
        assert cli.main(["new", str(figures), "flow", "--layout", "pipeline"]) == 2
        assert "chitragupta doctor" in capsys.readouterr().err


class TestABrokenInstall:
    """#1052 review: the scaffolds are read when `figure new` runs, never
    while the parser is built, so a broken one cannot take `sync` and
    `check` down with it."""

    @pytest.fixture
    def broken(self, tmp_path, monkeypatch):
        (tmp_path / "pipeline.tex").write_bytes(b"% cg-layout: pipeline\n\xff\xfe")
        monkeypatch.setattr(_new, "SCAFFOLD_DIR", tmp_path)

    def test_figure_sync_still_runs(self, figures, broken):
        assert cli.main(["sync", "--check", str(figures)]) == 0

    def test_figure_new_exits_two_naming_doctor(self, figures, broken, capsys):
        assert cli.main(["new", str(figures), "flow", "--layout", "pipeline"]) == 2
        assert "chitragupta doctor" in capsys.readouterr().err

    def test_no_scaffolds_at_all_says_so(self, figures, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(_new, "SCAFFOLD_DIR", tmp_path / "absent")
        assert cli.main(["new", str(figures), "flow", "--layout", "pipeline"]) == 2
        assert "no layouts are installed" in capsys.readouterr().err
