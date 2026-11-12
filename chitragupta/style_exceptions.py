"""The project's list of terms no prose rule should report (#1187).

`content/style_exceptions.toml` holds `terms = [...]`: exact strings
(proper names such as "Unified Process") that no prose rule reports and
the verbatim scan masks, in every draft under every dialect. Acronym
expansions from `acronyms.load_vocabulary()` are exceptions already, so
`terms()` adds them; the file lists only the rest.

It is project data, unlike the per-host verbatim allowlist: absent means
no terms. A present file that does not parse, cannot be read, has a key
other than `terms`, or has a `terms` that is not a list of non-empty
strings raises ValueError, following verbatim_check/_allowlist.py rather
than acronyms._load's skip-with-note. A broken exceptions file that
silently loaded as empty would turn suppressed findings back into
unattended edits, which is exactly the failure #1187 is about.
"""

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
    case-insensitively (first spelling wins, file terms first), longest
    first so a caller matching in order meets the longest term first."""
    seen: dict[str, str] = {}
    for term in (*file_terms(), *acronyms.load_vocabulary().values()):
        seen.setdefault(term.lower(), term)
    return tuple(sorted(seen.values(), key=len, reverse=True))
