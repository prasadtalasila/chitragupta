"""The project's list of terms no prose rule should report (#1187).

`content/style_exceptions.toml` holds `terms = [...]`, exact strings that
no prose rule reports and the verbatim scan masks; acronym expansions are
added by `terms()`. Absent means no terms, but a malformed file raises
ValueError: silently loading as empty would turn suppressed findings back
into unattended edits, the failure #1187 is about.
"""

import re
import tomllib

from chitragupta import acronyms, config


def file_terms() -> tuple[str, ...]:
    """The file's terms, stripped, in file order; `()` when it is absent."""
    path = config.STYLE_EXCEPTIONS_PATH
    if not path.exists():
        return ()
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"{path}: malformed TOML -- {exc}") from None
    except OSError as exc:
        raise ValueError(f"{path}: cannot read style exceptions -- {exc}") from None

    unknown = sorted(set(data) - {"terms"})
    if unknown:
        raise ValueError(f"{path}: unknown key(s) {unknown} -- expected only ['terms']")
    values = data.get("terms", [])
    if not isinstance(values, list) or not all(isinstance(v, str) and v.strip() for v in values):
        raise ValueError(f"{path}: 'terms' must be a list of non-empty strings")
    return tuple(v.strip() for v in values)


def terms() -> tuple[str, ...]:
    """File terms plus every acronym expansion, de-duplicated
    case-insensitively (first spelling wins), longest first."""
    seen: dict[str, str] = {}
    for term in (*file_terms(), *acronyms.load_vocabulary().values()):
        seen.setdefault(term.lower(), term)
    return tuple(sorted(seen.values(), key=len, reverse=True))


def drop_exempt(findings: list[dict], text: str) -> list[dict]:
    """`findings` minus those lying wholly inside a declared term (#1187).

    Done here because Vale's `exceptions` are per-token and cannot see a
    multi-word name. `chitragupta.Acronyms` is never dropped: it asks
    whether an acronym was expanded, not about spelling. Vale's `Span`
    columns are 1-based, inclusive and in characters (vale 3.26.0), so
    they index the Python string directly.
    """
    lines = text.split("\n")  # vale counts lines by "\n" only
    pattern = "|".join(re.escape(t) for t in terms())
    regex = re.compile(rf"(?<!\w)(?:{pattern})(?!\w)", re.IGNORECASE) if pattern else None
    kept = []
    for finding in findings:
        if (
            finding.get("Check") != "chitragupta.Acronyms"
            and regex
            and _inside(finding, lines, regex)
        ):
            continue
        kept.append(finding)
    return kept


def _inside(finding: dict, lines: list[str], regex: re.Pattern) -> bool:
    """Whether the finding's span lies wholly within one term occurrence."""
    number = finding.get("Line", 0)
    if not 1 <= number <= len(lines):
        return False
    start, end = finding["Span"]
    return any(m.start() < start and end <= m.end() for m in regex.finditer(lines[number - 1]))
