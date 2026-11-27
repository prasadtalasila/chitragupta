"""Pandoc's braced citation form, `@{key}`, for `chitragupta/citation_gate.py`.

`_pandoc_cites` finds where each `@{` starts; this finds where it ends.
Standard library only.
"""

import bisect
import re

# `@{key}` takes any brace-balanced key without whitespace, which
# `PANDOC_KEY` cannot spell, so `[@{fabricated_2026}]` once passed the gate
# as 0 citations (#944). Past this length a scan reports what it has as a
# key no ledger holds: fail closed, and stay linear.
BRACED_KEY_LIMIT = 512


def _brace_index(text: str) -> tuple[dict, list]:
    """Each `{`'s matching `}` within its run of non-space characters,
    and where every whitespace character sits: one pass, so each `@{`
    then costs a lookup rather than a scan."""
    closes: dict[int, int] = {}
    stack: list[int] = []
    spaces = []
    for match in re.finditer(r"[{}]|\s", text):
        char = match.group()
        if char == "{":
            stack.append(match.start())
        elif char == "}":
            if stack:
                closes[stack.pop()] = match.start()
        else:
            stack.clear()
            spaces.append(match.start())
    return closes, spaces


def braced_keys(text: str, starts: list) -> "list[tuple[int, int, str]]":
    """(start, end, key) for every `@{key}` pandoc would read as a
    citation, given each one's (start, offset just past its `{`)."""
    if not starts:
        return []
    closes, spaces = _brace_index(text)
    found = []
    for start, body in starts:
        close = closes.get(body - 1)
        if close is not None and close - body <= BRACED_KEY_LIMIT:
            found.append((start, close + 1, text[body:close]))
            continue
        index = bisect.bisect_left(spaces, body)
        run_end = spaces[index] if index < len(spaces) else len(text)
        if run_end - body > BRACED_KEY_LIMIT:
            end = body + BRACED_KEY_LIMIT
            found.append((start, end, text[body:end]))
    return found
