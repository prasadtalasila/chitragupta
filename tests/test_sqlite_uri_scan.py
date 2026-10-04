"""#963's class: a sqlite `file:` URI built by string formatting.

Nothing under chitragupta/, scripts/ or bench/ may build one: a path
holding `?`, `#` or `%` silently names a different file. Build it with
chitragupta.ledger_paths.read_only_uri: `Path.absolute().as_uri()`,
with a UNC path's authority rewritten to the empty one sqlite accepts.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORMATTED_URI = re.compile(r"""f["']file:""")


def test_no_file_uri_is_built_by_formatting():
    offenders = [
        f"{path.relative_to(ROOT)}:{n}"
        for top in ("chitragupta", "scripts", "bench")
        for path in sorted((ROOT / top).rglob("*.py"))
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if FORMATTED_URI.search(line)
    ]
    assert offenders == []
