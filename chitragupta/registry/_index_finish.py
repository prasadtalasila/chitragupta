"""`registry index`: turn a typeset book's `book.idx` into its index (#1168).

The second LaTeX pass after `bibtexu` leaves `book.idx` holding one line
per `\\index{<id>}` the filter placed, each with the page it fell on.
This reads that file, the term table and every indexed chapter's sidecar
(all beside `book.idx`, where the book's fragments render), writes
`book-index.idx` with each id replaced by its printed entry, writes
`book.ist`, and runs `upmendex`, leaving `book.ind` for the last LaTeX
pass to print.

**Only the key changes.** hyperref wraps each entry's page in its own
macro (`|hyperpage`, `|hyperxindexformat{\\textbf}`); that suffix and the
page are copied verbatim, and the parser never names the macro.
`book.idx` itself is left alone, so this reruns safely.

**A stale build refuses.** An id the term table does not hold, a chapter
with no sidecar, or a sidecar rendered against an older table means
some chapter's entries no longer match the table: printing them would
put pages under the wrong term, so nothing is written.
"""

import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from chitragupta import config, programs
from chitragupta.registry import _index_entries
from chitragupta.registry._index_terms import TERMS_JSON
from chitragupta.render_output._index_terms import sidecar_path

STYLE = config.shipped("assets", "latex", "chitragupta-index.ist")


@dataclass
class Result:
    """What one run did: problems refuse; `dangling` cross-references are
    reported and left out."""

    problems: "list[str]" = field(default_factory=list)
    dangling: "list[str]" = field(default_factory=list)
    entries: int = 0
    data: "dict | None" = None
    sidecars: dict = field(default_factory=dict)


def digest(path: Path) -> str:
    """The SHA-1 the filter records of the term table it read."""
    return hashlib.sha1(Path(path).read_bytes()).hexdigest()


def _argument(text: str, start: int) -> "tuple[str, int] | None":
    """The brace-balanced argument opening at `text[start]`, and the
    index after it."""
    if start >= len(text) or text[start] != "{":
        return None
    depth = 0
    for index in range(start, len(text)):
        depth += {"{": 1, "}": -1}.get(text[index], 0)
        if depth == 0:
            return text[start + 1 : index], index + 1
    return None


def parse(text: str) -> "list[tuple[str, str, str]]":
    """`(id, encap, page)` for each `\\indexentry` line of a `.idx`."""
    found = []
    for line in text.splitlines():
        key = _argument(line, len("\\indexentry")) if line.startswith("\\indexentry") else None
        page = key and _argument(line, key[1])
        if page:
            ident, bar, encap = key[0].partition("|")
            found.append((ident, bar + encap, page[0]))
    return found


def _sidecars(directory: Path, units: "list[str]", want: str) -> "tuple[dict, list[str]]":
    found, problems = {}, []
    for unit in units:
        path = sidecar_path(directory, unit)
        if not path.is_file():
            problems.append(f"{unit} has no {path.name}: re-render it with --index-terms.")
            continue
        side = json.loads(path.read_text(encoding="utf-8"))
        if side.get("terms_digest") != want:
            problems.append(
                f"{unit} was rendered against an older term table: re-render it with --index-terms."
            )
        found[unit] = side
    return found, problems


def midsentence(sidecars: dict) -> "dict[str, dict[str, int]]":
    """Each term's mid-sentence casing counts, summed over the chapters."""
    merged: dict[str, dict[str, int]] = {}
    for side in sidecars.values():
        for tid, entry in (side["terms"] or {}).items():
            bucket = merged.setdefault(tid, {})
            for surface, count in entry["midsentence"].items():
                bucket[surface] = bucket.get(surface, 0) + count
    return merged


def _inputs(idx: Path, units: "list[str]", result: Result) -> "list[tuple[str, str, str]]":
    """The parsed `.idx`, with `result` holding the table, the sidecars
    and every reason the build is stale."""
    terms = idx.parent / TERMS_JSON
    if not terms.is_file():
        result.problems.append(
            f"No {TERMS_JSON} beside {idx.name}: run `registry build --index` first."
        )
        return []
    if not idx.is_file():
        result.problems.append(f"No {idx.name}: run lualatex on the book first.")
        return []
    result.data = json.loads(terms.read_text(encoding="utf-8"))
    result.sidecars, result.problems = _sidecars(idx.parent, units, digest(terms))
    entries = parse(idx.read_text(encoding="utf-8"))
    result.problems += [
        f"{idx.name} holds {ident}, which {TERMS_JSON} does not: rebuild the term "
        "table, re-render the chapters with --index-terms, and typeset again."
        for ident in sorted({ident for ident, _, _ in entries} - set(result.data["terms"]))
    ]
    return entries


def _upmendex(idx: Path, rewritten: Path, data: dict, run, result: Result) -> None:
    program = programs.resolve_program("upmendex")
    if program is None:
        result.problems.append(
            "[missing-binary] upmendex not found: it ships with TeX Live (texlive-binaries); "
            "`chitragupta install os-deps` installs it."
        )
        return
    style = idx.with_suffix(".ist")
    template = STYLE.read_text(encoding="utf-8")
    style.write_text(
        template.replace("@HEADINGS@", "1" if data["letter_headings"] else "0"), encoding="utf-8"
    )
    letter = ["-l"] if data["sort"] == "letter" else []
    ind, log = idx.with_suffix(".ind"), idx.with_suffix(".ilg")
    ind.unlink(missing_ok=True)
    # Relative names, run in the book's own directory: TeX Live's
    # `openout_any = p` makes upmendex refuse an absolute output path, and
    # it then exits 0 having printed the index to stdout instead.
    argv = [program, "-q", *letter, "-s", style.name, "-o", ind.name, "-t", log.name]
    completed = run(
        [*argv, rewritten.name], cwd=idx.parent, capture_output=True, text=True, check=False
    )
    if completed.returncode != 0 or not ind.is_file():
        said = log.read_text(encoding="utf-8") if log.is_file() else ""
        result.problems.append(
            f"upmendex failed ({completed.returncode}); {log.name}:\n{said}{completed.stderr}"
        )


def finish(idx: Path, units: "list[str]", convert, run=None) -> Result:
    """Write `book-index.idx`, `book.ist` and, through `upmendex`,
    `book.ind`, from `idx` and the sidecars of `units`. `convert` is
    `markdown_to_latex`."""
    idx, result, run = Path(idx), Result(), run or subprocess.run
    entries = _inputs(idx, units, result)
    if result.problems:
        return result
    keys, printed = _index_entries.keys(result.data, midsentence(result.sidecars), convert)
    lines = [
        f"\\indexentry{{{key}{encap}}}{{{page}}}"
        for ident, encap, page in entries
        for key in keys[ident]
    ]
    pages: dict[str, str] = {}
    for ident, _, page in entries:
        pages.setdefault(ident, page)
    more, result.dangling = _index_entries.cross_references(result.data, printed, pages, convert)
    rewritten = idx.with_name(f"{idx.stem}-index.idx")
    rewritten.write_text("\n".join(lines + more) + "\n", encoding="utf-8")
    result.entries = len(entries)
    _upmendex(idx, rewritten, result.data, run, result)
    return result
