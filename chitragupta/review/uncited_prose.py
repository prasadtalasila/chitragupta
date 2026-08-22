"""Uncited-prose report: which sentences of a draft carry no citation at
all.

`chitragupta/review/citation_coverage.py` looks like it answers this and
does not. It answers which *surfaced candidates* got cited -- a question
about the corpus side of the boundary. The unanswered question is on the
prose side: which claims in the draft rest on nothing. The two share the
word "uncited" and nothing else, which is why `coverage` always qualifies
its findings as *candidates* and this aid always qualifies its own as
*sentences*.

**The whole difficulty is in what this declines to report.** Measured on
the four real drafts before any of it was written, the naive reading --
every sentence carrying no citekey is a finding -- flags 78% of a survey
and 95% of a textbook chapter. A report that flags four fifths of a
draft is one nobody opens twice, and alarm fatigue is the stated risk for
this whole class. So two things narrow it, and both are recorded in
plans/c1-uncited-prose-report.md rather than invented here:

1. **Structural exclusions**, each measured -- the reference list,
   headings, captions, a table's header row, comment-only blocks, fenced
   code, and anything that flattens to nothing once its list marker is
   stripped. `chitragupta/review/_claims.py` owns them, because C2 needs
   the same answer without needing this report.
2. **The genre decides whether uncited prose is a finding at all** --
   `_units.UNCITED_PROSE`. A tutorial's body carries no citations by
   design; reporting it would bury what this report is for.

What is deliberately *not* an exclusion is the enclosing block carrying a
citation. Suppressing every sentence in a citing paragraph would take the
topic-sentence and transition problem out at a stroke, and it would be
blind to the failure this aid exists for: a paragraph with one citation
at the end and four unrelated assertions before it. Each finding carries
`block_cites` instead -- volume control for a human, and no invented
vocabulary of transition phrases.

**Surfaced, never repaired unattended.** The findings are binary, so an
agenda may consume them, but they are of *judgement* kind: the fix for an
uncited claim is evidence, not wording. An unattended reviser rewording
one would make it look supported without making it supported, which is
the failure class this project exists to prevent.

One of the six commands in the **review layer**, beside
citation_provenance.py, citation_coverage.py, verbatim_check.py,
synthesis.py and figure_layout/ -- read over a finished draft, by a person
or by a driver, never a gate, and never holding the write lock. Alone
among the six it reads nothing but the draft: no ledger, no corpus, no
sync, no `enrich` extra, and not even the figures a draft references.

Usage:
    python -m chitragupta.review uncited <draft.md>
    python -m chitragupta.review uncited <draft.md> --genre survey --write
"""

import argparse
import hashlib
import json
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path

from chitragupta import config, review
from chitragupta.review import _claims, _uncited_render, _units


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
        """The uncited sentences whose block cites nothing either -- the
        ones to read first."""
        return [s for s in self.uncited if not s.block_cites]


def resolve(draft: Path, genre: str | None) -> tuple[str, str | None, str]:
    """The standing of uncited prose in this draft, the genre, and where
    the genre came from. `_units` owns the table and the reasoning."""
    return _units.resolve_standing(draft, genre)


def build_report(draft: Path, standing: str, genre: str | None,
                 genre_source: str) -> Report:
    text = Path(draft).read_text(encoding="utf-8")
    return Report(Path(draft), genre, genre_source, standing,
                  _claims.claim_sentences(text))


def finding_id(sentence: str) -> str:
    """A finding's name, stable across runs and position-free -- the same
    convention the other four aids' `finding_id` use.

    Keyed on the sentence alone, so three things follow, all wanted:
    editing an unrelated paragraph renames nothing; citing the sentence
    makes the finding disappear, which is what "this finding is gone"
    should mean (R2); and a citation arriving elsewhere in the block
    flips `block_cites` without renaming anything, because the finding is
    still true.
    """
    return hashlib.sha256(sentence.encode()).hexdigest()[:12]


def findings(report: Report) -> list[dict]:
    """One object per uncited sentence -- or none at all, when the genre
    treats uncited prose as ordinary.

    Bare blocks first, then by line. A sentence whose paragraph cites
    nothing at all rests on nothing at all, and a reviewer should not
    have to read past the ones their own paragraph frames to reach it.
    """
    if report.standing == "ordinary":
        return []
    found = [{"id": finding_id(s.text), "line": s.line, "sentence": s.text,
              "block_cites": s.block_cites} for s in report.uncited]
    return sorted(found, key=lambda f: (f["block_cites"], f["line"]))


def _command(draft: Path, genre: str | None, as_json: bool, write: bool) -> str:
    """The invocation recorded in both the Markdown header and the JSON
    envelope. `--genre` in full when it was given: an empty finding list
    means something different when an override chose the standing."""
    parts = ["python", "-m", "chitragupta.review", "uncited", str(draft)]
    if genre:
        parts += ["--genre", genre]
    if as_json:
        parts += ["--json"]
    if write:
        parts += ["--write"]
    return shlex.join(parts)


def uncited_payload(report: Report, command: str) -> dict:
    """The same findings the report prints, as data -- an additional
    serialisation, never a second computation."""
    payload = review.envelope(report.draft, "uncited", command)
    payload.update({
        "genre": report.genre,
        "genre_source": report.genre_source,
        "standing": report.standing,
        "sentences_total": len(report.sentences),
        "uncited": len(report.uncited),
        "bare": len(report.bare),
        "findings": findings(report),
    })
    return payload


def build_parser(parser=None) -> argparse.ArgumentParser:
    """This aid's flags.

    `parser` is passed by chitragupta/review/__main__.py, which has
    already created the `uncited` subparser and needs the flags hung off
    *that* -- so they are declared once, here.
    """
    if parser is None:
        # A one-line description rather than this module's docstring, for
        # the reason chitragupta/corpus.py's DESCRIPTION gives (#152).
        parser = argparse.ArgumentParser(
            description="Report which sentences of a draft carry no citation.",
        )
    parser.add_argument("draft", help="Path to the draft to check")
    parser.add_argument("--genre", choices=sorted(_units.UNCITED_PROSE),
                        help="Read the draft under this genre instead of the one "
                             "its dossier records. The genre decides whether "
                             "uncited prose raises findings at all; this is for a "
                             "draft with no dossier, or to read one strictly on "
                             "purpose.")
    parser.add_argument("--json", action="store_true",
                        help="Print the findings as JSON instead of as text. "
                             "--write files it beside the report either way.")
    parser.add_argument("--write", action="store_true",
                        help="Also write the report to content/review/, mirroring the "
                             "draft's path. Off by default: printing is the usual use.")
    parser.add_argument("--formats", default="md,tex,pdf",
                        help="Additional formats to render beside the Markdown "
                             "report (default: md,tex,pdf). The .md is always "
                             "written -- it is the report; tex/pdf are renders "
                             "of it, and need pandoc/pdflatex on PATH.")
    return parser


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


def run(args: argparse.Namespace) -> int:
    """Dispatch already-parsed arguments, split from main() so
    chitragupta/review/__main__.py can hand over args parsed with this
    module's own build_parser().

    Exits 0 whatever it finds -- including on a draft where every
    sentence rests on nothing. This aid is advisory, and a non-zero exit
    is how a gate speaks.
    """
    try:
        draft_path = review.require_reviewable(Path(args.draft))
    except (FileNotFoundError, config.OutsideContentDir) as exc:
        print(exc, file=sys.stderr)
        return 1

    report = build_report(draft_path, *resolve(draft_path, args.genre))
    found = findings(report)

    if not (args.json or args.write):
        print(_uncited_render.format_report(report, found))
        return 0

    command = _command(draft_path, args.genre, args.json, args.write)
    payload = uncited_payload(report, command)
    print(json.dumps(payload, indent=2) if args.json
          else _uncited_render.format_report(report, found))

    if args.write:
        formats = [f.strip() for f in args.formats.split(",") if f.strip()]
        written = review.write(
            draft_path, "uncited",
            _uncited_render.render_markdown(report, command, found), formats)
        written["json"] = review.write_json(draft_path, "uncited", payload)
        review.print_written(written, stream=sys.stderr if args.json else sys.stdout)
    return 0
