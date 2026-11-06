"""`registry build --index` and `registry index`: the book index's two
commands (#1168), as `registry/_cli.py` dispatches them.

Split from that module, which holds the registry's other commands, to
keep both under docs/CODE-STANDARDS.md's C2 limit.
"""

import subprocess
import sys
from pathlib import Path

from chitragupta import spec
from chitragupta.registry import _index_finish, _index_report, _index_terms, _index_toml, _pages
from chitragupta.registry import build, registry_dir
from chitragupta.render_output._errors import ConversionError, MissingBinary
from chitragupta.render_output._markdown_to_latex import markdown_to_latex


def write_index(book, built: dict, target: Path) -> int:
    """`index-terms.json`, or a refusal that writes nothing (#1168): an
    `index.toml` naming a term that does not exist would otherwise index
    something other than what its author asked for."""
    doc, problems = _index_toml.read(spec.spec_dir(book))
    data: dict = {}
    if not problems:
        # `_linked` is the Glossary page's own reading of which symbols a
        # unit links to a term, so the index and the page cannot disagree.
        data, problems = _index_terms.table(
            built["terms"], _pages._linked(built), built["accepted"], doc
        )
    if problems:
        for problem in problems:
            print(f"  [index] {problem}", file=sys.stderr)
        print(
            f"\n  {len(problems)} problem(s) in index.toml; no {target.name} written.",
            file=sys.stderr,
        )
        return 1
    _pages.write(target, _index_terms.dumps(data))
    print(f"Wrote {target}.")
    return 0


def cmd_index(args) -> int:
    """The book's index from its typeset `.idx` (#1168): `book.ind`, or a
    refusal that writes neither it nor the report. Only numbered chapters
    and appendices are indexed: front and back matter are not."""
    built = build(args.book)
    units = [unit for unit in built["accepted"] if unit not in built["unnumbered"]]
    try:
        result = _index_finish.finish(Path(args.idx), units, markdown_to_latex)
    except MissingBinary as exc:
        print(f"[missing-binary] {exc}", file=sys.stderr)
        return 1
    except (ConversionError, OSError, subprocess.CalledProcessError) as exc:
        print(f"[conversion] pandoc could not convert the index: {exc}", file=sys.stderr)
        return 1
    if result.problems:
        for problem in result.problems:
            print(f"  [index] {problem}", file=sys.stderr)
        print(f"\n  {len(result.problems)} problem(s); no index written.", file=sys.stderr)
        return 1
    doc, problems = _index_toml.read(spec.spec_dir(args.book))
    for problem in problems:
        print(f"  [index] warning: {problem}", file=sys.stderr)
    found = _index_report.findings(result.data, result.sidecars, doc, units, result.dangling)
    report, _ = _index_report.write(
        registry_dir(args.book), result.data, result.sidecars, found, result.entries
    )
    print(_index_report.summary(result.entries, len(found), report))
    return 0
