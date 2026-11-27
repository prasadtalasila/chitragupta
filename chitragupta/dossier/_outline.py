"""`outline.md`: the human's own outline for a single-draft dossier
(#455) -- a heading, a `brief:` and/or one or more `claim:` blocks, and
optional declared `queries:` a genre skill runs verbatim instead of
inventing sub-themes.

Reads and validates only: retrieval and writing stay the skill's job
(plans/outline-driven-drafting-and-manual-edits.md). A sibling to
`scope.md`, not a second `spec.md`; it never applies to a book unit.
"""

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from chitragupta.dossier import OUTLINE_MD, _resolve_dossier, draft_relpath
from chitragupta.dossier._retrieval import recorded_queries_with_evidence

# Level 2 or deeper, per `OutlineSection`'s contract: matching `#` gave a
# leading `# Title` a bogus empty section (#506/m-64); it now falls to the
# preamble branch.
_HEADING = re.compile(r"^(#{2,6})\s+(.*)$")
_BRIEF = re.compile(r"^brief:\s*(.*)$", re.IGNORECASE)
_CLAIM = re.compile(r"^claim:\s*(.*)$", re.IGNORECASE)
_QUERIES_LABEL = re.compile(r"^queries:\s*$", re.IGNORECASE)
_QUERY_ITEM = re.compile(r"^-\s+(.*)$")


@dataclass
class OutlineSection:
    """One `##` heading's declared intent: steering (`brief`), content to
    ground (`claim`, zero or more), and the queries a skill runs verbatim
    for this section. `brief` and `claim` combine."""

    heading: str
    brief: str = ""
    claims: list[str] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)


@dataclass
class OutlineProblem:
    heading: str
    problem: str


@dataclass
class Outline:
    sections: "dict[str, OutlineSection]" = field(default_factory=dict)
    problems: list[OutlineProblem] = field(default_factory=list)


class _Parser:
    """One pass over `outline.md`'s lines as a small state machine.

    `mode` is the label accumulating prose (`"brief"`, `"claim"`,
    `"queries"` or `None`); `buffer` holds its lines until flushed.
    """

    def __init__(self) -> None:
        self.result = Outline()
        self.section: "OutlineSection | None" = None
        self.mode: "str | None" = None
        self.buffer: list[str] = []
        self.in_comment = False

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
        self.section = OutlineSection(heading=heading)
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
        # `line` is already rstripped, so the group is never empty.
        item = _QUERY_ITEM.match(line)
        if item:
            self.section.queries.append(item.group(1))
        elif line.strip():
            self.problem(f"queries: expects a `- ` bullet, not {line!r}")

    def add_line(self, raw_line: str, line: str) -> None:
        if self.mode in ("brief", "claim"):
            self.buffer.append(raw_line)
        elif line.strip():
            self.problem(f"unrecognised line: {line!r}")

    def problem(self, text: str) -> None:
        self.problem_for(self.section.heading, text)

    def problem_for(self, heading: str, text: str) -> None:
        self.result.problems.append(OutlineProblem(heading, text))

    def dispatch(self, raw_line: str) -> None:
        line = raw_line.rstrip()
        if self.consume_comment(line):
            return
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

    def consume_comment(self, line: str) -> bool:
        """True if `line` was swallowed as part of a (possibly multi-line)
        HTML comment, so structure-shaped lines inside one never reach
        dispatch."""
        if self.in_comment:
            if "-->" in line:
                self.in_comment = False
            return True
        stripped = line.lstrip()
        if stripped.startswith("<!--"):
            if "-->" not in stripped[4:]:
                self.in_comment = True
            return True
        return False

    def finish(self) -> Outline:
        self.flush()
        for heading, section in self.result.sections.items():
            if not section.brief and not section.claims:
                self.problem_for(heading, "neither a brief: nor a claim: block")
        return self.result


def parse(text: str) -> Outline:
    """`outline.md`'s text into one `OutlineSection` per `##`-or-deeper
    heading, plus whatever's wrong with it.

    Advisory about *shape*: a heading with neither `brief:` nor `claim:`
    is reported, a blank one is not (that is a human mid-edit).
    """
    parser = _Parser()
    for raw_line in text.splitlines():
        parser.dispatch(raw_line)
    return parser.finish()


@dataclass
class SectionDrift:
    """One `outline.md` section's declared queries, split by whether
    `retrieval.md` shows them actually run verbatim (`origin=declared`).

    `run_empty` is a **subset of `run`** (#480): issued, but every row
    returned nothing. `run` still means issued (#470).
    """

    heading: str
    run: list[str] = field(default_factory=list)
    not_run: list[str] = field(default_factory=list)
    run_empty: list[str] = field(default_factory=list)


@dataclass
class OutlineDrift:
    """ "Did this draft follow its declared outline?", read from
    `retrieval.md`'s `origin` column rather than trusted.

    `extended` is flat: `retrieval.md` records no section for a call.
    `regrounded` (E4's `--y-prev` rounds) is also counted in `run`, since
    the declared query did execute, and listed so `status` can say so.
    """

    sections: "dict[str, SectionDrift]" = field(default_factory=dict)
    extended: list[str] = field(default_factory=list)
    regrounded: list[str] = field(default_factory=list)


def _normalised(query: str) -> str:
    """Whitespace-collapsed as `log_retrieval` does, or differently spaced
    queries read as never run."""
    return " ".join(query.split())


def declared_vs_actual(dossier: Path, outline: "Outline | None" = None) -> OutlineDrift:
    """Compares `outline.md`'s declared queries against what
    `retrieval.md` actually shows ran, by whitespace-normalised text.

    With no `outline.md`, every section is empty: nothing to drift from.
    """
    if outline is None:
        path = dossier / OUTLINE_MD
        outline = parse(path.read_text(encoding="utf-8")) if path.is_file() else Outline()

    triples = recorded_queries_with_evidence(dossier)
    declared = [(q, e) for q, origin, e in triples if origin in ("declared", "reground")]
    run = {_normalised(q) for q, _ in declared}
    grounded = {_normalised(q) for q, evidence in declared if evidence}
    extended = [query for query, origin, _ in triples if origin == "extended"]
    regrounded = [query for query, origin, _ in triples if origin == "reground"]

    sections = {
        heading: SectionDrift(
            heading=heading,
            run=[q for q in section.queries if _normalised(q) in run],
            not_run=[q for q in section.queries if _normalised(q) not in run],
            run_empty=[q for q in section.queries if _normalised(q) in run - grounded],
        )
        for heading, section in outline.sections.items()
    }
    return OutlineDrift(sections=sections, extended=extended, regrounded=regrounded)


def _cmd_outline(args: argparse.Namespace) -> int:
    target = _resolve_dossier(Path(args.draft))
    path = target / OUTLINE_MD
    if not path.is_file():
        print(
            f"No {OUTLINE_MD} in {draft_relpath(target)}. Create one with "
            f"`python -m chitragupta.draft dossier init {args.draft} --genre <genre> --outline`.",
            file=sys.stderr,
        )
        return 1

    outline = parse(path.read_text(encoding="utf-8"))
    if outline.problems:
        for problem in outline.problems:
            print(f"[error] {problem.heading!r}: {problem.problem}", file=sys.stderr)
        return 1

    if not args.check:
        for heading, section in outline.sections.items():
            print(f"## {heading}")
            if section.brief:
                print(f"  brief: {section.brief}")
            for claim in section.claims:
                print(f"  claim: {claim}")
            for query in section.queries:
                print(f"  query: {query}")

    print(
        f"{len(outline.sections)} section(s), 0 problem(s), {draft_relpath(path)}.",
        file=sys.stderr,
    )
    return 0
