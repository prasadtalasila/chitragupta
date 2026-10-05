"""#985's class: `pip` reached as a binary beside the interpreter.

On Windows the binary is `Scripts\\pip.exe`, so a path built by putting
`pip` next to `python` names nothing there. Every pip call under
chitragupta/ and scripts/ goes through `<python> -m pip` instead, which
needs only the interpreter that is already known to exist and is always
that interpreter's own pip.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# `bin_dir / "pip"` in Python and `"$bin_dir/pip"` in a shell script;
# a cache directory such as `~/.cache/pip/` is not a binary, so a `pip`
# followed by another path segment does not match.
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
