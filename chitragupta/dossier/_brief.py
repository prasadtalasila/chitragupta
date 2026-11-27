"""`dossier brief`: the kept evidence for one section.

Reads the dossier on behalf of a *subagent*. Handing a fan-out writer a
command instead of pasting evidence into its prompt avoids re-emitting
it in the expensive output pool once per subagent (docs/TOKENS.md), and
the dossier survives compaction.
"""

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

from chitragupta.dossier._citekeys import citekeys_by_section, evidence_blocks
from chitragupta.dossier import (
    EVIDENCE_MD,
    SECTIONS_MD,
    _resolve_dossier,
    dossier_name,
    draft_relpath,
)


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

    Exact first (case and whitespace aside), then a unique substring, so
    "Failure modes" matches "2. Failure modes". An ambiguous name matches
    *nothing*: a guess hands a writer another section's evidence, which
    returns as a fluent, correctly cited section about the wrong thing.
    """
    target = _normalised(wanted)
    for title in known:
        if _normalised(title) == target:
            return title
    partial = [
        title for title in known if target in _normalised(title) or _normalised(title) in target
    ]
    return partial[0] if len(partial) == 1 else None


def brief(
    dossier: Path,
    citekeys: "list[str] | tuple[str, ...]" = (),
    section: str | None = None,
) -> Brief:
    """The kept-evidence blocks for `citekeys`, for `section`, or for both.

    Reports rather than raises, distinguishing `blocks`, `missing`, and an
    unmatched section (None, with `known_sections`). `missing` is the
    load-bearing one: a kept but never transcribed citekey is otherwise
    lost silently once the run ends.
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

    The caller is a dispatch prompt, so "nothing here" must be a status
    code, or a subagent writes ungrounded prose. Diagnostics go to stderr
    so stdout is only evidence.
    """
    if not args.citekeys and not args.section:
        print(
            "Name at least one citekey, or a section with --section. "
            "`brief` selects rows; it deliberately won't dump the whole "
            "of evidence.md into a reader's context.",
            file=sys.stderr,
        )
        return 1

    target = _resolve_dossier(Path(args.draft))
    if not target.is_dir():
        print(
            f"No dossier at {draft_relpath(target)}. Create one with "
            f"`python -m chitragupta.draft dossier init {args.draft} --genre <genre>`.",
            file=sys.stderr,
        )
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
    print(
        f"#   {len(report.blocks)} of {asked} citekey(s) from "
        f"{draft_relpath(target / EVIDENCE_MD)}",
        file=sys.stderr,
    )

    if not args.check:
        for _, block in report.blocks:
            print(f"\n{block}", end="")

    _warn_brief_gaps(report, asked)
    return 0 if report.blocks else 1


def _explain_unknown_section(section: str, target: Path, report: Brief) -> None:
    print(
        f"No section matching {section!r} in {draft_relpath(target / SECTIONS_MD)}.",
        file=sys.stderr,
    )
    if report.known_sections:
        print("  Sections it does hold:", file=sys.stderr)
        for title in report.known_sections:
            print(f"    {title}", file=sys.stderr)
    else:
        print(
            "  sections.md holds no rows yet -- the run that dispatches by "
            "section writes the section -> citekey plan there first.",
            file=sys.stderr,
        )


def _warn_brief_gaps(report: Brief, asked: int) -> None:
    if report.missing:
        print(
            f"\n[warn] {len(report.missing)} citekey(s) have no block in "
            "evidence.md, so nothing here grounds them:",
            file=sys.stderr,
        )
        for citekey in report.missing:
            print(f"    {citekey}", file=sys.stderr)
        print(
            "  Either the run that found them never transcribed them -- in "
            "which case they are gone and have to be re-retrieved -- or they "
            "are misspelled here.",
            file=sys.stderr,
        )
    elif not asked:
        # A row that assigns nothing: a plan gap, not a mistyped name.
        print(
            "\n[warn] That section is planned but has no citekeys assigned "
            "to it, so there is nothing to write from. Assign its evidence "
            "in sections.md, or don't dispatch a writer for it.",
            file=sys.stderr,
        )
