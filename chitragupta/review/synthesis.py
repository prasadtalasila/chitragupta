"""Multi-source synthesis report: how many sources each unit of a draft
rests on, at the unit its genre binds at.

Prose fusing two or more sources cannot transcribe any one of them: the
guarantee docs/WRITING-STANDARDS.md §11 asks for, made observable. The
unit differs by genre (`_units.py`); the header names it so a tutorial's
whole-document report is not read at paragraph scale. A thin corpus
legitimately yields single-source units, so only counts are reported, no
threshold or target (R3). A review aid, never a gate, no write lock. Its
paragraph count need not agree with `verbatim_check`'s.

Usage:
    python -m chitragupta.review synthesis <draft.md>
    python -m chitragupta.review synthesis <draft.md> --unit section --write
"""

import argparse
import hashlib
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path

from chitragupta import citation_gate, config, review
from chitragupta.review import _emit
from chitragupta.review import _synthesis_render, _units
from chitragupta.help_format import ClickParser

# Which section runs get their own line (every run is reported); not
# tunable: `textbook-chapter-writer` step 4's "third time within one
# section" rule.
RUN_REPORTED_AT = 3


@dataclass
class Report:
    draft: Path
    kind: str
    source: str
    genre: str | None
    units: list[_units.Unit]

    @property
    def citing(self) -> list[_units.Unit]:
        return [unit for unit in self.units if unit.citekeys]

    @property
    def uncited(self) -> int:
        return len(self.units) - len(self.citing)

    @property
    def single_source(self) -> int:
        return len([unit for unit in self.citing if len(unit.citekeys) == 1])

    @property
    def multi_source(self) -> int:
        return len([unit for unit in self.citing if len(unit.citekeys) > 1])

    @property
    def declared(self) -> int:
        return len([unit for unit in self.citing if len(unit.citekeys) == 1 and unit.declared])

    @property
    def undeclared(self) -> int:
        return self.single_source - self.declared

    @property
    def single_source_pct(self) -> float | None:
        """Of the units that cite at all -- None when none do. Uncited
        units are excluded: textbooks and tutorials are mostly original
        prose, which would make the number meaningless there."""
        if not self.citing:
            return None
        return 100.0 * self.single_source / len(self.citing)


def resolve(draft: Path, override: str | None) -> tuple[str, str, str | None]:
    """The unit, where it came from, and the genre it was read from; the
    genre travels even when an override won, since the report says both.
    """
    kind, source = _units.resolve_unit(draft, override)
    return kind, source, _units.genre_of(draft)


def build_report(draft: Path, kind: str, source: str, genre: str | None) -> Report:
    text = Path(draft).read_text(encoding="utf-8")
    latex = citation_gate.is_latex(draft)
    return Report(draft, kind, source, genre, _units.units(text, kind, latex=latex))


def finding_id(kind: str, text: str) -> str:
    """A finding's name, stable across runs and position-free.

    Keyed on the marker-stripped text, so declaring a unit does not rename
    it, and on the kind, so one section's two findings stay distinct.
    """
    digest = hashlib.sha256(f"{kind}\x00{text}".encode())
    return digest.hexdigest()[:12]


def _finding(unit: _units.Unit, kind: str) -> dict:
    return {
        "id": finding_id(kind, unit.text),
        "kind": kind,
        "line": unit.line,
        "unit": unit.kind,
        "citekeys": list(unit.citekeys),
        "declared": unit.declared,
        "longest_run": unit.longest_run,
    }


def findings(report: Report) -> list[dict]:
    """One object per unit where the guarantee did not bind.

    `single_source` rests on one citekey; `single_key_run` spans several
    but in blocks, which fuses nothing. A single-source unit is never also
    reported for its run, and an uncited unit is never a finding
    (`_units.UNCITED_PROSE`). Undeclared first, then by line.
    """
    found = [_finding(unit, "single_source") for unit in report.citing if len(unit.citekeys) == 1]
    found += [
        _finding(unit, "single_key_run")
        for unit in report.citing
        if len(unit.citekeys) > 1 and unit.longest_run >= RUN_REPORTED_AT
    ]
    return sorted(found, key=lambda f: (f["declared"] is not None, f["line"]))


def _command(draft: Path, unit: str | None, as_json: bool, write: bool) -> str:
    """The invocation recorded in the Markdown header and JSON envelope;
    `--unit` included, since it changes what the counts mean."""
    parts = ["python", "-m", "chitragupta.review", "synthesis", str(draft)]
    if unit:
        parts += ["--unit", unit]
    if as_json:
        parts += ["--json"]
    if write:
        parts += ["--write"]
    return shlex.join(parts)


def build_parser(parser=None) -> argparse.ArgumentParser:
    """This aid's flags, declared once for chitragupta/review/__main__.py."""
    if parser is None:
        # Not this module's docstring (#152; see chitragupta/corpus.py).
        parser = ClickParser(
            description="Report how many sources each unit of a draft rests on.",
        )
    parser.add_argument("draft", help="Path to the draft to check")
    parser.add_argument(
        "--unit",
        choices=_units.KINDS,
        help="Measure at this unit instead of the one this draft's "
        "genre binds at. The genre is read from the dossier's "
        "scope.md; this is for a draft that has none.",
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


def main(argv: list[str]) -> int:
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

    report = build_report(draft_path, *resolve(draft_path, args.unit))

    found = findings(report)

    return _emit.emit(
        draft_path,
        "synthesis",
        args,
        text=lambda: _synthesis_render.format_report(report, found),
        command=lambda: _command(draft_path, args.unit, args.json, args.write),
        payload=lambda command: _synthesis_render.synthesis_payload(report, command, found),
        markdown=lambda command: _synthesis_render.render_markdown(report, command, found),
    )
