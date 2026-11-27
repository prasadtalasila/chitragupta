import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SIBLING_PIP = re.compile(r"""/\s*["']pip(\.exe)?["']|/pip(\.exe)?["'\s]""")


def test_the_pattern_catches_both_spellings_it_replaced():
    assert SIBLING_PIP.search('"CHITRAGUPTA_PIP": str(bin_dir / "pip"),')
    assert SIBLING_PIP.search('ensure_gpu_torch "$bin_dir/pip" "$bin_dir/python"')
    assert not SIBLING_PIP.search("rm -rf /root/.cache/pip/wheels")


def test_no_pip_path_is_built_beside_the_interpreter():
    offenders = [
        f"{path.relative_to(ROOT)}:{n}"
        for top in ("chitragupta", "scripts")
        for path in sorted((ROOT / top).rglob("*"))
        if path.suffix in (".py", ".sh")
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if SIBLING_PIP.search(line) and not line.lstrip().startswith("#")
    ]
    assert offenders == []
