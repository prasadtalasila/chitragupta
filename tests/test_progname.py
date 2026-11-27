import chitragupta.progname as progname


class TestProgFor:
    def test_module_form_when_not_a_console_script(self, monkeypatch):
        monkeypatch.setattr(progname.sys, "argv", ["/usr/bin/python3", "-m"])
        assert progname.prog_for("draft") == "python -m chitragupta.draft"

    def test_console_script_name_is_used_when_it_is_one(self, monkeypatch):
        monkeypatch.setattr(progname.sys, "argv", ["/venv/bin/chitragupta"])
        assert progname.prog_for("draft") == "chitragupta draft"

    def test_the_short_alias_reports_itself_not_the_long_name(self, monkeypatch):
        monkeypatch.setattr(progname.sys, "argv", ["/venv/bin/cg"])
        assert progname.prog_for("review") == "cg review"

    def test_windows_exe_suffix_is_stripped(self, monkeypatch):
        monkeypatch.setattr(progname.sys, "argv", ["/venv/Scripts/chitragupta.EXE"])
        assert progname.prog_for("draft") == "chitragupta draft"

    def test_no_layer_gives_the_bare_command(self, monkeypatch):
        monkeypatch.setattr(progname.sys, "argv", ["/venv/bin/chitragupta"])
        assert progname.prog_for("") == "chitragupta"
        monkeypatch.setattr(progname.sys, "argv", ["/usr/bin/python3"])
        assert progname.prog_for("") == "python -m chitragupta"

    def test_a_lookalike_name_is_not_a_console_script(self, monkeypatch):
        monkeypatch.setattr(progname.sys, "argv", ["/usr/local/bin/chitragupta-old"])
        assert progname.prog_for("draft") == "python -m chitragupta.draft"
