"""`chitragupta/progname.py`: what `--help` calls this command.

There are two ways in now -- the installed console script and the module
form the hooks and skills keep using -- and a usage line naming the wrong
one tells a reader to type something that may not be on their PATH.
"""

import chitragupta.progname as progname


class TestProgFor:
    def test_module_form_when_not_a_console_script(self, monkeypatch):
        monkeypatch.setattr(progname.sys, "argv", ["/usr/bin/python3", "-m"])
        assert progname.prog_for("draft") == "python -m chitragupta.draft"

    def test_console_script_name_is_used_when_it_is_one(self, monkeypatch):
        monkeypatch.setattr(progname.sys, "argv", ["/venv/bin/chitragupta"])
        assert progname.prog_for("draft") == "chitragupta draft"

    def test_the_short_alias_reports_itself_not_the_long_name(self, monkeypatch):
        """`cg review --help` must not print `chitragupta review`: the
        point of the alias is that it is what the user actually typed."""
        monkeypatch.setattr(progname.sys, "argv", ["/venv/bin/cg"])
        assert progname.prog_for("review") == "cg review"

    def test_windows_exe_suffix_is_stripped(self, monkeypatch):
        """Windows appends .exe to a console script, and nobody types
        `chitragupta.exe draft`.

        Written with a forward-slash path on purpose: os.path.basename
        does not split on a backslash when this suite runs on Linux, so a
        literal Windows path would pass here for the wrong reason and the
        suffix branch would never be reached. What is under test is the
        suffix, not the separator, and the case is checked too."""
        monkeypatch.setattr(progname.sys, "argv", ["/venv/Scripts/chitragupta.EXE"])
        assert progname.prog_for("draft") == "chitragupta draft"

    def test_no_layer_gives_the_bare_command(self, monkeypatch):
        monkeypatch.setattr(progname.sys, "argv", ["/venv/bin/chitragupta"])
        assert progname.prog_for("") == "chitragupta"
        monkeypatch.setattr(progname.sys, "argv", ["/usr/bin/python3"])
        assert progname.prog_for("") == "python -m chitragupta"

    def test_a_lookalike_name_is_not_a_console_script(self, monkeypatch):
        """Matched exactly, not by prefix: `chitragupta-old` on someone's
        PATH is a different program."""
        monkeypatch.setattr(progname.sys, "argv", ["/usr/local/bin/chitragupta-old"])
        assert progname.prog_for("draft") == "python -m chitragupta.draft"
