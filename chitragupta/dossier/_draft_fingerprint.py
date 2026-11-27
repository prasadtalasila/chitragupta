"""Notice that the draft moved (#454, FEATURE-ROADMAP.md's E3): a text
fingerprint for the draft, beside `scope.md`'s corpus one, plus the five
staleness classes a changed fingerprint can mean: a citekey cited with no
`evidence.md` block, an `evidence.md` block no longer cited, a heading
with no `sections.md` row, a `sections.md` row with no heading, and a
`math.md` row whose span is gone from the draft.

Headings compare as a set of titles (row order carries nothing). Uses
`chitragupta.spec.digest` (text), not `dossier.digest` (an unordered
citekey set that a rewording would not move), as `unit.state()` does.

**Who stamps.** There is no Python chokepoint on a skill's edits, so
`draft-reviser` calls `dossier stamp` after the gate passes. A forgotten
stamp reads as a human edit, the safe direction to fail.

**The five classes are gated on `changed`**: unconditionally they would
fire on nearly every legacy or hand-edited dossier, and nobody reads a
permanent wall of findings.
"""

import argparse
import re
from dataclasses import dataclass, field
from pathlib import Path

from chitragupta import citation_gate
from chitragupta.dossier import SCOPE_MD, dossier_dir, draft_relpath
from chitragupta.dossier._citekeys import citekeys_by_section, evidence_blocks
from chitragupta.dossier._sections import sections
from chitragupta.render_output import _math, _math_findings, _math_symbols

# The draft-digest line in scope.md, read like the corpus line: any other
# shape (or absence) means "no baseline", never an error.
_DRAFT_DIGEST_LINE = re.compile(r"^-\s*draft digest:.*$", re.MULTILINE)

_DRAFT_DIGEST_VALUE = re.compile(r"`([0-9a-f]{12})`")


def recorded_draft_digest(dossier: Path) -> "str | None":
    """The digest `stamp` last recorded for this dossier's draft.

    `None` for never stamped, no scope.md, or a hand-mangled line: all
    mean there is no baseline.
    """
    scope = dossier / SCOPE_MD
    if not scope.is_file():
        return None
    line = _DRAFT_DIGEST_LINE.search(scope.read_text(encoding="utf-8"))
    if not line:
        return None
    value = _DRAFT_DIGEST_VALUE.search(line.group(0))
    return value.group(1) if value else None


def stamp(draft: Path) -> Path:
    """Record `draft`'s current digest into its dossier's `scope.md`.

    Rewrites the line in place, or appends it once for an older dossier;
    nothing else changes. Raises with no dossier rather than writing a
    fingerprint nothing else describes.
    """
    # Deferred: `chitragupta.spec` imports `chitragupta.dossier._sections`,
    # so a module-level import would hit a partially imported spec
    # (`_archive.py` defers likewise).
    from chitragupta.spec import digest as text_digest

    if not draft.is_file():
        raise FileNotFoundError(f"No draft at {draft}.")
    scope = dossier_dir(draft) / SCOPE_MD
    if not scope.is_file():
        raise FileNotFoundError(f"No scope.md at {scope} -- run `dossier init` before stamping.")
    line = f"- draft digest: `{text_digest(draft.read_text(encoding='utf-8'))}`"
    text = scope.read_text(encoding="utf-8")
    if _DRAFT_DIGEST_LINE.search(text):
        text = _DRAFT_DIGEST_LINE.sub(lambda _match: line, text, count=1)
    else:
        text = text.rstrip("\n") + "\n" + line + "\n"
    scope.write_text(text, encoding="utf-8")
    return scope


@dataclass
class Staleness:
    """What moved in a draft since its dossier's last `stamp`.

    The five list fields stay empty until `changed` (module docstring).
    """

    recorded_digest: "str | None"
    current_digest: str
    missing_evidence: "list[str]" = field(default_factory=list)
    orphaned_evidence: "list[str]" = field(default_factory=list)
    new_headings: "list[str]" = field(default_factory=list)
    stale_section_rows: "list[str]" = field(default_factory=list)
    desynced_math: "list[str]" = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return self.recorded_digest is not None and self.recorded_digest != self.current_digest


def _math_desync(draft: Path, text: str) -> "list[str]":
    """The `math.md` orphans among `_math_findings.findings()`'s results.

    Orphans only: gaps are a hygiene finding, not evidence the draft
    moved. Selected on `MathFinding.kind`, not message wording, so a
    reworded warning cannot empty the check (#506/m-66).
    """
    mapping = _math.load_mapping(draft)
    mapping_file = _math.mapping_path(draft)
    has_mapping_file = mapping_file is not None and mapping_file.is_file()
    return [
        finding.message
        for finding in _math_findings.findings(
            text, mapping, has_mapping_file, glossary=_math_symbols.glossary_spans(draft)
        )
        if finding.kind == "orphan"
    ]


def staleness(draft: Path) -> Staleness:
    from chitragupta.spec import digest as text_digest  # see stamp()'s comment

    target = dossier_dir(draft)
    text = draft.read_text(encoding="utf-8")
    report = Staleness(recorded_draft_digest(target), text_digest(text))
    if not report.changed:
        return report

    cited = {key for _, key in citation_gate.extract_citekeys_for(draft, text)}
    recorded_evidence = set(evidence_blocks(target))
    report.missing_evidence = sorted(cited - recorded_evidence)
    report.orphaned_evidence = sorted(recorded_evidence - cited)

    headings = {section.title for section in sections(text)}
    recorded_sections = set(citekeys_by_section(target))
    report.new_headings = sorted(headings - recorded_sections)
    report.stale_section_rows = sorted(recorded_sections - headings)

    report.desynced_math = _math_desync(draft, text)
    return report


def recorded_but_uncited(draft: Path) -> "dict[str, list[str]]":
    """citekey -> which dossier files still record it, for the citekeys
    the draft's text no longer cites (#701).

    Deliberately ungated, unlike `Staleness.orphaned_evidence`: that needs
    a stamp, which no dossier before stamping has, and reads only
    `evidence.md`. `rejected.md` is **not** read: a recorded rejection is
    not a defect. Reads the two `CITED_FILES` separately to name *which*
    file still records the key.
    """
    target = dossier_dir(draft)
    text = draft.read_text(encoding="utf-8")
    cited = {key for _, key in citation_gate.extract_citekeys_for(draft, text)}
    surfaces = {
        "evidence": set(evidence_blocks(target)),
        "sections": {key for keys in citekeys_by_section(target).values() for key in keys},
    }
    found: dict[str, list[str]] = {}
    for surface, recorded in surfaces.items():
        for citekey in recorded - cited:
            found.setdefault(citekey, []).append(surface)
    return {citekey: sorted(names) for citekey, names in sorted(found.items())}


def status_lines(report: Staleness) -> "list[str]":
    lines = ["Draft fingerprint:"]
    if report.recorded_digest is None:
        lines.append("  not recorded -- run `dossier stamp` once the draft is ready.")
        return lines
    if not report.changed:
        lines.append(f"  unchanged since last stamp (digest `{report.recorded_digest}`).")
        return lines
    lines.append(
        f"  CHANGED since last stamp (was `{report.recorded_digest}`, "
        f"now `{report.current_digest}`)."
    )
    for key in report.missing_evidence:
        lines.append(f"    `{key}` is cited but has no evidence.md block")
    for key in report.orphaned_evidence:
        lines.append(f"    `{key}` has an evidence.md block but is no longer cited")
    for title in report.new_headings:
        lines.append(f'    "{title}" is a heading with no row in sections.md')
    for title in report.stale_section_rows:
        lines.append(f'    "{title}" has a sections.md row but no matching heading')
    lines.extend(f"    {warning}" for warning in report.desynced_math)
    return lines


def _cmd_stamp(args: argparse.Namespace) -> int:
    draft = Path(args.draft)
    if not draft.is_file():
        print(f"No such draft: {args.draft}")
        return 1
    try:
        stamp(draft)
    except FileNotFoundError:
        print(
            f"No dossier at {draft_relpath(dossier_dir(draft))}. Create one with "
            f"`python -m chitragupta.draft dossier init {args.draft} --genre <genre>`."
        )
        return 1
    digest = recorded_draft_digest(dossier_dir(draft))
    print(f"{draft_relpath(draft)}: stamped at digest `{digest}`")
    return 0
