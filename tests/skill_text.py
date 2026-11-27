import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

_REFERENCE = re.compile(r"`(\.claude/skills(?:-common|/[^`\s/]+)/references/[^`\s]+\.md)`")


def collapsed(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def expanded(text: str) -> str:
    def splice(match):
        body = (REPO_ROOT / match.group(1)).read_text(encoding="utf-8")
        return f"{match.group(0)} {collapsed(body)}"

    return _REFERENCE.sub(splice, collapsed(text))


def skill_text(path: Path) -> str:
    return expanded(path.read_text(encoding="utf-8"))


_CITED = re.compile(
    r"`(\.claude/skills(?:-common|/[^`\s/]+)/references/[^`\s]+\.md)` (§\d+(?:(?:, | and )§\d+)*)"
)
_NUMBERED = re.compile(r"^## (\d+)\. ", re.MULTILINE)


def cited(text: str) -> set:
    return {
        (path, number)
        for path, sections in _CITED.findall(collapsed(text))
        for number in re.findall(r"§(\d+)", sections)
    }


def numbered_sections(reference: Path) -> list:
    path = reference.relative_to(REPO_ROOT).as_posix()
    return [(path, n) for n in _NUMBERED.findall(reference.read_text(encoding="utf-8"))]
