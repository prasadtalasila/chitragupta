"""Checks that a bib file is what it looks like, before `bib_reader`
turns its entries into references: how many entries the raw text really
holds, and which citekeys more than one entry carries.

Split from `chitragupta/bib_reader.py` when issue 840's duplicate check
took it past the 250-line ceiling. The seam is the question asked: these
functions judge the *file* -- what bibtexparser dropped or returned
twice -- and stdlib is enough for that, where `bib_reader` is about the
entries it keeps and needs bibtexparser to have them at all.
"""

import re
from collections import Counter
from collections.abc import Collection

# @comment/@string/@preamble are legitimate BibTeX constructs that never
# show up in BibDatabase.entries (bibtexparser tracks them separately,
# not as dropped entries) -- `bib_reader.read_library` parses with common_strings=True,
# so a real export using any of these is plausible, and counting them as
# "entries" would fire a false discrepancy warning on a perfectly good file.
_NON_ENTRY_TYPES = {"comment", "string", "preamble"}
# BibTeX allows either `@type{...}` or `@type(...)` -- bibtexparser
# accepts both (PR #8 review) -- so a file using the paren form would be
# under-counted by a brace-only pattern, which could hide a genuine drop
# instead of just risking a false-positive warning on a good file.
_ENTRY_START_RE = re.compile(r"^@(\w+)\s*[{(]", re.MULTILINE)


def block_has_fields(body: str) -> bool:
    """Whether an `@`-block's body carries anything past its citekey.

    A Zotero export writes `@misc{key,\\n}` for an attachment saved with
    no metadata, and bibtexparser drops it -- correctly, since there is
    no title, author or year to lose. Counting it as an entry made the
    dropped-entry warning below fire on every sync against a perfectly
    healthy library (this project's own bibliography carries two such
    stubs), and a guard that cries wolf is worse than none: the run it
    needs to be believed on is the one where a real entry has unbalanced
    braces. So the test drawn here is bibtexparser's own -- no field
    means no entry -- and the two agree about what they are counting.

    `body` runs from just past the opening delimiter to the start of the
    next `@`-block, not to a matching close brace. That bound is the
    whole point: a forward brace-matcher would, on the *unbalanced* entry
    this warning exists to catch, run to end of file and swallow every
    entry after it -- silencing the warning in exactly the case it is
    for. One trailing `}`/`)` is stripped rather than matched, so a block
    whose last field value ends in a brace (`title = {T}\\n}`) is not
    mistaken for a contentless one.
    """
    body = body.rstrip()
    if body.endswith(("}", ")")):
        body = body[:-1].rstrip()
    _, comma, fields = body.partition(",")
    return bool(comma and fields.strip())


def count_raw_entries(text: str, kept_types: Collection[str] | None = None) -> int:
    """How many actual `@entrytype{...}`/`@entrytype(...)` blocks the raw
    file text has, independent of whether bibtexparser managed to parse
    each one.

    bibtexparser (both BibTexParser.parse and the customization hook)
    silently skips an entry it can't parse -- e.g. unbalanced braces --
    with no exception and no entry in the returned BibDatabase, so
    len(bib_database.entries) alone can't reveal a dropped entry.
    Comparing against this raw count is the only way `read_library` can
    tell "the file has exactly as many entries as it looks like" from
    "some entries silently vanished."

    Contentless stubs are excluded -- see `block_has_fields`. Every
    match bounds the previous one, including the @comment/@string/
    @preamble blocks filtered out afterwards: one of those sitting
    between two entries still ends the first entry's body.

    `kept_types`, when given, is every (lowercase) entry type the parser
    keeps; a block of any other type is one it ignores by design rather
    than loses, so it is not counted (issue 888).

    An `@type{` line inside a field value is not a block at all; see
    `_entry_starts`.
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
    field value (#965).

    An abstract or a `note` quoting BibTeX, wrapped by the exporter so
    that `@article{` starts a line, was counted as an entry: a phantom
    drop, exit 3 on every run, and `--remove-stale` refusing to prune.

    Two signs, either enough. **Depth:** an entry's body opens at brace
    depth 1 and a braced field value at 2 or deeper, so a line at depth
    1 or less is outside every value. **A blank line before it:** every
    exporter separates entries with one, and BibTeX quoted in a value
    almost never has one right before its `@`.

    Neither alone. Depth alone is the issue's suggestion and hides the
    case this count exists for: an entry with unbalanced braces leaves
    the depth raised for the rest of the file, so nothing after it would
    count -- the trap `block_has_fields` describes for a forward
    brace-matcher. The blank line alone would stop counting a real entry
    in a hand-kept file that does not separate its entries.
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
    return, warned when nonzero -- see `count_raw_entries` for why this
    comparison is the only way to see a drop at all.

    The count travels on `bib_reader.Library` (issue 841) rather than
    ending at the warning: a read that lost an entry must not drive
    `--remove-stale`, which would prune the lost paper's row."""
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


# Issue 840. bibtexparser does not require unique keys: two `@entry`
# blocks under one citekey both come back, and upserting both made the
# later one overwrite the earlier's ledger row -- title, DOI, PDF -- with
# nothing printed and exit 0. A hand-merged export, or two Better-BibTeX
# libraries with clashing key patterns, produces this routinely. Every
# entry under such a key is skipped rather than one picked, because
# picking is guessing which paper the draft author meant by it; the key
# is still reported as seen (`bib_reader.Library.seen_citekeys`), so the row it
# already has is neither listed as stale nor pruned while it is fixed.
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
