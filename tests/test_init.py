"""`chitragupta init`: scaffold a project directory from a small, controlled
fixture rather than this repository's own ever-growing `.claude/`/`docs/`
tree -- the same reasoning tests/test_release.py gives for building a
throwaway git repo instead of asserting against the real one. Two classes
at the bottom are the exceptions: they read the real repository, because
that is the actual thing each guards against drift -- the manifest-agreement
test reads the pair of lists (`scripts/release.py`'s denylist, this
module's allowlist) it exists to keep honest, and the link-resolution test
(#352) reads the real prose, because a synthetic fixture would not contain
the dangling links it exists to catch.
"""

from pathlib import Path
import re

import pytest

import chitragupta.init as init
import scripts.release as release


def make_source(tmp_path: Path) -> Path:
    """A tiny stand-in for SOURCE_ROOT, with one file under each of
    init's COPY_VERBATIM entries plus the config example -- enough to
    exercise "file", "directory with one file" and "directory with
    nested files" without the real tree's size."""
    src = tmp_path / "source"
    (src / ".claude" / "skills" / "survey-writer").mkdir(parents=True)
    (src / ".claude" / "skills" / "survey-writer" / "SKILL.md").write_text(
        "# survey", encoding="utf-8"
    )
    (src / ".claude" / "hooks").mkdir(parents=True)
    (src / ".claude" / "hooks" / "session_start_hook.py").write_text("# hook", encoding="utf-8")
    (src / ".claude" / "settings.json").write_text("{}", encoding="utf-8")
    (src / "docs").mkdir()
    (src / "docs" / "CLI.md").write_text("# CLI", encoding="utf-8")
    (src / "assets" / "style").mkdir(parents=True)
    (src / "assets" / "style" / "acronyms.toml").write_text("PDF = []", encoding="utf-8")
    (src / "AGENTS.md").write_text("agent guidance", encoding="utf-8")
    (src / "CLAUDE.md").write_text("router", encoding="utf-8")
    (src / "SOUL.md").write_text("why", encoding="utf-8")
    (src / "README.md").write_text("readme", encoding="utf-8")
    (src / "DOCKER.md").write_text("running with docker", encoding="utf-8")
    (src / "config.toml.example").write_text(
        '[bib]\npath = "papers/bibliography.bib"\n', encoding="utf-8"
    )
    return src


@pytest.fixture
def source(tmp_path, monkeypatch):
    src = make_source(tmp_path)
    monkeypatch.setattr(init, "SOURCE_ROOT", src)
    return src


class TestScaffold:
    def test_writes_every_top_level_entry(self, source, tmp_path):
        dest = tmp_path / "project"
        init.scaffold(dest)
        assert {p.name for p in dest.iterdir()} == init.TOP_LEVEL

    def test_config_toml_example_becomes_config_toml(self, source, tmp_path):
        dest = tmp_path / "project"
        init.scaffold(dest)
        assert (dest / "config.toml").read_text(encoding="utf-8") == (
            source / "config.toml.example"
        ).read_text(encoding="utf-8")
        assert not (dest / "config.toml.example").exists()

    def test_nested_files_land_at_the_matching_relative_path(self, source, tmp_path):
        dest = tmp_path / "project"
        init.scaffold(dest)
        got = dest / ".claude" / "skills" / "survey-writer" / "SKILL.md"
        assert got.read_text(encoding="utf-8") == "# survey"

    def test_pycache_is_never_copied(self, source, tmp_path):
        """Not disk cruft from a checkout -- `pip install` byte-compiles
        every `.py` file it installs, including `.claude/hooks/*.py`
        (site-packages data, not part of the `chitragupta` package), so
        an installed SOURCE_ROOT can carry a fresh `__pycache__` the very
        first time `init` runs (#263, measured against a real wheel)."""
        pycache = source / ".claude" / "hooks" / "__pycache__"
        pycache.mkdir()
        (pycache / "session_start_hook.cpython-313.pyc").write_bytes(b"\x00")
        dest = tmp_path / "project"
        report = init.scaffold(dest)
        assert not (dest / ".claude" / "hooks" / "__pycache__").exists()
        assert not any("__pycache__" in line for line in report)

    def test_empty_content_and_papers_dirs_are_created(self, source, tmp_path):
        dest = tmp_path / "project"
        init.scaffold(dest)
        for rel in init.EMPTY_DIRS:
            d = dest / rel
            assert d.is_dir()
            assert list(d.iterdir()) == []

    def test_a_second_run_changes_nothing_and_says_so(self, source, tmp_path):
        dest = tmp_path / "project"
        init.scaffold(dest)
        (dest / "AGENTS.md").write_text("the user's own edit", encoding="utf-8")
        report = init.scaffold(dest)
        assert (dest / "AGENTS.md").read_text(encoding="utf-8") == "the user's own edit"
        assert any("exists, unchanged" in line and "AGENTS.md" in line for line in report)

    def test_force_overwrites_and_names_every_file_it_touches(self, source, tmp_path):
        dest = tmp_path / "project"
        init.scaffold(dest)
        (dest / "AGENTS.md").write_text("the user's own edit", encoding="utf-8")
        report = init.scaffold(dest, force=True)
        assert (dest / "AGENTS.md").read_text(encoding="utf-8") == "agent guidance"
        assert any("overwrote" in line and "AGENTS.md" in line for line in report)

    def test_force_never_deletes_a_file_the_manifest_does_not_own(self, source, tmp_path):
        """Never destroys: `--force` overwrites what it ships, and must
        not touch a skill the user added themselves under the same
        directory it is also writing into."""
        dest = tmp_path / "project"
        init.scaffold(dest)
        mine = dest / ".claude" / "skills" / "my-own-skill" / "SKILL.md"
        mine.parent.mkdir(parents=True)
        mine.write_text("# mine", encoding="utf-8")
        init.scaffold(dest, force=True)
        assert mine.read_text(encoding="utf-8") == "# mine"

    def test_dry_run_writes_nothing(self, source, tmp_path):
        dest = tmp_path / "project"
        report = init.scaffold(dest, dry_run=True)
        assert not dest.exists()
        assert any("would create" in line for line in report)

    def test_dry_run_reports_the_same_tree_a_real_run_writes(self, source, tmp_path):
        """From the same manifest, not a second, hand-maintained listing
        of it -- so the two cannot drift apart from each other."""
        dry_dest = tmp_path / "dry"
        real_dest = tmp_path / "real"
        dry_report = init.scaffold(dry_dest, dry_run=True)
        real_report = init.scaffold(real_dest)
        dry_paths = {line.split(": ", 1)[1] for line in dry_report}
        real_paths = {line.split(": ", 1)[1] for line in real_report}
        assert {p.replace(str(dry_dest), "") for p in dry_paths} == {
            p.replace(str(real_dest), "") for p in real_paths
        }

    def test_dry_run_on_an_existing_project_reports_would_overwrite(self, source, tmp_path):
        dest = tmp_path / "project"
        init.scaffold(dest)
        report = init.scaffold(dest, force=True, dry_run=True)
        assert any("would overwrite" in line and "AGENTS.md" in line for line in report)
        assert (dest / "AGENTS.md").read_text(encoding="utf-8") == "agent guidance"


class TestMain:
    def test_default_directory_is_the_current_one(self, source, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert init.main([]) == 0
        assert (tmp_path / "config.toml").exists()

    def test_an_explicit_directory_is_honoured(self, source, tmp_path):
        dest = tmp_path / "elsewhere"
        assert init.main([str(dest)]) == 0
        assert (dest / "config.toml").exists()

    def test_dry_run_flag_reaches_scaffold(self, source, tmp_path):
        dest = tmp_path / "project"
        assert init.main([str(dest), "--dry-run"]) == 0
        assert not dest.exists()

    def test_force_flag_reaches_scaffold(self, source, tmp_path):
        dest = tmp_path / "project"
        init.main([str(dest)])
        (dest / "AGENTS.md").write_text("edited", encoding="utf-8")
        init.main([str(dest), "--force"])
        assert (dest / "AGENTS.md").read_text(encoding="utf-8") == "agent guidance"

    def test_help_exits_zero_and_is_short(self, capsys):
        with pytest.raises(SystemExit) as excinfo:
            init.main(["--help"])
        assert excinfo.value.code == 0
        out = capsys.readouterr().out
        assert "init" in out
        assert len(out.splitlines()) <= 20

    def test_help_does_not_print_the_module_docstring(self):
        assert init.DESCRIPTION != init.__doc__
        assert "\n\n" not in init.DESCRIPTION


class TestManifestAgreesWithTheReleaseZip:
    """The pin the module docstring describes: `scripts/release.py`'s
    `EXCLUDE_TOP_LEVEL` denylist and this module's `TOP_LEVEL` allowlist
    must agree, modulo `DELIBERATE_DIFFERENCES` -- read against the real
    repository, which is the actual pair of lists at risk of drifting."""

    def test_the_named_differences_are_exactly_the_gap(self):
        zip_top_level = {
            p.split("/", 1)[0] for p in release.tracked_files()
        } | release.EMPTY_TOP_LEVEL
        renamed = {init.CONFIG_DEST if p == init.CONFIG_EXAMPLE else p for p in zip_top_level}
        assert renamed - init.TOP_LEVEL == init.DELIBERATE_DIFFERENCES
        assert init.TOP_LEVEL - renamed == set()


class TestScaffoldedDocLinksResolve:
    """#352: `init` copies `docs/`, `AGENTS.md`, `CLAUDE.md`, `SOUL.md`,
    `README.md` and `DOCKER.md` verbatim, and those documents
    cross-reference each other by relative Markdown link. Four targets
    in `DELIBERATE_DIFFERENCES` -- `DEVELOPER-AGENTS.md`, `DEVELOPER.md`,
    `DOCKER-DEVELOPER.md`, `plans/` -- are deliberately not copied, so a
    link to any of them from something that *is* copied dangles in a
    scaffolded project even though it resolves fine in this checkout.
    Reads the real `SOURCE_ROOT` rather than the `source` fixture's tiny
    tree, because a synthetic fixture would not contain the prose this
    exists to check."""

    # Same shape as scripts/release.py's own `_rewrite_link` pattern.
    LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

    def test_every_relative_markdown_link_resolves(self, tmp_path):
        dest = tmp_path / "project"
        init.scaffold(dest)

        md_files = sorted(dest.rglob("*.md"))
        assert md_files, (
            "scaffolded project has no .md files at all -- init.scaffold() "
            "is broken in a way that would make every assertion below pass "
            "vacuously"
        )

        broken = []
        for md_file in md_files:
            text = md_file.read_text(encoding="utf-8")
            for text_, target in self.LINK_RE.findall(text):
                if target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                target_path = target.split("#", 1)[0]
                if not target_path or "content/" in target_path:
                    continue
                if not (md_file.parent / target_path).resolve().exists():
                    broken.append(f"{md_file.relative_to(dest)}: [{text_}]({target})")

        assert not broken, (
            "Dangling relative Markdown link(s) in a scaffolded project "
            "(target not among init's COPY_VERBATIM):\n" + "\n".join(broken)
        )


class TestAnIncompleteInstallationRefuses:
    """m-37 (#509). `_write_tree` on an absent source `rglob`s nothing and
    returns `[]`, so a wheel built without `.claude/` scaffolded a project
    with **no citation-gate hook**, printed a report that simply did not
    mention it, and exited 0. A partial scaffold is worse than none: the
    user has no reason to look."""

    def test_a_missing_source_refuses_before_writing_anything(self, tmp_path, monkeypatch):
        monkeypatch.setattr(init, "SOURCE_ROOT", tmp_path / "nowhere")
        dest = tmp_path / "project"
        with pytest.raises(init.ScaffoldSourceMissing) as raised:
            init.scaffold(dest)
        assert ".claude" in str(raised.value)
        assert not dest.exists()

    def test_the_missing_names_are_all_reported_not_just_the_first(self, tmp_path, monkeypatch):
        source = tmp_path / "partial"
        (source / ".claude").mkdir(parents=True)
        (source / ".claude" / "settings.json").write_text("{}", encoding="utf-8")
        monkeypatch.setattr(init, "SOURCE_ROOT", source)
        with pytest.raises(init.ScaffoldSourceMissing) as raised:
            init.scaffold(tmp_path / "project")
        message = str(raised.value)
        assert "docs" in message and "AGENTS.md" in message
        assert ".claude" not in message

    def test_dry_run_refuses_too(self, tmp_path, monkeypatch):
        """A `--dry-run` that printed a tree the real run could not write
        would be the same lie one step earlier."""
        monkeypatch.setattr(init, "SOURCE_ROOT", tmp_path / "nowhere")
        with pytest.raises(init.ScaffoldSourceMissing):
            init.scaffold(tmp_path / "project", dry_run=True)

    def test_the_cli_exits_one_and_says_so(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(init, "SOURCE_ROOT", tmp_path / "nowhere")
        assert init.main([str(tmp_path / "project")]) == 1
        assert "[error]" in capsys.readouterr().err
