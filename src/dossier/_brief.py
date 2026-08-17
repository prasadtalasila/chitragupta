"""`dossier brief`: the kept evidence for one section.

Split out of src/dossier.py (#219). `status` and `drift` read a
dossier on behalf of a human. This reads it on behalf of a *subagent*,
and the difference is what the shape is for: a skill that fans out
(`deep-research` Phase 5 dispatches one writer per section) has to give
each subagent the evidence its section stands on. Pasting that evidence
into the dispatch prompt spends it in the output pool, which is the
expensive direction (docs/TOKENS.md), and spends it once per subagent.
Handing over a command instead moves the same text into the subagent's
own one-shot context, where it is billed once and discarded with that
context. This does not, and cannot, shrink what the *orchestrator* is
already carrying -- a context is append-only between compactions -- but
it removes the re-emission, and, because the dossier outlives the run,
the need to re-derive any of it after a compaction or in a later
session.
"""

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

from src.dossier._citekeys import citekeys_by_section, evidence_blocks
from src.dossier import EVIDENCE_MD, SECTIONS_MD, _resolve_dossier, dossier_name, draft_relpath

@dataclass
class Brief:
    """The evidence a dispatched subagent was asked for, and what of it
    the dossier could not supply."""

    dossier: Path
    section: str | None = None  # the sections.md row this matched, if asked by section
    blocks: list[tuple[str, str]] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    known_sections: list[str] = field(default_factory=list)


def _normalised(title: str) -> str:
    return " ".join(title.split()).casefold()


def _match_section(wanted: str, known: dict[str, list[str]]) -> str | None:
    """The `sections.md` row `wanted` names, or None if it names no single
    one.

    Exact first (modulo case and runs of whitespace), then a unique
    substring either way, so a writer dispatched for "Failure modes"
    matches the row a skill numbered "2. Failure modes" without the
    caller having to know how it was numbered.

    An ambiguous name matches *nothing* rather than the first candidate.
    Guessing here hands a section writer another section's evidence,
    which is the one failure mode this whole path has to avoid: it comes
    back as a fluent, correctly-cited section about the wrong thing.
    """
    target = _normalised(wanted)
    for title in known:
        if _normalised(title) == target:
            return title
    partial = [
        title for title in known
        if target in _normalised(title) or _normalised(title) in target
    ]
    return partial[0] if len(partial) == 1 else None


def brief(
    dossier: Path,
    citekeys: "list[str] | tuple[str, ...]" = (),
    section: str | None = None,
) -> Brief:
    """The kept-evidence blocks for `citekeys`, for `section`, or for both.

    Reports rather than raises, like everything else here -- but the
    report distinguishes three things a caller has to tell apart: a
    citekey with a block (`blocks`), one asked for with no block
    (`missing`), and a section name that matches no row (`section` back
    as None, with `known_sections` filled in).

    `missing` is the load-bearing one. A citekey that was retrieved,
    kept, and then never transcribed exists nowhere once the run that
    found it ends, and until this the loss was silent: the draft looked
    finished and the judgment behind it was gone. A dispatch that reads
    from here turns that into a named citekey at the moment it matters.
    """
    known = citekeys_by_section(dossier)
    matched = _match_section(section, known) if section else None
    report = Brief(dossier=dossier, section=matched, known_sections=list(known))
    if section and matched is None:
        return report

    asked: list[str] = []
    for citekey in list(known.get(matched, [])) + list(citekeys):
        if citekey not in asked:
            asked.append(citekey)

    blocks = evidence_blocks(dossier)
    for citekey in asked:
        if citekey in blocks:
            report.blocks.append((citekey, blocks[citekey]))
        else:
            report.missing.append(citekey)
    return report


def _cmd_brief(args: argparse.Namespace) -> int:
    """Exit codes: 0 when it printed at least one block, 1 when it could
    not print any.

    A caller of this is a dispatch prompt, not a person, so "nothing
    here" has to be a status code rather than a paragraph -- a subagent
    that reads an empty brief and writes the section anyway produces
    exactly the ungrounded prose this project exists to prevent. Every
    diagnostic goes to stderr so that stdout is only ever the evidence.
    """
    if not args.citekeys and not args.section:
        print("Name at least one citekey, or a section with --section. "
              "`brief` selects rows; it deliberately won't dump the whole "
              "of evidence.md into a reader's context.", file=sys.stderr)
        return 1

    target = _resolve_dossier(Path(args.draft))
    if not target.is_dir():
        print(f"No dossier at {draft_relpath(target)}. Create one with "
              f"`python -m src.draft dossier init {args.draft} --genre <genre>`.",
              file=sys.stderr)
        return 1

    report = brief(target, args.citekeys, args.section)
    if args.section and report.section is None:
        _explain_unknown_section(args.section, target, report)
        return 1

    label = f"{dossier_name(target)}"
    if report.section:
        label += f" -- section {report.section!r}"
    asked = len(report.blocks) + len(report.missing)
    print(f"# Kept evidence: {label}", file=sys.stderr)
    print(f"#   {len(report.blocks)} of {asked} citekey(s) from "
          f"{draft_relpath(target / EVIDENCE_MD)}", file=sys.stderr)

    if not args.check:
        for _, block in report.blocks:
            print(f"\n{block}", end="")

    _warn_brief_gaps(report, asked)
    return 0 if report.blocks else 1


def _explain_unknown_section(section: str, target: Path, report: Brief) -> None:
    """stderr for a --section that matched nothing: what is there instead."""
    print(f"No section matching {section!r} in "
          f"{draft_relpath(target / SECTIONS_MD)}.", file=sys.stderr)
    if report.known_sections:
        print("  Sections it does hold:", file=sys.stderr)
        for title in report.known_sections:
            print(f"    {title}", file=sys.stderr)
    else:
        print("  sections.md holds no rows yet -- the run that dispatches by "
              "section writes the section -> citekey plan there first.",
              file=sys.stderr)


def _warn_brief_gaps(report: Brief, asked: int) -> None:
    """The two ungrounded-evidence warnings a brief can end with."""
    if report.missing:
        print(f"\n[warn] {len(report.missing)} citekey(s) have no block in "
              "evidence.md, so nothing here grounds them:", file=sys.stderr)
        for citekey in report.missing:
            print(f"    {citekey}", file=sys.stderr)
        print("  Either the run that found them never transcribed them -- in "
              "which case they are gone and have to be re-retrieved -- or they "
              "are misspelled here.", file=sys.stderr)
    elif not asked:
        # A row that exists and assigns nothing. Distinct from a name
        # that matched no row, and it wants the opposite fix: the plan
        # has a gap in it, rather than the caller having mistyped.
        print("\n[warn] That section is planned but has no citekeys assigned "
              "to it, so there is nothing to write from. Assign its evidence "
              "in sections.md, or don't dispatch a writer for it.",
              file=sys.stderr)
