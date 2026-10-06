"""The pdf requirement is LuaLaTeX, never stated as pdflatex (#1022).

A pdf render runs LuaLaTeX (#996) and has no pdflatex fallback
(render_output/_pandoc.py `_require_pdf_toolchain`). pdflatex is still
right in three places -- the figure-layout probe, the author's own
thesis or book build, and history -- and none of those names it beside
pandoc as what a render needs, which is the shape every stale line had.
So this forbids that shape rather than the word: the hundred-odd
correct mentions need no allowlist, and a new requirement line written
the old way is caught. Whitespace is collapsed first so a line break
between the two words cannot hide a match.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ROOTS = ("docs", ".claude/skills", ".agents/skills", ".opencode/skills", "chitragupta", "assets")
FILES = ("README.md", "DEVELOPER.md", "AGENTS.md", "DEVELOPER-AGENTS.md", "SOUL.md")

_REQUIREMENT = re.compile(
    r"pandoc`?\s*(?:/|\+|and|or)\s*`?pdflatex|PDF with\s*`?pdflatex", re.IGNORECASE
)


def _texts():
    for root in ROOTS:
        for path in sorted((REPO_ROOT / root).rglob("*")):
            if path.suffix in {".md", ".py", ".lua"} and path.is_file():
                yield path
    for name in FILES:
        yield REPO_ROOT / name


def test_no_text_states_pdflatex_as_the_pdf_requirement():
    offenders = []
    for path in _texts():
        text = " ".join(path.read_text(encoding="utf-8").split())
        for match in _REQUIREMENT.finditer(text):
            context = text[max(match.start() - 50, 0) : match.end() + 15]
            offenders.append(f"{path.relative_to(REPO_ROOT)}: ...{context}...")
    assert offenders == []


def test_the_pattern_catches_each_shape_the_stale_lines_had():
    for stale in (
        "need pandoc/pdflatex on PATH",
        "| `pdf` | pandoc + `pdflatex` | |",
        "when `pandoc`/`pdflatex` are available",
        "when pandoc and pdflatex are\npresent",
        "this pipeline renders PDF with pdflatex",
    ):
        assert _REQUIREMENT.search(" ".join(stale.split())), stale
