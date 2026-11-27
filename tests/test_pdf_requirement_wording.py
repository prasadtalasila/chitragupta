import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ROOTS = (
    "docs",
    ".claude/skills",
    ".claude/skills-common",
    ".agents/skills",
    ".opencode/skills",
    "chitragupta",
    "assets",
)
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
