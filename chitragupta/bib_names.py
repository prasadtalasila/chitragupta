"""How a BibTeX author name divides into given and family name.

One function, and it exists because the five lines below used to exist
twice -- character for character -- in `chitragupta/bib_reader.py`'s
`_parse_authors` and `chitragupta/references.py`'s `_format_name`. `pylint`'s
`duplicate-code` found that during the 5.8.0 baseline measurement; nobody
found it by reading.

The duplication was quiet in a specific and bad way.
[DEVELOPER-AGENTS.md](../DEVELOPER-AGENTS.md)'s module boundary says
`references.py` must never parse `bibliography.bib`, and it does not --
it reads the ledger's `bib_fields` column, exactly as required. But that
boundary is about *the file*. What was duplicated is the **grammar**, and
`references.py` obeyed the letter of the rule while carrying a second,
independently-maintained copy of `bib_reader`'s most subtle parsing.
Extend one side for a case the grammar does not handle today -- a `von`
particle, a `Jr.` suffix, a second comma -- and the other keeps the old
reading, so the ledger records one name and the rendered bibliography
prints a different one for the same entry, with nothing failing. On a
tool whose whole purpose is citations you can trust, two disagreeing
spellings of an author is the wrong kind of quiet.

**Stdlib-only, and deliberately import-free.** `references.py` is tier-1
code that has to run under the bare system interpreter with no venv (see
its own module docstring, and AGENTS.md on `python -m chitragupta.draft gate`),
while `bib_reader.py` needs `bibtexparser`. A shared helper that reached
for anything at all would either drag a dependency into tier 1 or invert
the layering; this is plain string handling, so it needs neither. That is
enforced rather than asserted, and by a test that already existed:
`tests/test_references.py::test_runs_with_bare_system_python3` runs
`python -m chitragupta.draft references` on the system interpreter, which now
imports this module, so an import added here that a venv-less host cannot
satisfy fails there. No second check was added for it.
"""


def split_name(name: str) -> tuple[str, str]:
    """`name` as `(given, family)`.

    "Doe, Jane" -> ("Jane", "Doe"); "Jane Doe" -> ("Jane", "Doe");
    "Cher" -> ("", "Cher").

    `name` is expected already stripped -- both call sites strip it for
    their own reasons before getting here (`_parse_authors` to test
    whether the segment is empty at all, `_format_name` to recognise a
    braced corporate author), so stripping again would be defensive
    handling for a state that cannot occur.

    What this deliberately does *not* handle is anything neither call
    site handled before it existed: `von`/`van der` particles, `Jr.` and
    other suffixes, and BibTeX's three-part `von Last, Jr, First` form
    all read the same way they always did. #234 moved the grammar; it did
    not make it more capable. Making it so is a change to make here,
    once, which is the entire point.
    """
    if "," in name:
        last, first = (p.strip() for p in name.split(",", 1))
    else:
        parts = name.rsplit(" ", 1)
        first, last = (parts[0], parts[1]) if len(parts) == 2 else ("", parts[0])
    return first, last
