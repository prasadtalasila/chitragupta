"""Notice that the draft moved (#454, FEATURE-ROADMAP.md's E3): a text
fingerprint for the draft, beside `scope.md`'s corpus one, plus the four
staleness classes a changed fingerprint can mean.

`scope.md`'s corpus line already answers "has the corpus moved since
this draft was written?" (`dossier.recorded_corpus`). Nothing answered
the same question about the draft itself, so a hand edit left
`sections.md`, `evidence.md` and `math.md` describing a document that no
longer existed, and `draft-reviser` had no way to know.

Reuses `chitragupta.spec.digest` -- a plain sha256[:12] of the text --
not `dossier.digest`, which is order-independent over a *set of
citekeys* and would not move at all for a reworded sentence. The book
track's `unit.state()` already draws exactly this line, between
`spec.digest` for prose and this package's own `digest` for citekeys;
this module makes the same choice for a single draft instead of a book
unit.

**Who stamps.** A draft is written by a skill's `Edit` calls, so there is
no Python chokepoint to hook automatically. `draft-reviser` calls
`stamp()` (via `dossier stamp`) itself, after `python -m chitragupta.draft
gate` passes -- the same point `scope.md`'s corpus line is already
re-stamped at, by hand, in re-grounding mode. A pipeline that forgets to
stamp reads as a human edit on the next `status`, which is the right
direction to fail: a false "you edited this" costs one confirmation; a
missed stamp would silently corrupt every later drift check.

**Why the four classes are gated on `changed`.** Computed unconditionally
they would fire on nearly any real dossier -- a legacy one predates
`sections.md` matching every heading, and a hand-edited `evidence.md`
routinely lags a draft by one citation. A permanent wall of findings on
every `status` run is noise nobody reads; gating on "the digest moved at
all" first is what keeps a healthy, unedited draft's report silent.
"""

import argparse
import re
from dataclasses import dataclass, field
from pathlib import Path

from chitragupta import citation_gate
from chitragupta.dossier import SCOPE_MD, dossier_dir, draft_relpath
from chitragupta.dossier._citekeys import citekeys_by_section, evidence_blocks
from chitragupta.dossier._sections import sections
from chitragupta.render_output import _math

# `- draft digest: `a1b2c3d4e5f6`` or `- draft digest: not recorded (...)`
# in scope.md -- one field over from `dossier._CORPUS_LINE`'s corpus
# fingerprint, and read the same way: a line outside this shape (hand
# rewritten to something else, or simply absent) means "no baseline",
# never an error.
_DRAFT_DIGEST_LINE = re.compile(r"^-\s*draft digest:.*$", re.MULTILINE)

_DRAFT_DIGEST_VALUE = re.compile(r"`([0-9a-f]{12})`")


def recorded_draft_digest(dossier: Path) -> "str | None":
    """The digest `stamp` last recorded for this dossier's draft.

    `None` covers "never stamped", "no scope.md" and "the line was
    hand-edited outside the recognised shape" alike -- all three mean the
    same thing to every caller: there is no baseline to compare the
    current draft against.
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

    Rewrites the `- draft digest:` line in place -- whichever shape it
    was in, freshly-initialised `not recorded` or a prior digest --
    rather than appending a second one; appends it once, at the end of
    the file, for a dossier that predates this field entirely. Everything
    else in `scope.md` is left untouched.

    Raises rather than guessing if there is no dossier to stamp: this is
    the one place a caller could otherwise silently write a fingerprint
    for a draft nothing else in the dossier describes yet.
    """
    # Deferred: `chitragupta.spec` imports `chitragupta.dossier._sections`,
    # and this module is reached from `chitragupta.dossier._cli`, which
    # `chitragupta.dossier.__init__` imports at its own bottom -- a
    # module-level import here would ask for `chitragupta.spec.digest`
    # while `chitragupta.spec` is still mid-import. `_archive.py`'s
    # `evidence_appendix` import defers for the same reason.
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

    The four list fields stay empty until `changed` is true -- see the
    module docstring for why an unconditional scan would drown `status`
    in findings on almost any real dossier.
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
    """The `math.md` orphans among `_math.warnings()`'s findings.

    Filtered to orphans only -- a row with no matching span, the tell
    that a revision reworded or deleted the sentence it belonged to.
    `warnings()` also reports *gaps* (a quantity-shaped span with no
    row), which is a pre-existing hygiene finding rather than evidence
    that the draft moved, so it is deliberately excluded here.
    """
    mapping = _math.load_mapping(draft)
    mapping_file = _math.mapping_path(draft)
    has_mapping_file = mapping_file is not None and mapping_file.is_file()
    return [
        warning
        for warning in _math.warnings(text, mapping, has_mapping_file)
        if warning.endswith("appears nowhere in the draft")
    ]


def staleness(draft: Path) -> Staleness:
    """What changed in `draft` since its dossier's last `stamp`."""
    from chitragupta.spec import digest as text_digest  # see stamp()'s comment

    target = dossier_dir(draft)
    text = draft.read_text(encoding="utf-8")
    report = Staleness(recorded_draft_digest(target), text_digest(text))
    if not report.changed:
        return report

    cited = {
        key for _, key in citation_gate.extract_citekeys(text, latex=draft.suffix.lower() == ".tex")
    }
    recorded_evidence = set(evidence_blocks(target))
    report.missing_evidence = sorted(cited - recorded_evidence)
    report.orphaned_evidence = sorted(recorded_evidence - cited)

    headings = {section.title for section in sections(text)}
    recorded_sections = set(citekeys_by_section(target))
    report.new_headings = sorted(headings - recorded_sections)
    report.stale_section_rows = sorted(recorded_sections - headings)

    report.desynced_math = _math_desync(draft, text)
    return report


def status_lines(report: Staleness) -> "list[str]":
    """`dossier status`'s draft-fingerprint block, as printable lines.

    Kept here rather than folded into `_status.py`'s own print helpers,
    which are already close to docs/CODE-STANDARDS.md's C2 line limit --
    a registered file is not a licence to keep growing it.
    """
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
