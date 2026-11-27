import re
from pathlib import Path

import pytest

from chitragupta.citekey_safety import UnsafeCitekey, citekey_path

ROOT = Path(__file__).resolve().parent.parent
HELPER = ROOT / "chitragupta" / "citekey_safety.py"
PATH_JOIN = re.compile(r"""/\s*f["']\{(?:\w+\.)?citekey\}|/\s*f["']\{stem\}""")


class TestCitekeyPath:
    def test_a_safe_citekey_lands_directly_in_the_directory(self, tmp_path):
        assert citekey_path(tmp_path, "smith2024", ".json") == tmp_path / "smith2024.json"

    @pytest.mark.parametrize(
        "citekey", ["../x", "../../etc/passwd", "a/b", "a\\b", "..", ".", "", "CON"]
    )
    def test_an_unsafe_citekey_is_refused(self, tmp_path, citekey):
        with pytest.raises(UnsafeCitekey, match="cannot name a file"):
            citekey_path(tmp_path, citekey, ".json")

    def test_the_refusal_is_a_value_error(self, tmp_path):
        with pytest.raises(ValueError):
            citekey_path(tmp_path, "../x", ".json")


def test_no_citekey_is_joined_into_a_path_outside_the_helper():
    offenders = [
        f"{path.relative_to(ROOT)}:{n}"
        for top in ("chitragupta", "scripts")
        for path in sorted((ROOT / top).rglob("*.py"))
        if path != HELPER
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if PATH_JOIN.search(line)
    ]
    assert offenders == []
