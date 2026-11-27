"""Uncited-prose report: which sentences of a draft carry no citation at
all.

Not `citation_coverage.py`, which asks which surfaced *candidates* got
cited; this asks which *sentences* rest on nothing. Naively that flags
78-95% of a draft, so two things narrow it
(plans/c1-uncited-prose-report.md): structural exclusions owned by
`_claims.py`, and the genre's standing (`_units.UNCITED_PROSE`). A citing
enclosing block is deliberately not an exclusion, or a paragraph with one
citation and four unrelated assertions would pass; `block_cites` is
reported instead.

Surfaced, never repaired unattended: the fix for an uncited claim is
evidence, and rewording would make it look supported without being so.
A review aid, never a gate, no write lock; reads only the draft.

Usage:
    python -m chitragupta.review uncited <draft.md>
    python -m chitragupta.review uncited <draft.md> --genre survey --write
"""

import argparse
import hashlib
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path

from chitragupta import config, review
from chitragupta.review import _emit
from chitragupta.review import _claims, _uncited_render, _units
from chitragupta.help_format import ClickParser


@dataclass
class Report:
    draft: Path
    genre: str | None
    genre_source: str
    standing: str
    sentences: list[_claims.Sentence]

    @property
    def uncited(self) -> list[_claims.Sentence]:
        return [s for s in self.sentences if not s.cites]

    @property
    def bare(self) -> list[_claims.Sentence]:
        """Uncited sentences whose block cites nothing either: read first."""
        return [s for s in self.uncited if not s.block_cites]


def resolve(draft: Path, genre: str | None) -> tuple[str, str | None, str]:
    """The standing of uncited prose, the genre, and where it came from."""
    return _units.resolve_standing(draft, genre)


def build_report(draft: Path, standing: str, genre: str | None, genre_source: str) -> Report:
    text = Path(draft).read_text(encoding="utf-8")
    return Report(Path(draft), genre, genre_source, standing, _claims.claim_sentences(text))


def finding_id(sentence: str) -> str:
    """A finding's name, stable across runs and position-free.

    Keyed on the sentence alone: unrelated edits rename nothing, citing it
    removes the finding (R2), and a citation elsewhere in the block only
    flips `block_cites`.
    """
    return hashlib.sha256(sentence.encode()).hexdigest()[:12]


def findings(report: Report) -> list[dict]:
    """One object per uncited sentence -- none when the genre treats
    uncited prose as ordinary -- bare blocks first, then by line.
    """
    if report.standing == "ordinary":
        return []
    found = [
        {"id": finding_id(s.text), "line": s.line, "sentence": s.text, "block_cites": s.block_cites}
        for s in report.uncited
    ]
    return sorted(found, key=lambda f: (f["block_cites"], f["line"]))


def _command(draft: Path, genre: str | None, as_json: bool, write: bool) -> str:
    """The invocation recorded in the Markdown header and JSON envelope;
    `--genre` included, since an override chose the standing."""
    parts = ["python", "-m", "chitragupta.review", "uncited", str(draft)]
    if genre:
        parts += ["--genre", genre]
    if as_json:
        parts += ["--json"]
    if write:
        parts += ["--write"]
    return shlex.join(parts)


def uncited_payload(report: Report, command: str) -> dict:
    """The findings as data: a serialisation, never a second computation."""
    payload = review.envelope(report.draft, "uncited", command)
    payload.update(
        {
            "genre": report.genre,
            "genre_source": report.genre_source,
            "standing": report.standing,
            "sentences_total": len(report.sentences),
            "uncited": len(report.uncited),
            "bare": len(report.bare),
            "findings": findings(report),
        }
    )
    return payload


def build_parser(parser=None) -> argparse.ArgumentParser:
    """This aid's flags, declared once for chitragupta/review/__main__.py."""
    if parser is None:
        # Not this module's docstring (#152; see chitragupta/corpus.py).
        parser = ClickParser(
            description="Report which sentences of a draft carry no citation.",
        )
    parser.add_argument("draft", help="Path to the draft to check")
    parser.add_argument(
        "--genre",
        choices=sorted(_units.UNCITED_PROSE),
        help="Read the draft under this genre instead of the one "
        "its dossier records. The genre decides whether "
        "uncited prose raises findings at all; this is for a "
        "draft with no dossier, or to read one strictly on "
        "purpose.",
    )
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


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


def run(args: argparse.Namespace) -> int:
    """Dispatch already-parsed arguments (for __main__). Exits 0 whatever
    it finds: a non-zero exit is how a gate speaks.
    """
    try:
        draft_path = review.require_reviewable(Path(args.draft))
    except (FileNotFoundError, config.OutsideContentDir) as exc:
        print(exc, file=sys.stderr)
        return 1

    report = build_report(draft_path, *resolve(draft_path, args.genre))
    found = findings(report)

    return _emit.emit(
        draft_path,
        "uncited",
        args,
        text=lambda: _uncited_render.format_report(report, found),
        command=lambda: _command(draft_path, args.genre, args.json, args.write),
        payload=lambda command: uncited_payload(report, command),
        markdown=lambda command: _uncited_render.render_markdown(report, command, found),
    )
