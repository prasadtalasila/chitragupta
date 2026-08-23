"""Citation-coverage report: how much of what retrieval surfaced actually
made it into a draft's citations.

`chitragupta.retrieval.search()` (and its embedding-based upgrade,
`chitragupta.enrich.embed_index.search()`) return candidate sources for a query --
but nothing today reports whether a genre skill actually used them.
A citekey that scored well but never got cited is either a sign the
draft skipped a relevant source, or a sign the query was too broad; a
citekey cited but never surfaced by any of the given queries is not a
problem (it's likely explained by a different query the skill also ran)
but worth showing so the report isn't misread as a gap-finder.

One of the six commands in the **review layer**, named by the entry point
rather than by a sibling list this module has no line budget to grow --
read over a finished draft, by a person or by a driver, never a gate,
and never holding the write lock. Purely informational, unlike citation_gate.py.
chitragupta/review/__init__.py owns where a written report goes
(`content/review/<topic>/<stem>.coverage.md`, mirroring the draft's
path) and what its header looks like.

Printing to stdout is the default, because the usual use is a question
asked and answered in one sitting; `--write` is for when the answer
should still be there next month, and diffable against the next
revision's.

Stdlib-only (reuses chitragupta.retrieval and chitragupta.citation_gate.extract_citekeys_from_line,
both already stdlib-only) -- runs with bare `python`, no venv, same as
citation_gate.py/references.py.

Usage:
    python -m chitragupta.review coverage <draft.md> --query "topic one" --query "topic two" [--k 5]
    python -m chitragupta.review coverage <draft.md> --query "topic one" --write
"""

import argparse
import hashlib
import json
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path

from chitragupta import config, retrieval, review
from chitragupta.citation_gate import extract_citekeys_from_line


@dataclass
class CoverageResult:
    candidates: dict[str, str] = field(default_factory=dict)  # citekey -> title
    cited: set[str] = field(default_factory=set)  # every citekey actually cited in the draft

    @property
    def cited_candidates(self) -> set[str]:
        return set(self.candidates) & self.cited

    @property
    def uncited_candidates(self) -> set[str]:
        return set(self.candidates) - self.cited

    @property
    def cited_outside_candidates(self) -> set[str]:
        """Cited, but not surfaced by any of the given queries -- not a
        problem by itself, just outside what this report's queries cover."""
        return self.cited - set(self.candidates)

    @property
    def coverage_pct(self) -> float | None:
        if not self.candidates:
            return None
        return 100.0 * len(self.cited_candidates) / len(self.candidates)


def cited_citekeys(draft_path: Path) -> set[str]:
    keys: set[str] = set()
    for line in draft_path.read_text(encoding="utf-8").splitlines():
        keys.update(extract_citekeys_from_line(line))
    return keys


def compute_coverage(draft_path: Path, queries: list[str], k: int = 5) -> CoverageResult:
    candidates: dict[str, str] = {}
    for query in queries:
        for result in retrieval.search(query, k=k):
            candidates[result.citekey] = result.title
    return CoverageResult(candidates=candidates, cited=cited_citekeys(draft_path))


def format_report(draft_path: Path, queries: list[str], result: CoverageResult) -> str:
    lines = [f"Citation coverage for {draft_path}", f"Queries: {queries}"]

    if result.coverage_pct is None:
        lines.append("No candidates found for any query -- nothing to compare against.")
    else:
        lines.append(
            f"Coverage: {result.coverage_pct:.0f}% "
            f"({len(result.cited_candidates)}/{len(result.candidates)} retrieved candidates cited)"
        )
        if result.uncited_candidates:
            lines.append("Retrieved but not cited:")
            for key in sorted(result.uncited_candidates):
                lines.append(f"  - {key}: {result.candidates[key]}")

    if result.cited_outside_candidates:
        lines.append("Cited but not surfaced by these queries (not necessarily a problem):")
        for key in sorted(result.cited_outside_candidates):
            lines.append(f"  - {key}")

    return "\n".join(lines)


def _command(draft_path: Path, queries: list[str], k: int, as_json: bool, write: bool) -> str:
    """The invocation recorded in both the Markdown header and the JSON
    envelope. Queries in full -- "62% covered" means nothing without
    knowing 62% *of what*.
    """
    parts = ["python", "-m", "chitragupta.review", "coverage", str(draft_path)]
    for query in queries:
        parts += ["--query", query]
    parts += ["--k", str(k)]
    if as_json:
        parts += ["--json"]
    if write:
        parts += ["--write"]
    return shlex.join(parts)


def finding_id(citekey: str, status: str) -> str:
    """A finding's name, stable across runs and position-free -- the same
    convention `verbatim_check.finding_id` and
    `citation_provenance.finding_id` use.
    """
    digest = hashlib.sha256(f"{citekey}\x00{status}".encode())
    return digest.hexdigest()[:12]


def _findings(result: CoverageResult) -> list[dict]:
    """One object per citekey the printed report itemises. Unconditional,
    unlike `format_report`'s "retrieved but not cited" section: an empty
    candidate set still leaves a cited-outside finding to report."""
    findings = [
        {
            "id": finding_id(key, "uncited_candidates"),
            "citekey": key,
            "title": result.candidates[key],
            "status": "uncited_candidates",
        }
        for key in sorted(result.uncited_candidates)
    ]
    findings += [
        {
            "id": finding_id(key, "cited_outside_candidates"),
            "citekey": key,
            "title": None,
            "status": "cited_outside_candidates",
        }
        for key in sorted(result.cited_outside_candidates)
    ]
    return findings


def coverage_payload(
    draft_path: Path, queries: list[str], k: int, result: CoverageResult, command: str
) -> dict:
    """The same findings `format_report` prints, as data. An additional
    serialisation of `result`, never a second computation.
    """
    payload = review.envelope(draft_path, "coverage", command)
    payload.update(
        {
            "queries": queries,
            "k": k,
            "coverage_pct": result.coverage_pct,
            "candidates_total": len(result.candidates),
            "cited_candidates_total": len(result.cited_candidates),
            "findings": _findings(result),
        }
    )
    return payload


def render_markdown(
    draft_path: Path, queries: list[str], k: int, result: CoverageResult, command: str
) -> str:
    """The same report as `format_report`, as a Markdown document.

    Kept beside the plain-text version rather than replacing it: stdout
    is read in a terminal mid-review and wants no syntax, while a file
    kept for months is read next to the draft's other review reports and
    should look like them.
    """
    lines = review.header(draft_path, "coverage", command)
    lines += [
        "## How to read this",
        "",
        "Each query below was run through the same retrieval this project's",
        "genre skills use. A candidate it surfaced that the draft never cites",
        "is either a source worth adding or a query that was too broad --",
        "this report does not know which, and does not guess.",
        "",
        "A citekey cited but not surfaced here is **not** a gap: it is almost",
        "always explained by a different query the skill ran. It is listed so",
        "the report cannot be misread as a complete picture of the draft's",
        "sources.",
        "",
        "## Queries",
        "",
    ]
    lines += [f"- `{query}`" for query in queries]
    lines += ["", f"Top {k} results per query.", "", "## Coverage", ""]

    if result.coverage_pct is None:
        lines += ["No candidates found for any query -- nothing to compare against.", ""]
    else:
        lines += [
            f"**{result.coverage_pct:.0f}%** -- {len(result.cited_candidates)} of "
            f"{len(result.candidates)} retrieved candidates are cited.",
            "",
        ]
        if result.uncited_candidates:
            lines += ["### Retrieved but not cited", ""]
            for key in sorted(result.uncited_candidates):
                lines.append(f"- `{key}` -- {result.candidates[key]}")
            lines.append("")

    if result.cited_outside_candidates:
        lines += [
            "### Cited but not surfaced by these queries",
            "",
            "Not necessarily a problem -- see above.",
            "",
        ]
        for key in sorted(result.cited_outside_candidates):
            lines.append(f"- `{key}`")
        lines.append("")

    return "\n".join(lines)


def build_parser(parser=None) -> argparse.ArgumentParser:
    """This aid's flags.

    `parser` is passed by chitragupta/review/__main__.py, which has already
    created the `coverage` subparser and needs the flags hung off *that*
    -- so they are declared once, here, and the entry point never
    restates them.
    """
    if parser is None:
        # A one-line description rather than this module's docstring, for
        # the reason chitragupta/corpus.py's DESCRIPTION gives (#152).
        parser = argparse.ArgumentParser(
            description="Report whether a draft cites the sources retrieval surfaces for a query.",
        )
    parser.add_argument("draft", help="Path to the draft to check")
    parser.add_argument(
        "--query",
        action="append",
        required=True,
        dest="queries",
        help="A retrieval query to check coverage for (repeatable)",
    )
    parser.add_argument("--k", type=int, default=5, help="Top-k results per query (default: 5)")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the findings as JSON instead of as text. "
        "--write files it beside the report either way.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Also write the report to content/review/, mirroring the "
        "draft's path. Off by default: printing is the usual use.",
    )
    parser.add_argument(
        "--formats",
        default="md,tex,pdf",
        help="Additional formats to render beside the Markdown "
        "report (default: md,tex,pdf). The .md is always "
        "written -- it is the report; tex/pdf are renders "
        "of it, and need pandoc/pdflatex on PATH.",
    )
    return parser


def main(argv: list[str]) -> int:
    return run(build_parser().parse_args(argv))


def run(args: argparse.Namespace) -> int:
    """Dispatch already-parsed arguments, split from main() so
    chitragupta/review/__main__.py can hand over args parsed with this
    module's own build_parser() rather than re-slicing argv.

    Mirrors `verbatim scan`'s own `--json`/`--write` contract: printing
    stays the default and cheap path; `--json` prints the payload instead
    of text; `--write` files it beside the Markdown either way, with the
    written-files summary on stderr under `--json`.
    """
    try:
        draft_path = review.require_reviewable(Path(args.draft))
    except (FileNotFoundError, config.OutsideContentDir) as exc:
        print(exc, file=sys.stderr)
        return 1

    result = compute_coverage(draft_path, args.queries, k=args.k)

    if not (args.json or args.write):
        print(format_report(draft_path, args.queries, result))
        return 0

    command = _command(draft_path, args.queries, args.k, args.json, args.write)
    payload = coverage_payload(draft_path, args.queries, args.k, result, command)
    print(
        json.dumps(payload, indent=2)
        if args.json
        else format_report(draft_path, args.queries, result)
    )

    if args.write:
        formats = [f.strip() for f in args.formats.split(",") if f.strip()]
        body = render_markdown(draft_path, args.queries, args.k, result, command)
        written = review.write(draft_path, "coverage", body, formats)
        written["json"] = review.write_json(draft_path, "coverage", payload)
        review.print_written(written, stream=sys.stderr if args.json else sys.stdout)
    return 0
