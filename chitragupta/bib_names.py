"""How a BibTeX author name divides into given and family name.

The one copy of a grammar `bib_reader._parse_authors` and
`references_ieee._format_name` once each carried (#234): extending one
copy alone would have made the ledger and the rendered bibliography
disagree about an author, silently.

Stdlib-only and import-free: the references path is tier 1 under bare
python3, while `bib_reader` needs bibtexparser.
`tests/test_references.py::test_runs_with_bare_system_python3` enforces
it.
"""


def split_name(name: str) -> tuple[str, str]:
    """`name` as `(given, family)`.

    "Doe, Jane" -> ("Jane", "Doe"); "Jane Doe" -> ("Jane", "Doe");
    "Cher" -> ("", "Cher").

    `name` is expected already stripped (both callers strip it). `von`
    particles, `Jr.` suffixes and the three-part form are not handled; a
    change to that belongs here, once.
    """
    if "," in name:
        last, first = (p.strip() for p in name.split(",", 1))
    else:
        parts = name.rsplit(" ", 1)
        first, last = (parts[0], parts[1]) if len(parts) == 2 else ("", parts[0])
    return first, last
