"""The writing standards are one core file and a folder of layer files,
and every citation into them still lands.

Issue 1197 (part of #1091) split `docs/WRITING-STANDARDS.md` into a core
and `docs/writing-standards/`: one file per element a draft contains
(figures, mathematics, tables, the page), a folder for genres and one
for house styles. Section numbers stay global, so `§12` names the same
rules wherever they live, and the core keeps a stub heading for every
section that moved.

What the split can break is invisible in the file it changes. Skills
cite `WRITING-STANDARDS.md` §N well over a hundred times across their
three harness copies, `chitragupta/style_*` prints §N in every finding,
and other documents link to headings by anchor. A section moved with no
stub, a number reused by a new layer file, or a layer file nobody can
find from the core would each leave those citations pointing at nothing,
and no other test reads them. These four do.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS = REPO_ROOT / "docs"
CORE = DOCS / "WRITING-STANDARDS.md"
LAYERS = DOCS / "writing-standards"

# Where a citation can come from: every tree a model, a user or a
# finding message reads. `.claude/worktrees/` holds whole nested
# checkouts of this repository and is never scanned.
_SCANNED_ROOTS = (".claude", ".agents", ".opencode", "docs", "chitragupta")
_SCANNED_FILES = ("AGENTS.md", "SOUL.md")
_TEXT_SUFFIXES = {".md", ".py", ".toml", ".yml", ".yaml", ".txt", ".tex", ".sh"}

_FENCE = re.compile(r"^(```+|~~~+).*?^\1\s*$", re.MULTILINE | re.DOTALL)
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
_NUMBERED = re.compile(r"^#{2,3}\s+(?:\S+\s+)?(\d+)\.\s", re.MULTILINE)
_SECTION_HEAD = re.compile(r"^## ", re.MULTILINE)

# A path into the standards, then one or more sections: "§12",
# "§10, §12 and §13", "section 8". Backticks, a link's closing bracket
# and a comma may sit between the path and the first section.
_PATH = r"(?P<path>WRITING-STANDARDS(?:\.md)?|writing-standards/(?:[\w-]+/)*[\w-]+\.md)"
_CITATION = re.compile(
    _PATH + r"[`)\]]*[,:]?\s*(?P<sections>(?:§\s?|section\s)\d+"
    r"(?:(?:,\s|\sand\s|\sor\s)(?:§\s?|section\s)\d+)*)"
)
_ANCHOR = re.compile(r"\]\((?P<target>[^)\s#]*)#(?P<anchor>[^)\s]+)\)")


def _without_fences(text: str) -> str:
    """`text` with fenced blocks blanked: an example `## Symbols` inside a
    fence is content, not a heading."""
    return _FENCE.sub(lambda match: "\n" * match.group(0).count("\n"), text)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _layer_files() -> "list[Path]":
    return sorted(LAYERS.rglob("*.md")) if LAYERS.is_dir() else []


def _numbered_files() -> "list[Path]":
    """The files that may hold a numbered section: the core and every
    layer file but the folder READMEs."""
    return [CORE] + [path for path in _layer_files() if path.name != "README.md"]


def _scanned() -> "list[Path]":
    found = [REPO_ROOT / name for name in _SCANNED_FILES]
    for root in _SCANNED_ROOTS:
        for path in sorted((REPO_ROOT / root).rglob("*")):
            relative = path.relative_to(REPO_ROOT).parts
            if path.is_file() and path.suffix in _TEXT_SUFFIXES and "worktrees" not in relative:
                found.append(path)
    return found


def _numbers(path: Path) -> "list[int]":
    return [int(number) for number in _NUMBERED.findall(_without_fences(_read(path)))]


def _slug(heading: str) -> str:
    """GitHub's anchor for a heading, which `mkdocs.yml` also uses: lower
    case, punctuation and emoji dropped, each space a hyphen."""
    return re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")


def _anchors(path: Path) -> "set[str]":
    """Every anchor `path`'s headings produce, with GitHub's `-1`, `-2`
    suffix on a repeated one."""
    seen: "dict[str, int]" = {}
    anchors = set()
    for _, heading in _HEADING.findall(_without_fences(_read(path))):
        slug = _slug(heading)
        anchors.add(f"{slug}-{seen[slug]}" if slug in seen else slug)
        seen[slug] = seen.get(slug, 0) + 1
    return anchors


def _resolve(cited: str) -> Path:
    """The file a cited path names: the core, or a layer file."""
    if cited.startswith("WRITING-STANDARDS"):
        return CORE
    return DOCS / cited


def _index_targets() -> "set[Path]":
    """The files the core's index table links to, or an empty set when
    the core has no index section."""
    sections = _SECTION_HEAD.split(_without_fences(_read(CORE)))
    index = [body for body in sections if "index" in body.split("\n", 1)[0].lower()]
    assert index, "docs/WRITING-STANDARDS.md has no `## ... index` section"
    rows = [line for line in index[0].splitlines() if line.startswith("|")]
    links = re.findall(r"\]\(([^)#\s]+\.md)\)", "\n".join(rows))
    return {(DOCS / link).resolve() for link in links}


def test_every_file_is_in_the_index():
    targets = _index_targets()
    missing = [
        str(path.relative_to(REPO_ROOT)) for path in _layer_files() if path.resolve() not in targets
    ]
    assert not missing, f"not linked from the core's index table: {missing}"


def test_every_cited_section_resolves():
    numbers = {path: set(_numbers(path)) for path in _numbered_files()}
    broken = []
    for source in _scanned():
        text = re.sub(r"\s+", " ", _read(source))
        for match in _CITATION.finditer(text):
            target = _resolve(match.group("path"))
            for number in re.findall(r"\d+", match.group("sections")):
                if int(number) not in numbers.get(target, set()):
                    broken.append(f"{source.relative_to(REPO_ROOT)}: {match.group(0)}")
    assert not broken, f"cites a section no heading carries: {broken}"


def test_every_anchor_resolves():
    """A link to `WRITING-STANDARDS.md#<anchor>` from anywhere, and a
    same-file `#<anchor>` link inside the core or a layer file, lands on
    a heading."""
    broken = []
    for source in _scanned():
        for match in _ANCHOR.finditer(_read(source)):
            target = match.group("target")
            if target.endswith("WRITING-STANDARDS.md"):
                file = CORE
            elif target == "" and source in [CORE, *_layer_files()]:
                file = source
            elif "writing-standards/" in target:
                file = (source.parent / target).resolve()
            else:
                continue
            if match.group("anchor") not in _anchors(file):
                broken.append(f"{source.relative_to(REPO_ROOT)}: {match.group(0)}")
    assert not broken, f"anchors no heading produces: {broken}"


def _stubbed(number: int, holder: Path) -> bool:
    """Whether the core's section `number` is a stub pointing at `holder`."""
    for body in _SECTION_HEAD.split(_without_fences(_read(CORE))):
        heading = body.split("\n", 1)[0]
        if re.match(rf"(?:\S+\s+)?{number}\.\s", heading):
            return f"writing-standards/{holder.relative_to(LAYERS).as_posix()}" in body
    return False


def test_section_numbers_are_unique():
    """No number heads two sections, except the core's stub for a section
    that moved, which must point at the one file holding it now."""
    core = _numbers(CORE)
    clashes = sorted({number for number in core if core.count(number) > 1})
    holders: "dict[int, list[Path]]" = {}
    for path in _numbered_files()[1:]:
        for number in _numbers(path):
            holders.setdefault(number, []).append(path)
    for number, paths in sorted(holders.items()):
        if len(paths) > 1 or (number in core and not _stubbed(number, paths[0])):
            clashes.append(number)
    assert not clashes, f"section numbers heading two sections: {clashes}"
