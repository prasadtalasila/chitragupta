"""`structure.md`: the human's own outline for a single-draft dossier
(#455) -- a heading, a `brief:` and/or one or more `claim:` blocks, and
optional declared `queries:` a genre skill runs verbatim instead of
inventing sub-themes.

This reads and validates only. It never calls retrieval and never
writes `sections.md`/`evidence.md` -- that stays the deciding skill's
job, the same layer boundary `retrieval_cli` (retrieves and logs) vs.
the skill (decides what's kept) already holds everywhere else. See
plans/outline-driven-drafting-and-manual-edits.md, "PR 2: an outline
the human writes", "What this explicitly does not do".

Deliberately a sibling to `scope.md`, not a second `spec.md`: `spec.md`
is the book track's own human-authored outline, at book scale, with its
own `spec sign` gate. This file never applies to a book unit.
"""

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from chitragupta.dossier import STRUCTURE_MD, _resolve_dossier, draft_relpath
from chitragupta.dossier._retrieval import recorded_queries_with_origin

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_BRIEF = re.compile(r"^brief:\s*(.*)$", re.IGNORECASE)
_CLAIM = re.compile(r"^claim:\s*(.*)$", re.IGNORECASE)
_QUERIES_LABEL = re.compile(r"^queries:\s*$", re.IGNORECASE)
_QUERY_ITEM = re.compile(r"^-\s+(.*)$")


@dataclass
class StructureSection:
    """One `##` heading's declared intent: steering (`brief`), content to
    ground (`claim`, zero or more), and the queries a skill runs verbatim
    for this section. `brief` and `claim` combine -- each carries its own
    explicit label, so there is no ambiguity left for the two to resolve
    by being mutually exclusive."""

    heading: str
    brief: str = ""
    claims: list[str] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)


@dataclass
class StructureProblem:
    heading: str
    problem: str


@dataclass
class Structure:
    sections: "dict[str, StructureSection]" = field(default_factory=dict)
    problems: list[StructureProblem] = field(default_factory=list)


class _Parser:
    """One pass over `structure.md`'s lines, tracked as a small state
    machine so `parse` itself stays a dispatch loop -- see that
    function's docstring for what the result means.

    `mode` is which label is currently accumulating prose: `"brief"`,
    `"claim"`, `"queries"`, or `None` between labels. `buffer` holds that
    label's lines until the next label, heading, or end of file flushes
    it into `section`.
    """

    def __init__(self) -> None:
        self.result = Structure()
        self.section: "StructureSection | None" = None
        self.mode: "str | None" = None
        self.buffer: list[str] = []

    def flush(self) -> None:
        if self.section is not None and self.mode is not None:
            block = "\n".join(self.buffer).strip()
            if self.mode == "brief":
                self.section.brief = block
            elif self.mode == "claim" and block:
                self.section.claims.append(block)
        self.buffer = []

    def start_heading(self, heading: str) -> None:
        self.flush()
        self.section = StructureSection(heading=heading)
        self.result.sections[heading] = self.section
        self.mode = None

    def start_brief(self, first: str) -> None:
        self.flush()
        if self.section.brief:
            self.problem("more than one brief: block")
        self.mode = "brief"
        self.buffer = [first] if first else []

    def start_claim(self, first: str) -> None:
        self.flush()
        self.mode = "claim"
        self.buffer = [first] if first else []

    def start_queries(self) -> None:
        self.flush()
        self.mode = "queries"

    def add_query_line(self, line: str) -> None:
        item = _QUERY_ITEM.match(line)
        if item:
            query = item.group(1).strip()
            if query:
                self.section.queries.append(query)
        elif line.strip():
            self.problem(f"queries: expects a `- ` bullet, not {line!r}")

    def add_line(self, raw_line: str, line: str) -> None:
        if self.mode in ("brief", "claim"):
            self.buffer.append(raw_line)
        elif line.strip() and not line.lstrip().startswith("<!--"):
            self.problem(f"unrecognised line: {line!r}")

    def problem(self, text: str) -> None:
        self.result.problems.append(StructureProblem(self.section.heading, text))

    def dispatch(self, raw_line: str) -> None:
        line = raw_line.rstrip()
        heading_match = _HEADING.match(line)
        if heading_match:
            self.start_heading(heading_match.group(2).strip())
        elif self.section is None:
            return  # preamble before the first heading -- a title, a comment
        elif brief_match := _BRIEF.match(line):
            self.start_brief(brief_match.group(1))
        elif claim_match := _CLAIM.match(line):
            self.start_claim(claim_match.group(1))
        elif _QUERIES_LABEL.match(line):
            self.start_queries()
        elif self.mode == "queries":
            self.add_query_line(line)
        else:
            self.add_line(raw_line, line)

    def finish(self) -> Structure:
        self.flush()
        for heading, section in self.result.sections.items():
            if not section.brief and not section.claims:
                self.problem_for(heading, "neither a brief: nor a claim: block")
        return self.result

    def problem_for(self, heading: str, text: str) -> None:
        self.result.problems.append(StructureProblem(heading, text))


def parse(text: str) -> Structure:
    """`structure.md`'s text into one `StructureSection` per `##`-or-deeper
    heading, plus whatever's wrong with it.

    Advisory about *shape*, not about content -- a heading with neither a
    `brief:` nor a `claim:` block is reported (nothing else has anything
    to write that section from), but a `brief:`/`claim:` with only
    whitespace after it is not: an empty steering paragraph is a human
    mid-edit, not a malformed file.
    """
    parser = _Parser()
    for raw_line in text.splitlines():
        parser.dispatch(raw_line)
    return parser.finish()


@dataclass
class SectionDrift:
    """One `structure.md` section's declared queries, split by whether
    `retrieval.md` shows them actually run verbatim (`origin=declared`)."""

    heading: str
    run: list[str] = field(default_factory=list)
    not_run: list[str] = field(default_factory=list)


@dataclass
class StructureDrift:
    """"Did this draft follow its declared structure?", read from
    `retrieval.md`'s `origin` column rather than trusted.

    `extended` is flat, not per-section: `retrieval.md` records no
    section for a call, only the query text and its origin, so an
    `--extend` addition can be reported as having happened but not
    attributed to the section that came up thin.
    """

    sections: "dict[str, SectionDrift]" = field(default_factory=dict)
    extended: list[str] = field(default_factory=list)


def declared_vs_actual(dossier: Path, structure: "Structure | None" = None) -> StructureDrift:
    """Compares `structure.md`'s declared queries against what
    `retrieval.md` actually shows ran, by exact query text.

    Reads `structure.md` itself when `structure` isn't already parsed
    (`_cmd_status` passes one in it already has; a standalone caller
    doesn't). A dossier with no `structure.md` reports every section
    empty -- there is nothing declared to have drifted from.
    """
    if structure is None:
        path = dossier / STRUCTURE_MD
        structure = parse(path.read_text(encoding="utf-8")) if path.is_file() else Structure()

    pairs = recorded_queries_with_origin(dossier)
    run = {query for query, origin in pairs if origin == "declared"}
    extended = [query for query, origin in pairs if origin == "extended"]

    sections = {
        heading: SectionDrift(
            heading=heading,
            run=[q for q in section.queries if q in run],
            not_run=[q for q in section.queries if q not in run],
        )
        for heading, section in structure.sections.items()
    }
    return StructureDrift(sections=sections, extended=extended)


def _cmd_structure(args: argparse.Namespace) -> int:
    target = _resolve_dossier(Path(args.draft))
    path = target / STRUCTURE_MD
    if not path.is_file():
        print(
            f"No {STRUCTURE_MD} in {draft_relpath(target)}. Create one with "
            f"`python -m chitragupta.draft dossier init {args.draft} --genre <genre> --structure`.",
            file=sys.stderr,
        )
        return 1

    structure = parse(path.read_text(encoding="utf-8"))
    if structure.problems:
        for problem in structure.problems:
            print(f"[error] {problem.heading!r}: {problem.problem}", file=sys.stderr)
        return 1

    if not args.check:
        for heading, section in structure.sections.items():
            print(f"## {heading}")
            if section.brief:
                print(f"  brief: {section.brief}")
            for claim in section.claims:
                print(f"  claim: {claim}")
            for query in section.queries:
                print(f"  query: {query}")

    print(
        f"{len(structure.sections)} section(s), 0 problem(s), "
        f"{draft_relpath(path)}.",
        file=sys.stderr,
    )
    return 0
