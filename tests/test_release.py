"""scripts/release.py: builds release/chitragupta-<version>.zip
from git-tracked files, excluding developer-only material. Uses a real,
throwaway git repo (cheap, and exercises the actual `git ls-files` call
rather than mocking subprocess) rather than the real repo's own tracked
files, so exclusions/inclusions are asserted against a small, controlled
fixture instead of this project's ever-changing file list."""

import subprocess

import pytest

import scripts.release as release


def make_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)

    (repo / "pyproject.toml").write_text(
        '[tool.poetry]\nname = "x"\nversion = "9.9.9"\n'
        'repository = "https://github.com/example-owner/example-repo"\n',
        encoding="utf-8",
    )
    (repo / "README.md").write_text(
        'hello\n'
        '<img src="docs/logo.svg" alt="logo">\n'
        '[See GENRE.md](docs/GENRE.md)\n'
        '[already absolute](https://example.com/elsewhere)\n'
        '[in-page anchor](#hello)\n',
        encoding="utf-8",
    )
    (repo / "chitragupta").mkdir()
    (repo / "chitragupta" / "foo.py").write_text("x = 1")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_foo.py").write_text("def test_x(): pass")
    (repo / "DEVELOPER.md").write_text("dev notes")
    (repo / ".github" / "workflows").mkdir(parents=True)
    (repo / ".github" / "workflows" / "ci.yml").write_text("name: ci")
    (repo / ".gitignore").write_text("content/parsed/\n")
    (repo / "sonar-project.properties").write_text("sonar.projectKey=x\n")
    (repo / "codecov.yml").write_text("codecov:\n  notify:\n    after_n_builds: 2\n")
    (repo / "AGENTS.md").write_text("agent guidance")
    (repo / "DEVELOPER-AGENTS.md").write_text("agent guidance for developing this repo")
    (repo / "SOUL.md").write_text("why this exists")
    (repo / ".claude" / "skills" / "survey-writer").mkdir(parents=True)
    (repo / ".claude" / "skills" / "survey-writer" / "SKILL.md").write_text("# survey")
    (repo / "bench").mkdir()
    (repo / "bench" / "bench_docling.py").write_text("x = 1")
    (repo / "content" / "drafts").mkdir(parents=True)
    (repo / "content" / "drafts" / "example-tutorial.md").write_text("# Example")
    (repo / "papers" / "pdfs").mkdir(parents=True)
    (repo / "papers" / "pdfs" / "manifest.json").write_text("{}")

    subprocess.run(["git", "add", "-A", "-f"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)
    return repo


@pytest.fixture
def repo(tmp_path, monkeypatch):
    repo_dir = make_repo(tmp_path)
    monkeypatch.setattr(release, "REPO_ROOT", repo_dir)
    return repo_dir


class TestGetVersion:
    def test_reads_poetry_version(self, repo):
        assert release.get_version() == "9.9.9"


class TestGetRepository:
    def test_reads_poetry_repository(self, repo):
        assert release.get_repository() == "https://github.com/example-owner/example-repo"


class TestRenderPypiReadme:
    """README.md, rewritten with absolute GitHub URLs for PyPI -- see
    the module docstring for why README.md itself stays relative-link
    friendly instead."""

    def test_an_image_src_becomes_an_absolute_raw_url(self, repo):
        rendered = release.render_pypi_readme("9.9.9")
        assert ('src="https://raw.githubusercontent.com/example-owner/'
                'example-repo/v9.9.9/docs/logo.svg"') in rendered

    def test_a_relative_markdown_link_becomes_an_absolute_blob_url(self, repo):
        rendered = release.render_pypi_readme("9.9.9")
        assert ("[See GENRE.md](https://github.com/example-owner/example-repo/"
                "blob/v9.9.9/docs/GENRE.md)") in rendered

    def test_an_already_absolute_link_is_left_alone(self, repo):
        rendered = release.render_pypi_readme("9.9.9")
        assert "[already absolute](https://example.com/elsewhere)" in rendered

    def test_an_in_page_anchor_link_is_left_alone(self, repo):
        """The table of contents -- rewriting these would point every
        `#section` link at a GitHub blob page instead of the same
        page's own heading."""
        rendered = release.render_pypi_readme("9.9.9")
        assert "[in-page anchor](#hello)" in rendered

    def test_the_tag_is_pinned_to_the_given_version_not_main(self, repo):
        rendered = release.render_pypi_readme("1.2.3")
        assert "/blob/v1.2.3/" in rendered
        assert "/main/" not in rendered


class TestTrackedFiles:
    def test_excludes_tests_but_ships_developer_md(self, repo):
        paths = release.tracked_files()
        assert "README.md" in paths
        assert "chitragupta/foo.py" in paths
        assert "pyproject.toml" in paths
        assert not any(p.startswith("tests/") for p in paths)
        # Every prose doc ships. What stays behind is this repo's own
        # machinery -- tests/, bench/, .github/ and .gitignore.
        assert "DEVELOPER.md" in paths

    def test_excludes_github_and_gitignore(self, repo):
        paths = release.tracked_files()
        assert not any(p.startswith(".github/") for p in paths)
        assert ".gitignore" not in paths

    def test_excludes_sonar_project_properties(self, repo):
        # Root-level CI config, excluded for the same reason .github/ is:
        # it does something only in a git checkout of *this* repo, and it
        # names this repo's Sonar project key specifically.
        paths = release.tracked_files()
        assert "sonar-project.properties" not in paths

    def test_excludes_codecov_yml(self, repo):
        # Same category as the two above, and the worst of the three to
        # ship. It is not merely inert in someone else's checkout: it says
        # `after_n_builds: 2`, so a consumer who unzips a release into
        # their own repo and pushes it gets a Codecov that waits for a
        # second upload their CI never makes, and every coverage status
        # hangs pending. That is the exact failure mode codecov.yml's own
        # comment warns about, exported to someone who never opted into it.
        paths = release.tracked_files()
        assert "codecov.yml" not in paths

    def test_ships_all_three_agent_guidance_files(self, repo):
        # All three ship. .claude/ and its genre skills ship too, and they
        # cite AGENTS.md by name, so excluding any of the three would leave
        # a dangling reference for anyone reading from an unzipped release
        # -- including someone who unzips it to work on the pipeline.
        paths = release.tracked_files()
        assert "SOUL.md" in paths
        assert "AGENTS.md" in paths
        assert "DEVELOPER-AGENTS.md" in paths
        # .claude/ ships for the same reason -- the genre skills are what
        # cite AGENTS.md, so the two have to travel together.
        assert ".claude/skills/survey-writer/SKILL.md" in paths

    def test_excludes_bench(self, repo):
        # bench/ measures *this* repo's parser on *this* host's corpus --
        # developer-only material in the same category as tests/, and it
        # needs a bib file a release consumer doesn't have.
        paths = release.tracked_files()
        assert not any(p.startswith("bench/") for p in paths)

    def test_excludes_tracked_files_under_content_and_papers(self, repo):
        paths = release.tracked_files()
        assert not any(p.startswith("content/") for p in paths)
        assert not any(p.startswith("papers/") for p in paths)


class TestBuildRelease:
    def test_zip_contains_only_non_dev_files(self, repo):
        import zipfile

        zip_path, n_files = release.build_release()

        assert zip_path == repo / "release" / "chitragupta-9.9.9.zip"
        assert zip_path.exists()
        assert n_files == 8  # README.md, SOUL.md, AGENTS.md, DEVELOPER-AGENTS.md,
        #                      DEVELOPER.md, pyproject.toml, chitragupta/foo.py,
        #                      .claude/skills/survey-writer/SKILL.md

        with zipfile.ZipFile(zip_path) as zf:
            names = set(zf.namelist())
        assert "chitragupta-9.9.9/README.md" in names
        assert "chitragupta-9.9.9/chitragupta/foo.py" in names
        assert not any("tests/" in n for n in names)
        assert any(n.endswith("/DEVELOPER.md") for n in names)

    def test_zip_excludes_github_and_gitignore(self, repo):
        import zipfile

        zip_path, _ = release.build_release()

        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
        assert not any(".github/" in n for n in names)
        assert not any(n.endswith("/.gitignore") for n in names)
        assert any(n.endswith("/SOUL.md") for n in names)
        assert any(n.endswith("/AGENTS.md") for n in names)
        assert any(n.endswith("/DEVELOPER-AGENTS.md") for n in names)
        assert any("/.claude/skills/" in n for n in names)

    def test_zip_ships_content_and_papers_as_empty_directories(self, repo):
        import zipfile

        zip_path, _ = release.build_release()

        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
        assert "chitragupta-9.9.9/content/" in names
        assert "chitragupta-9.9.9/papers/" in names
        # The directory placeholder is present, but none of the real,
        # per-host tracked files that used to live under it are.
        assert not any(n.startswith("chitragupta-9.9.9/content/") and n != "chitragupta-9.9.9/content/" for n in names)
        assert not any(n.startswith("chitragupta-9.9.9/papers/") and n != "chitragupta-9.9.9/papers/" for n in names)

        # Staging directory is cleaned up; only the zip remains under release/.
        assert list((repo / "release").iterdir()) == [zip_path]

    def test_rerunning_overwrites_stale_archive(self, repo):
        release.build_release()
        zip_path, _ = release.build_release()
        assert zip_path.exists()

    def test_leftover_staging_dir_from_a_crashed_run_is_cleared(self, repo):
        """A prior run that died before its own cleanup would leave the
        staging dir behind; build_release must clear it, not merge into it
        or fail on FileExistsError."""
        stale_staging = repo / "release" / "chitragupta-9.9.9"
        stale_staging.mkdir(parents=True)
        (stale_staging / "leftover-from-a-crashed-run.txt").write_text("stale")

        zip_path, n_files = release.build_release()

        assert n_files == 8
        assert not stale_staging.exists()


class TestMain:
    def test_main_prints_archive_path_and_returns_zero(self, repo, capsys):
        rc = release.main()
        assert rc == 0
        out = capsys.readouterr().out
        assert "chitragupta-9.9.9.zip" in out

    def test_main_also_writes_the_pypi_readme(self, repo, capsys):
        release.main()
        out = capsys.readouterr().out
        assert "README.pypi.md" in out
        rendered = (repo / "README.pypi.md").read_text(encoding="utf-8")
        assert "raw.githubusercontent.com" in rendered
