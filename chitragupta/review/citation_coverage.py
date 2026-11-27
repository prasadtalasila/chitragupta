"""Citation-coverage report: how much of what retrieval surfaced actually
made it into a draft's citations.

A citekey retrieval scored well but the draft never cites means a skipped
source or a too-broad query; one cited but not surfaced is usually another
query's, shown so the report is not misread as a gap-finder. A review aid:
informational, never a gate, no write lock. Stdout by default; `--write`
files `content/review/<topic>/<stem>.coverage.md` for diffing later.
Stdlib-only.

Usage:
    python -m chitragupta.review coverage <draft.md> --query "topic one" --query "topic two" [--k 5]
    python -m chitragupta.review coverage <draft.md> --query "topic one" --write
"""

import argparse
import hashlib
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path

from chitragupta import config, retrieval, review
from chitragupta.retrieval_added import SPELLING, describe
from chitragupta.review import _emit
from chitragupta.citation_gate import extract_citekeys_from_line
from chitragupta.review import _citation_coverage_render
from chitragupta.help_format import ClickParser


@dataclass
class CoverageResult:
    candidates: dict[str, str] = field(default_factory=dict)  # citekey -> title
    cited: set[str] = field(default_factory=set)  # every citekey actually cited in the draft
    # query -> the spelling corrections it was ranked with (#1232)
    corrections: dict[str, str] = field(default_factory=dict)

    @property
    def cited_candidates(self) -> set[str]:
        return set(self.candidates) & self.cited

    @property
    def uncited_candidates(self) -> set[str]:
        return set(self.candidates) - self.cited

    @property
    def cited_outside_candidates(self) -> set[str]:
        """Cited, but outside what this report's queries cover; not a
        problem by itself."""
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
    corrections: dict[str, str] = {}
    for query in queries:
        for result in retrieval.search(query, k=k):
            candidates[result.citekey] = result.title
        corrected = [a for a in retrieval.query_terms(query)[1] if a.source == SPELLING]
        if corrected:
            corrections[query] = describe(corrected)
    return CoverageResult(
        candidates=candidates, cited=cited_citekeys(draft_path), corrections=corrections
    )


def _command(draft_path: Path, queries: list[str], k: int, as_json: bool, write: bool) -> str:
    """The invocation recorded in the header and envelope, queries in full:
    "62% covered" means nothing without knowing of what.
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
    """A finding's name, stable across runs and position-free."""
    digest = hashlib.sha256(f"{citekey}\x00{status}".encode())
    return digest.hexdigest()[:12]


def _findings(result: CoverageResult) -> list[dict]:
    """One object per itemised citekey; unconditional, since an empty
    candidate set still leaves cited-outside findings."""
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
    """The same findings `format_report` prints, as data."""
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
    if result.corrections:
        payload["corrections"] = result.corrections
    return payload


def build_parser(parser=None) -> argparse.ArgumentParser:
    """This aid's flags, hung off the subparser `__main__` created."""
    if parser is None:
        # Not this module's docstring (#152; see chitragupta/corpus.py).
        parser = ClickParser(
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
    _emit.add_formats(parser)
    return parser


def main(argv: list[str]) -> int:
    return run(build_parser().parse_args(argv))


def run(args: argparse.Namespace) -> int:
    """Dispatch already-parsed arguments, as `verbatim scan` does: print by
    default, `--json` prints the payload, `--write` files it too, with the
    written-files summary on stderr under `--json`.
    """
    try:
        draft_path = review.require_reviewable(Path(args.draft))
    except (FileNotFoundError, config.OutsideContentDir) as exc:
        print(exc, file=sys.stderr)
        return 1

    result = compute_coverage(draft_path, args.queries, k=args.k)

    return _emit.emit(
        draft_path,
        "coverage",
        args,
        text=lambda: _citation_coverage_render.format_report(draft_path, args.queries, result),
        command=lambda: _command(draft_path, args.queries, args.k, args.json, args.write),
        payload=lambda command: coverage_payload(draft_path, args.queries, args.k, result, command),
        markdown=lambda command: _citation_coverage_render.render_markdown(
            draft_path, args.queries, args.k, result, command
        ),
    )
