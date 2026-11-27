import importlib.util
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def not_on_pypi(_url):
    return False


@pytest.fixture(scope="module")
def check():
    spec = importlib.util.spec_from_file_location(
        "check_version_bump", REPO_ROOT / "scripts" / "check_version_bump.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def _no_real_network(check, monkeypatch):
    reached = []

    def tripwire(url, *_args, **_kwargs):
        reached.append(url)
        raise check.urllib.error.URLError("the test suite does not have a network")

    monkeypatch.setattr(check.urllib.request, "urlopen", tripwire)
    yield
    assert not reached, (
        f"this test reached the network: {reached}. Every test here must "
        "stay off it -- pass `fetch=not_on_pypi` to main() for a definite "
        "'not published', or `--offline` to skip the PyPI check entirely."
    )


class TestOrdering:
    @pytest.mark.parametrize(
        "lower,higher",
        [
            ("5.9.0", "5.10.0"),
            ("5.19.0", "5.20.0"),
            ("5.9.9", "5.10.0"),
            ("4.99.0", "5.0.0"),
            ("5.19.0", "5.19.1"),
        ],
    )
    def test_a_higher_version_sorts_higher(self, check, lower, higher):
        assert check.parse(lower) < check.parse(higher)

    def test_a_string_comparison_would_have_got_this_wrong(self, check):
        assert "5.9.0" > "5.10.0"  # the trap
        assert check.parse("5.9.0") < check.parse("5.10.0")

    def test_a_non_numeric_component_sorts_after_the_numbers(self, check):
        assert check.parse("5.20.0") < check.parse("5.20.rc1")


class TestTheRules:
    TAGS = ("v5.18.0", "v5.19.0")

    def test_a_real_bump_passes(self, check):
        assert check.problems("5.20.0", "5.19.0", self.TAGS) == []

    def test_a_version_equal_to_main_is_the_silent_collision(self, check):
        found = check.problems("5.19.0", "5.19.0", self.TAGS)
        assert found
        assert "another pr took that number" in found[0].lower()

    def test_a_version_below_main_is_caught(self, check):
        assert check.problems("5.18.0", "5.19.0", self.TAGS)

    def test_a_merged_but_untagged_version_is_still_caught(self, check):
        found = check.problems("5.20.0", "5.20.0", self.TAGS)
        assert found, "a tag-existence check alone would have passed this"
        assert "main is already at 5.20.0" in found[0]

    def test_an_already_released_version_is_caught_by_the_tag_rule(self, check):
        found = check.problems("5.19.0", "5.18.0", self.TAGS)
        assert any("already released as v5.19.0" in p for p in found)

    def test_both_rules_can_fire_at_once(self, check):
        assert len(check.problems("5.18.0", "5.19.0", self.TAGS)) == 2

    def test_no_tags_at_all_is_not_a_failure(self, check):
        assert check.problems("5.20.0", "5.19.0", []) == []


class TestParsingPyproject:
    def test_it_reads_the_project_version(self, check):
        assert check.version_in('[project]\nversion = "5.20.0"\n') == "5.20.0"

    def test_it_still_reads_a_poetry_version(self, check):
        assert check.version_in('[tool.poetry]\nversion = "5.20.0"\n') == "5.20.0"

    def test_project_wins_where_both_are_present(self, check):
        text = '[project]\nversion = "5.21.0"\n[tool.poetry]\nversion = "5.20.0"\n'
        assert check.version_in(text) == "5.21.0"


def git_repo(root: Path, base_version: str, head_version: str, tag: str | None):
    def run(*args):
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)

    run("init", "--quiet", "-b", "main")
    run("config", "user.email", "t@example.com")
    run("config", "user.name", "t")
    pyproject = root / "pyproject.toml"
    pyproject.write_text(f'[project]\nversion = "{base_version}"\n', encoding="utf-8")
    run("add", "pyproject.toml")
    run("commit", "--quiet", "-m", "base")
    if tag:
        run("tag", tag)
    pyproject.write_text(f'[project]\nversion = "{head_version}"\n', encoding="utf-8")
    return root


class TestTheCommand:
    @pytest.fixture
    def in_repo(self, check, tmp_path, monkeypatch):
        def build(base, head, tag=None):
            git_repo(tmp_path, base, head, tag)
            monkeypatch.setattr(check, "REPO_ROOT", tmp_path)
            return tmp_path

        return build

    def test_a_real_bump_passes(self, check, in_repo, capsys):
        in_repo("5.19.0", "5.20.0")
        assert check.main(["--base-ref", "main"], fetch=not_on_pypi) == 0
        assert "out-ranks" in capsys.readouterr().out

    def test_a_collision_exits_one_and_says_why(self, check, in_repo, capsys):
        in_repo("5.19.0", "5.19.0")
        assert check.main(["--base-ref", "main"], fetch=not_on_pypi) == 1
        assert "::error::" in capsys.readouterr().err

    def test_a_released_version_is_caught_through_real_tags(self, check, in_repo, capsys):
        in_repo("5.19.0", "5.20.0", tag="v5.20.0")
        assert check.main(["--base-ref", "main"], fetch=not_on_pypi) == 1
        assert "already released" in capsys.readouterr().err

    def test_the_base_ref_travels_into_the_message(self, check, in_repo, capsys):
        in_repo("5.19.0", "5.20.0")
        assert check.main(["--base-ref", "main"], fetch=not_on_pypi) == 0
        assert "main's" in capsys.readouterr().out


class TestItFailsReadably:
    def test_a_missing_base_ref_says_what_to_fetch(self, check, capsys):
        assert check.main(["--base-ref", "refs/heads/no-such-branch"]) == 1
        assert "cannot read" in capsys.readouterr().err

    def test_git_output_is_decoded_as_utf8(self, check):
        import inspect

        source = inspect.getsource(check._git)
        assert 'encoding="utf-8"' in source


class TestCIWiring:
    def test_the_version_bump_step_is_scoped_to_pull_request(self):
        ci_yml = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        steps = re.split(r"\n(?=      - name:)", ci_yml)
        matches = [
            s
            for s in steps
            if s.startswith("      - name: Version bump has not been lost to a collision")
        ]
        assert matches, "ci.yml no longer has the version-bump step under this name"
        assert "if: github.event_name == 'pull_request'" in matches[0], (
            "the version-bump step lost its pull_request guard -- it will fail "
            "unconditionally on every push to main"
        )


class TestUnreleased:
    def test_a_tagged_base_is_silent(self, check):
        assert check.unreleased("6.2.0", ["v6.1.0", "v6.2.0"]) is None

    def test_an_untagged_base_is_reported(self, check):
        found = check.unreleased("6.2.0", ["v6.1.0"])
        assert found is not None and "6.2.0" in found

    def test_it_names_the_command_that_fixes_it(self, check):
        found = check.unreleased("6.2.0", ["v6.1.0"])
        assert "git tag -a v6.2.0" in found
        assert "git push origin v6.2.0" in found

    def test_no_tags_at_all_is_reported_rather_than_crashing(self, check):
        assert check.unreleased("0.1.0", []) is not None

    def test_a_prefix_match_is_not_a_tag(self, check):
        assert check.unreleased("6.2.0", ["v6.2.0-rc1"]) is not None

    def test_a_patch_base_is_silent_once_its_minor_is_tagged(self, check):
        assert check.unreleased("6.2.3", ["v6.1.0", "v6.2.0"]) is None

    def test_a_patch_base_reports_its_untagged_minor_not_itself(self, check):
        found = check.unreleased("6.2.3", ["v6.1.0"])
        assert "git tag -a v6.2.0" in found
        assert "v6.2.3" not in found


class TestTheWarningDoesNotGate:
    def test_an_untagged_base_alone_still_exits_zero(self, check, monkeypatch, capsys):
        monkeypatch.setattr(check, "problems", lambda *a: [])
        monkeypatch.setattr(check, "unreleased", lambda *a: "a release is owed")
        monkeypatch.setattr(check, "_git", lambda *a: '[project]\nversion = "0.0.1"\n')
        assert check.main([], fetch=not_on_pypi) == 0
        assert "::warning::a release is owed" in capsys.readouterr().err

    def test_a_real_problem_still_exits_one(self, check, monkeypatch, capsys):
        monkeypatch.setattr(check, "problems", lambda *a: ["collision"])
        monkeypatch.setattr(check, "unreleased", lambda *a: "a release is owed")
        monkeypatch.setattr(check, "_git", lambda *a: '[project]\nversion = "0.0.1"\n')
        assert check.main([], fetch=not_on_pypi) == 1
        err = capsys.readouterr().err
        assert "::warning::" in err and "::error::collision" in err

    def test_a_tagged_base_emits_no_warning_at_all(self, check, monkeypatch, capsys):
        monkeypatch.setattr(check, "problems", lambda *a: [])
        monkeypatch.setattr(check, "unreleased", lambda *a: None)
        monkeypatch.setattr(check, "_git", lambda *a: '[project]\nversion = "0.0.1"\n')
        assert check.main([], fetch=not_on_pypi) == 0
        assert "::warning::" not in capsys.readouterr().err


class TestOnPyPI:
    def test_a_404_means_not_published(self, check):
        assert check.on_pypi("9.9.9", lambda url: False) is False

    def test_a_payload_means_published(self, check):
        assert check.on_pypi("0.1.1", lambda url: {"info": {}}) is True

    def test_a_transport_failure_is_unknown_not_an_answer(self, check):
        def boom(url):
            raise OSError("no network")

        assert check.on_pypi("1.0.0", boom) is None

    def test_an_unreadable_body_is_unknown(self, check):
        assert check.on_pypi("1.0.0", lambda url: None) is None

    def test_it_asks_about_the_distribution_not_the_import_package(self, check):
        seen = []
        check.on_pypi("1.2.3", lambda url: seen.append(url) or False)
        assert "chitragupta-cli/1.2.3" in seen[0]


class TestPyPIBlocks:
    def test_a_published_version_fails_the_check(self, check, monkeypatch, capsys):
        monkeypatch.setattr(check, "on_pypi", lambda *a: True)
        monkeypatch.setattr(check, "_git", lambda *a: '[project]\nversion = "0.0.1"\n')
        assert check.main([]) == 1
        assert "can never be re-uploaded" in capsys.readouterr().err

    def test_an_unreachable_pypi_warns_and_continues(self, check, monkeypatch, capsys):
        monkeypatch.setattr(check, "on_pypi", lambda *a: None)
        monkeypatch.setattr(check, "problems", lambda *a: [])
        monkeypatch.setattr(check, "unreleased", lambda *a: None)
        monkeypatch.setattr(check, "_git", lambda *a: '[project]\nversion = "0.0.1"\n')
        assert check.main([]) == 0
        assert "could not reach PyPI" in capsys.readouterr().err

    def test_offline_skips_the_network_entirely(self, check, monkeypatch, capsys):
        def boom(*_a):
            raise AssertionError("--offline must not touch the network")

        monkeypatch.setattr(check, "on_pypi", boom)
        monkeypatch.setattr(check, "problems", lambda *a: [])
        monkeypatch.setattr(check, "unreleased", lambda *a: None)
        monkeypatch.setattr(check, "_git", lambda *a: '[project]\nversion = "0.0.1"\n')
        assert check.main(["--offline"]) == 0
        assert "could not reach PyPI" not in capsys.readouterr().err


class TestTheTestsStayOffTheNetwork:
    def test_the_real_fetcher_is_still_what_ci_gets(self, check):
        import inspect

        assert inspect.signature(check.main).parameters["fetch"].default is check._fetch_json

    def test_the_tripwire_is_actually_installed(self, check):
        assert check.urllib.request.urlopen.__name__ == "tripwire"


class TestBlocksAMerge:
    def test_it_fetches_before_it_reads_and_blocks_on_a_problem(self, check, monkeypatch, capsys):
        order = []
        monkeypatch.setattr(check.subprocess, "run", lambda *a, **k: order.append(("fetch", a[0])))
        monkeypatch.setattr(check, "main", lambda argv: order.append(("check", argv)) or 1)

        assert check.blocks_a_merge() is True
        assert [step for step, _ in order] == ["fetch", "check"]
        assert order[0][1][:2] == ["git", "fetch"]
        assert "--tags" in order[0][1]
        assert order[1][1] == ["--offline"]
        captured = capsys.readouterr()
        assert "Refusing to merge" in captured.err
        assert "Refusing to merge" not in captured.out

    def test_a_sound_bump_does_not_block_and_says_nothing_extra(self, check, monkeypatch, capsys):
        monkeypatch.setattr(check.subprocess, "run", lambda *a, **k: None)
        monkeypatch.setattr(check, "main", lambda argv: 0)

        assert check.blocks_a_merge() is False
        assert "Refusing" not in capsys.readouterr().err

    def test_an_unreadable_base_ref_blocks_too(self, check, monkeypatch, capsys):
        monkeypatch.setattr(check.subprocess, "run", lambda *a, **k: None)
        monkeypatch.setattr(check, "main", lambda argv: 1)

        assert check.blocks_a_merge() is True
        assert "Refusing to merge" in capsys.readouterr().err

    def test_any_other_exit_code_proceeds(self, check, monkeypatch):
        monkeypatch.setattr(check.subprocess, "run", lambda *a, **k: None)
        monkeypatch.setattr(check, "main", lambda argv: 2)
        assert check.blocks_a_merge() is False

    def test_a_failed_fetch_does_not_raise(self, check, monkeypatch):
        calls = []

        def failing_run(*args, **kwargs):
            calls.append(kwargs.get("check"))
            return None

        monkeypatch.setattr(check.subprocess, "run", failing_run)
        monkeypatch.setattr(check, "main", lambda argv: 0)
        check.blocks_a_merge()
        assert calls == [False]


class TestFetchJson:
    @staticmethod
    def _stub_urlopen(check, monkeypatch, result):
        import contextlib

        @contextlib.contextmanager
        def fake(_url, timeout=None):
            if isinstance(result, Exception):
                raise result
            yield result

        monkeypatch.setattr(check.urllib.request, "urlopen", fake)

    def test_a_body_is_decoded(self, check, monkeypatch):
        class Body:
            @staticmethod
            def read():
                return b'{"info": {"version": "1.0.0"}}'

        self._stub_urlopen(check, monkeypatch, Body())
        assert check._fetch_json("https://example.invalid")["info"]["version"] == "1.0.0"

    def test_a_404_is_the_answer_not_a_failure(self, check, monkeypatch):
        err = check.urllib.error.HTTPError("u", 404, "Not Found", {}, None)
        self._stub_urlopen(check, monkeypatch, err)
        assert check._fetch_json("https://example.invalid") is False

    def test_any_other_http_status_is_unknown(self, check, monkeypatch):
        err = check.urllib.error.HTTPError("u", 503, "Unavailable", {}, None)
        self._stub_urlopen(check, monkeypatch, err)
        assert check._fetch_json("https://example.invalid") is None

    def test_a_transport_error_is_unknown(self, check, monkeypatch):
        self._stub_urlopen(check, monkeypatch, check.urllib.error.URLError("down"))
        assert check._fetch_json("https://example.invalid") is None

    def test_an_unparseable_body_is_unknown(self, check, monkeypatch):
        class Body:
            @staticmethod
            def read():
                return b"not json"

        self._stub_urlopen(check, monkeypatch, Body())
        assert check._fetch_json("https://example.invalid") is None
