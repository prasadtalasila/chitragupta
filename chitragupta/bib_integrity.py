"""Checks that a bib file is what it looks like, before `bib_reader`
turns its entries into references: how many entries the raw text really
holds, and which citekeys more than one entry carries.

Stdlib only, judging the file; split from `bib_reader.py` (#840).
"""

import re
from collections import Counter
from collections.abc import Collection

from chitragupta.citekey_safety import citekey_problem

# Never parsed entries, so counting them would false-alarm a good file.
_NON_ENTRY_TYPES = {"comment", "string", "preamble"}
# Both `@type{` and `@type(` (PR #8), or a paren-form file is under-counted
# and a genuine drop hidden.
_ENTRY_START_RE = re.compile(r"^@(\w+)\s*[{(]", re.MULTILINE)


def block_has_fields(body: str) -> bool:
    """Whether an `@`-block's body carries anything past its citekey.

    bibtexparser rightly drops a Zotero `@misc{key,\\n}` stub, and counting
    it made the drop warning cry wolf every sync. `body` runs to the next
    `@`-block, not a matched close brace: a brace-matcher would swallow the
    rest of the file on the unbalanced entry this warning exists to catch.
    One trailing `}`/`)` is stripped instead.
    """
    body = body.rstrip()
    if body.endswith(("}", ")")):
        body = body[:-1].rstrip()
    _, comma, fields = body.partition(",")
    return bool(comma and fields.strip())


def count_raw_entries(text: str, kept_types: Collection[str] | None = None) -> int:
    """How many actual `@entrytype{...}`/`@entrytype(...)` blocks the raw
    file text has, parsed or not.

    bibtexparser silently skips an entry it cannot parse, so this count is
    the only way to see a drop. Stubs are excluded (`block_has_fields`);
    filtered @comment-style blocks still bound their neighbours.
    `kept_types` excludes types the parser ignores by design (issue 888).
    """
    starts = _entry_starts(text)
    ends = [m.start() for m in starts[1:]] + [len(text)]
    return sum(
        1
        for m, end in zip(starts, ends)
        if _counted_type(m.group(1).lower(), kept_types) and block_has_fields(text[m.end() : end])
    )


def _entry_starts(text: str) -> list:
    """The `@type{` lines that open an entry, skipping those inside a
    field value (#965), which caused a phantom drop and exit 3 every run.

    Either sign suffices: brace depth <= 1, or a blank line before it.
    Depth alone stops counting after an unbalanced entry; the blank line
    alone misses a hand-kept file without separators.
    """
    starts, depth, scanned = [], 0, 0
    for match in _ENTRY_START_RE.finditer(text):
        start = match.start()
        depth += text.count("{", scanned, start) - text.count("}", scanned, start)
        scanned = start
        previous_line = text[text.rfind("\n", 0, max(start - 1, 0)) + 1 : max(start - 1, 0)]
        if depth <= 1 or not previous_line.strip():
            starts.append(match)
    return starts


def _counted_type(entry_type: str, kept_types: Collection[str] | None) -> bool:
    """Whether a block of `entry_type` is an entry the parser should return."""
    if entry_type in _NON_ENTRY_TYPES:
        return False
    return kept_types is None or entry_type in kept_types


def dropped_entries(
    raw_text: str, parsed_count: int, bib_name: str, kept_types: Collection[str] | None = None
) -> int:
    """How many entries the raw text holds that bibtexparser did not
    return, warned when nonzero. Carried on `bib_reader.Library`
    (issue 841) so a lossy read cannot drive `--remove-stale`."""
    raw_count = count_raw_entries(raw_text, kept_types)
    if parsed_count >= raw_count:
        return 0
    print(
        f"  WARNING: bibtexparser parsed {parsed_count} entries but "
        f"{bib_name} has {raw_count} @entry block(s) -- "
        f"{raw_count - parsed_count} may have been silently dropped "
        "(bibtexparser skips an entry it can't parse -- e.g. unbalanced "
        "braces/quotes -- without raising). Check the file by hand for "
        "an entry whose citekey doesn't show up in this run's output."
    )
    return raw_count - parsed_count


# Issue 840: two entries under one key made the later silently overwrite
# the earlier's row. Every such entry is skipped, never one picked (that is
# guessing which paper a key means); the key stays in `seen_citekeys`, so
# its row is not pruned meanwhile.
def duplicated_citekeys(entries, bib_name: str) -> tuple[str, ...]:
    """The citekeys more than one entry carries, in bib order, each warned."""
    counts = Counter(entry["ID"] for entry in entries)
    duplicated = tuple(key for key, count in counts.items() if count > 1)
    for key in duplicated:
        print(
            f"  WARNING skipping citekey {key!r}: {counts[key]} entries in "
            f"{bib_name} share it, so none of them is synced -- "
            "this project never guesses which paper a citekey means. Give each "
            "entry its own key in your reference manager, re-export, and re-run sync."
        )
    return duplicated


def unfilenameable_citekeys(entries, duplicated) -> tuple[str, ...]:
    """The citekeys that cannot be a filename, in bib order, each warned.

    Checked first: such a key would fail much later as an OSError, or
    write outside content/. Duplicated keys are already reported.
    """
    skipped = []
    for entry in entries:
        key = entry["ID"]
        problem = citekey_problem(key)
        if problem is None or key in duplicated:
            continue
        skipped.append(key)
        print(
            f"  WARNING skipping citekey {key!r}: {problem}. "
            "It is used directly as a filename (content/parsed/<citekey>.txt "
            "and the enrichment layer's own outputs), and this project never "
            "rewrites a citekey -- the bib file is the source of truth. Rename "
            "it in your reference manager, re-export, and re-run sync."
        )
    return tuple(skipped)
