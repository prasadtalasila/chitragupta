"""Multi-source synthesis report: how many sources each unit of a draft
rests on, at the unit its genre binds at.

Prose required to fuse two or more sources cannot be a transcription of
any one of them -- you cannot transcribe two sources simultaneously. That
is the guarantee `docs/WRITING-STANDARDS.md` §11 asks a drafter for, and
this is what makes it observable rather than merely written down.

The *unit* differs by genre and the guarantee does not:
`chitragupta/review/_units.py` owns that mapping and the reasoning.
This module reports what it finds there, and its header names the genre,
the unit and where the unit came from -- so a tutorial's report, measured
at the whole document, cannot be read as a paragraph-scale failure.

**A thin corpus legitimately produces single-source units.** The report
counts them; it does not judge them, and no draft is blocked by what it
says. A proportion is exactly the shape docs/AUTO-IMPROVEMENT.md's R3
exists to keep out of an unattended loop, so there is no threshold here,
no target, and no per-genre bar -- only counts, and a human to read them.

One of the six commands in the **review layer**, with
chitragupta/review/citation_provenance.py,
chitragupta/review/citation_coverage.py,
chitragupta/review/verbatim_check.py,
chitragupta/review/figure_layout/ and
chitragupta/review/uncited_prose.py -- read over a finished draft, by a
person or by a driver, never a gate, and never holding the write lock.

This aid owns its own units through `_units.py`. `verbatim_check` splits
paragraphs its own way for its own purposes, and the two are **not**
expected to agree on a paragraph count; neither is wrong when they
differ.

Usage:
    python -m chitragupta.review synthesis <draft.md>
    python -m chitragupta.review synthesis <draft.md> --unit section --write
"""

import argparse
import hashlib
import json
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path

from chitragupta import config, review
from chitragupta.review import _synthesis_render, _units

# The run length at which a section's block structure is worth itemising.
# Not a quality threshold and not tunable: it is the number
# `textbook-chapter-writer` step 4 already instructs against -- "before
# reusing the same citekey a third time within one section, do one more
# search() pass". Every section's run is reported whatever its length;
# this only decides which ones get their own line.
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
        """Of the units that cite at all -- None when none do.

        Uncited units are excluded deliberately: most of a textbook
        chapter and effectively all of a tutorial are original prose, and
        counting that as a failure to fuse sources would make the number
        meaningless in the two genres that need it read most carefully.
        """
        if not self.citing:
            return None
        return 100.0 * self.single_source / len(self.citing)


def resolve(draft: Path, override: str | None) -> tuple[str, str, str | None]:
    """The unit, where it came from, and the genre it was read from.

    The genre travels even when an override won, because the report says
    both: "measured at the section, because you asked, on a draft
    recorded as a tutorial" is a different thing to have done than
    measuring a textbook chapter at its own unit.
    """
    kind, source = _units.resolve_unit(draft, override)
    return kind, source, _units.genre_of(draft)


def build_report(draft: Path, kind: str, source: str, genre: str | None) -> Report:
    text = Path(draft).read_text(encoding="utf-8")
    return Report(draft, kind, source, genre, _units.units(text, kind))


def finding_id(kind: str, text: str) -> str:
    """A finding's name, stable across runs and position-free -- the same
    convention the other three aids' `finding_id` use.

    Keyed on the unit's marker-stripped text, so declaring a unit does
    not rename the finding that describes it, and on the finding's kind,
    so a section reported for both its spread and its run keeps two
    distinguishable names.
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

    Two kinds, and a unit raises at most one. `single_source` is a unit
    resting on one citekey. `single_key_run` is a unit that spans several
    sources but arrives in blocks -- three paragraphs of one paper, then
    three of the next -- which satisfies spread and fuses nothing.

    A single-source unit is never *also* reported for its run: a unit
    resting on one source has a run as long as it has paragraphs, and
    saying so twice tells a reader nothing the first finding did not.

    An uncited unit is **never** a finding. Original prose is the genre
    working correctly in three of the five genres, and reporting it would
    bury what this report is actually for.

    Undeclared first, then by line: a drafter who stated their reason has
    already done what the rule asks, and the report should not make them
    read past their own declarations to find what they have not looked at.
    """
    found = [_finding(unit, "single_source") for unit in report.citing if len(unit.citekeys) == 1]
    found += [
        _finding(unit, "single_key_run")
        for unit in report.citing
        if len(unit.citekeys) > 1 and unit.longest_run >= RUN_REPORTED_AT
    ]
    return sorted(found, key=lambda f: (f["declared"] is not None, f["line"]))


def _command(draft: Path, unit: str | None, as_json: bool, write: bool) -> str:
    """The invocation recorded in both the Markdown header and the JSON
    envelope. `--unit` in full when it was given: a count of single-source
    paragraphs means something different on a draft whose genre asked for
    sections."""
    parts = ["python", "-m", "chitragupta.review", "synthesis", str(draft)]
    if unit:
        parts += ["--unit", unit]
    if as_json:
        parts += ["--json"]
    if write:
        parts += ["--write"]
    return shlex.join(parts)


def synthesis_payload(report: Report, command: str) -> dict:
    """The same findings the report prints, as data -- an additional
    serialisation, never a second computation."""
    payload = review.envelope(report.draft, "synthesis", command)
    payload.update(
        {
            "genre": report.genre,
            "unit": report.kind,
            "unit_source": report.source,
            "units_total": len(report.units),
            "uncited": report.uncited,
            "single_source": report.single_source,
            "multi_source": report.multi_source,
            "declared": report.declared,
            "undeclared": report.undeclared,
            "single_source_pct": report.single_source_pct,
            "findings": findings(report),
        }
    )
    return payload


def build_parser(parser=None) -> argparse.ArgumentParser:
    """This aid's flags.

    `parser` is passed by chitragupta/review/__main__.py, which has
    already created the `synthesis` subparser and needs the flags hung
    off *that* -- so they are declared once, here.
    """
    if parser is None:
        # A one-line description rather than this module's docstring, for
        # the reason chitragupta/corpus.py's DESCRIPTION gives (#152).
        parser = argparse.ArgumentParser(
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
    module's own build_parser().

    Exits 0 whatever it finds -- including on a draft where every unit
    rests on one source. This aid is advisory, and a non-zero exit is how
    a gate speaks.
    """
    try:
        draft_path = review.require_reviewable(Path(args.draft))
    except (FileNotFoundError, config.OutsideContentDir) as exc:
        print(exc, file=sys.stderr)
        return 1

    report = build_report(draft_path, *resolve(draft_path, args.unit))

    found = findings(report)

    if not (args.json or args.write):
        print(_synthesis_render.format_report(report, found))
        return 0

    command = _command(draft_path, args.unit, args.json, args.write)
    payload = synthesis_payload(report, command)
    print(
        json.dumps(payload, indent=2)
        if args.json
        else _synthesis_render.format_report(report, found)
    )

    if args.write:
        formats = [f.strip() for f in args.formats.split(",") if f.strip()]
        written = review.write(
            draft_path,
            "synthesis",
            _synthesis_render.render_markdown(report, command, found),
            formats,
        )
        written["json"] = review.write_json(draft_path, "synthesis", payload)
        review.print_written(written, stream=sys.stderr if args.json else sys.stdout)
    return 0
