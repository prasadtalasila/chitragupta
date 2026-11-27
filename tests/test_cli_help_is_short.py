import pytest

from chitragupta import corpus, draft
from chitragupta import __main__ as package_main
from chitragupta.enrich import __main__ as enrich_main
from chitragupta.review import __main__ as review_main
from tests.conftest import run_python


ENTRY_POINTS = {
    "chitragupta": package_main,
    "chitragupta.corpus": corpus,
    "chitragupta.draft": draft,
    "chitragupta.review": review_main,
    "chitragupta.enrich": enrich_main,
}

_MAX_DESCRIPTION_CHARS = 200

_MAX_HELP_LINES = 30


def _help(module_path):
    result = run_python("-m", module_path, "--help")
    assert result.returncode == 0, result.stderr
    return result.stdout


@pytest.mark.parametrize("module_path", sorted(ENTRY_POINTS))
class TestTheDescriptionIsASummary:
    def test_it_is_not_the_module_docstring(self, module_path):
        module = ENTRY_POINTS[module_path]
        assert module.DESCRIPTION != module.__doc__

    def test_it_is_one_short_sentence(self, module_path):
        description = ENTRY_POINTS[module_path].DESCRIPTION
        assert len(description) <= _MAX_DESCRIPTION_CHARS
        assert "\n\n" not in description


@pytest.mark.parametrize("module_path", sorted(ENTRY_POINTS))
class TestHelpStaysShort:
    def test_the_whole_help_fits_a_screen(self, module_path):
        text = _help(module_path)
        head, _, _ = text.partition("\nCommands:\n")
        assert len(head.splitlines()) <= _MAX_HELP_LINES
        if module_path != "chitragupta":
            assert len(text.splitlines()) <= _MAX_HELP_LINES

    def test_it_does_not_reprint_the_docstrings_prose(self, module_path):
        module = ENTRY_POINTS[module_path]
        assert "ARCHITECTURE.md" in module.__doc__
        assert "ARCHITECTURE.md" not in _help(module_path)
