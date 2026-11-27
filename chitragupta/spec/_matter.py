"""Front matter, appendices and back matter: the outline's reserved ids.

Three part ids and five chapter ids are reserved (#1137, #1168):

- `{#front}`, `{#appendices}` and `{#back}` print no `\\part` page and
  each has one legal position: `\\frontmatter`, `\\appendix` and
  `\\backmatter` are switches, so a misplaced `{#back}` would unnumber
  every later chapter.
- `glossary`, `symbols`, `figures`, `tables` and `index` are generated
  pages: no unit, no sections, front or back matter only (the index
  back only, after the bibliography).

Imports nothing from `spec/__init__.py`, so it can be imported at its top.
"""

import re

FRONT = "front"
APPENDICES = "appendices"
BACK = "back"
_PARTS = (FRONT, APPENDICES, BACK)

# In the order `spec init` writes them under `{#back}`.
GENERATED = ("glossary", "symbols", "figures", "tables", "index")
INDEX = "index"

# The `- author:` line under the book's `#` title, beside `- reader:` and
# `- scope:`.
_AUTHOR = re.compile(r"^-\s*author:\s*(.*?)\s*$")


def author(title_lines: list[str]) -> str | None:
    """The book's author, from the lines under its `#` title, or None.

    Only those lines: an `- author:` in a chapter brief is about that
    chapter.
    """
    for line in title_lines:
        match = _AUTHOR.match(line)
        if match and match.group(1):
            return match.group(1)
    return None


def matter(entry: dict) -> str | None:
    """`front`, `appendices` or `back` for an entry in one of those parts
    (the part itself included), None for the main matter."""
    top = entry["ancestors"][0] if entry["ancestors"] else entry["id"]
    return top if top in _PARTS else None


def _misplaced_parts(parts: list[str]) -> list[str]:
    problems = []
    if FRONT in parts and parts[0] != FRONT:
        problems.append(
            f"`{FRONT}` is the front matter, so it must be the outline's first part; "
            f"`{parts[0]}` comes before it."
        )
    if BACK in parts and parts[-1] != BACK:
        problems.append(
            f"`{BACK}` is the back matter, so it must be the outline's last part; "
            f"`{parts[-1]}` comes after it."
        )
    if APPENDICES in parts:
        later = [part for part in parts[parts.index(APPENDICES) + 1 :] if part != BACK]
        if later:
            problems.append(
                f"`{APPENDICES}` must come after every other part and before `{BACK}`: "
                f"`{later[0]}` comes after it, and LaTeX would letter it as an appendix."
            )
    return problems


def _misplaced_id(entry: dict) -> str | None:
    if entry["id"] in _PARTS and entry["kind"] != "part":
        return (
            f"`{entry['id']}` is reserved for a part (a `##` heading): "
            f"`{entry['title']}` is a {entry['kind']}."
        )
    if entry["id"] in GENERATED:
        if entry["kind"] != "chapter" or matter(entry) not in (FRONT, BACK):
            return (
                f"`{entry['id']}` names a page the assembler generates, so it must be "
                f"a `###` chapter of `{FRONT}` or `{BACK}`: `{entry['title']}` is not."
            )
    if entry["id"] == INDEX and matter(entry) != BACK:
        return (
            f"`{INDEX}` is the book's index, which prints last, after the bibliography, "
            f"so it must be a `###` chapter of `{BACK}`, the back matter."
        )
    if entry["kind"] == "section" and entry["ancestors"][-1] in GENERATED:
        return (
            f"`{entry['ancestors'][-1]}` is a generated page and has no sections: "
            f"`{entry['id']}` is under it."
        )
    return None


def problems(units: list[dict]) -> list[str]:
    found = _misplaced_parts([entry["id"] for entry in units if entry["kind"] == "part"])
    for entry in units:
        problem = _misplaced_id(entry)
        if problem:
            found.append(problem)
    return found
