"""#781's migration: strip both generations of hand-rolled TikZ library
loading from figure files, leaving the plain `\\usetikzlibrary` line.

There is nothing in this repository to migrate -- a grep for either
internal over the tree, over `content/` and over its backup snapshots
returns no file. The 20 files the issue names live in the author's own
`content/drafts/`, which is gitignored. So this script is developed
against fixtures and run by whoever has the affected tree, which is also
why `main` is dry-run by default: its target is by definition a directory
with no undo.
"""

from scripts.strip_tikz_load_workarounds import main, strip_workarounds


class TestStripWorkarounds:
    def test_the_plain_load_survives(self):
        source = "\\usetikzlibrary{positioning}\n\\begin{tikzpicture}\n\\end{tikzpicture}\n"

        assert strip_workarounds(source) == source

    def test_a_flag_clearing_line_goes(self):
        source = (
            "\\expandafter\\let\\csname tikz@library@positioning@loaded\\endcsname\\relax\n"
            "\\usetikzlibrary{positioning}\n"
        )

        assert strip_workarounds(source) == "\\usetikzlibrary{positioning}\n"

    def test_a_hook_save_and_restore_goes(self):
        source = (
            "\\let\\cgsavedhook\\tikz@node@reset@hook\n"
            "\\usetikzlibrary{fit}\n"
            "\\global\\let\\tikz@node@reset@hook\\cgsavedhook\n"
            "\\begin{tikzpicture}\n"
        )

        assert strip_workarounds(source) == "\\usetikzlibrary{fit}\n\\begin{tikzpicture}\n"

    def test_a_makeatletter_wrapper_goes_with_it(self):
        # Both generations were written inside one, and a `\makeatletter`
        # left with nothing between it and its `\makeatother` is dead
        # weight that reads as a workaround still being there.
        source = (
            "\\makeatletter\n"
            "\\expandafter\\let\\csname tikz@library@fit@loaded\\endcsname\\relax\n"
            "\\makeatother\n"
            "\\usetikzlibrary{fit}\n"
        )

        assert strip_workarounds(source) == "\\usetikzlibrary{fit}\n"

    def test_a_makeatletter_around_anything_else_stays(self):
        # Only an emptied wrapper goes. A figure doing real `@`-internal
        # work keeps both halves.
        source = "\\makeatletter\n\\def\\myhelper{x}\n\\makeatother\n"

        assert strip_workarounds(source) == source

    def test_a_file_with_nothing_to_strip_is_returned_unchanged(self):
        source = "\\begin{tikzpicture}\n\\end{tikzpicture}\n"

        assert strip_workarounds(source) == source

    def test_a_line_that_merely_draws_is_never_touched(self):
        source = "\\draw (a) -- (b);\n"

        assert strip_workarounds(source) == source

    def test_a_drawing_line_that_mentions_the_internal_is_left_alone(self):
        # Line-oriented deliberately: a regex reaching inside a line
        # could cut a `\draw` in half, and a figure that stops compiling
        # is a worse outcome than a workaround left behind for a human
        # to see.
        source = "\\draw (a) -- (b); % tikz@node@reset@hook is why this exists\n"

        assert strip_workarounds(source) == source


class TestMain:
    def _figure(self, tmp_path, body):
        path = tmp_path / "fig.tex"
        path.write_text(body, encoding="utf-8")
        return path

    WORKAROUND = "\\let\\s\\tikz@node@reset@hook\n\\usetikzlibrary{fit}\n"

    def test_dry_run_is_the_default_and_writes_nothing(self, tmp_path, capsys):
        path = self._figure(tmp_path, self.WORKAROUND)

        assert main([str(tmp_path)]) == 0
        assert path.read_text(encoding="utf-8") == self.WORKAROUND
        out = capsys.readouterr().out
        assert "fig.tex" in out
        assert "tikz@node@reset@hook" in out

    def test_write_actually_strips(self, tmp_path):
        path = self._figure(tmp_path, self.WORKAROUND)

        assert main([str(tmp_path), "--write"]) == 0
        assert path.read_text(encoding="utf-8") == "\\usetikzlibrary{fit}\n"

    def test_a_named_file_works_as_well_as_a_directory(self, tmp_path):
        path = self._figure(tmp_path, self.WORKAROUND)

        assert main([str(path), "--write"]) == 0
        assert path.read_text(encoding="utf-8") == "\\usetikzlibrary{fit}\n"

    def test_a_clean_tree_reports_nothing_and_exits_zero(self, tmp_path, capsys):
        self._figure(tmp_path, "\\usetikzlibrary{fit}\n")

        assert main([str(tmp_path)]) == 0
        assert "no figure file" in capsys.readouterr().out.lower()

    def test_a_missing_path_is_an_error(self, tmp_path, capsys):
        assert main([str(tmp_path / "absent")]) == 1
        assert "absent" in capsys.readouterr().err
