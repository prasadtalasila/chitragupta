"""The third-party Vale rules `draft style` runs, and how their findings
meet the house rules' (#1183, #1186).

The rule files under `assets/vale/styles/` other than `chitragupta/` are
copied byte-identical from pinned releases of four packages, and
`vale.ini` switches each one on by name. Three things about them cannot
live in those files without editing them, so they live here:

- **Which section of docs/WRITING-STANDARDS.md each rule implements.**
  The packages' messages name none, and a finding a reader cannot trace
  to a rule is one they cannot judge, so the section is appended to the
  message on the way out.
- **That none may be repaired unattended.** Every vendored finding is
  `review` (see `style_rules.with_repair`): the packages were written for
  other prose, and even their narrowest lists hold words a draft uses
  correctly ("absolutely continuous", "If anything is unclear" in a
  tutorial, the noun "pettifogger").
- **Which rule wins when two report the same words.** The packages were
  written independently, and a handful of phrases sit in two of them:
  "at the end of the day" is both a cliché and a conclusion marker. The
  files cannot be edited to remove the copy, so the copy is dropped from
  the findings instead. tests/test_style_vendored.py feeds every rule
  file's tokens to Vale and fails on an overlap that is neither listed
  here nor recorded there as two different checks.
"""

# Rule -> the section of docs/WRITING-STANDARDS.md it implements.
# assets/vale/README.md has the same list with the reason for each.
SECTIONS = {
    "proselint.Cliches": 4,
    "proselint.Hedging": 4,
    "proselint.Hyperbole": 4,
    "proselint.Malapropisms": 4,
    "proselint.Needless": 4,
    "proselint.Nonwords": 4,
    "proselint.Oxymorons": 4,
    "proselint.RASSyndrome": 4,
    "proselint.Skunked": 4,
    "proselint.Uncomparables": 4,
    "proselint.Very": 4,
    "ai-tells.ClosingPleasantries": 4,
    "ai-tells.ConclusionMarkers": 4,
    "ai-tells.ContrastiveFormulas": 4,
    "ai-tells.NegatedPair": 4,
    "ai-tells.PromotionalPuffery": 4,
    "ai-tells.PseudoCleft": 4,
    "ai-tells.StackedHedges": 4,
    "ai-tells.SycophancyMarkers": 4,
    "Journals.EtAl": 4,
    "Journals.Hype": 4,
    "Journals.PValueCase": 4,
    "Journals.PValueZero": 4,
    "Journals.Placeholder": 7,
    "Journals.Prove": 7,
    "Journals.Significant": 7,
    "Journals.UnitSpacing": 4,
    "Journals.UnitSymbols": 4,
    "PLOS.PValues": 4,
    "Microsoft.Plurals": 4,
    "Microsoft.Uppercase": 4,
    "Microsoft.Wordiness": 4,
}

# Rule -> the rules that win over it. A finding of the rule on the left
# whose span overlaps, on the same line, a finding of one on the right is
# dropped. The winner is the more specific check, or the one whose
# message says what to write instead.
SHADOWED_BY = {
    "proselint.Cliches": ("ai-tells.ConclusionMarkers", "Microsoft.Wordiness"),
    "proselint.Needless": ("proselint.Nonwords",),
    "proselint.Skunked": ("ai-tells.ClosingPleasantries",),
    "proselint.Very": ("proselint.Uncomparables",),
    "chitragupta.Strawman": ("ai-tells.ContrastiveFormulas",),
    "Microsoft.Wordiness": ("ai-tells.ClosingPleasantries", "ai-tells.ConclusionMarkers"),
    "Journals.Prove": ("ai-tells.ClosingPleasantries",),
    "ai-tells.SycophancyMarkers": ("chitragupta.DefectMarkers", "ai-tells.ClosingPleasantries"),
}


def _overlaps(a: dict, b: dict) -> bool:
    return a["Line"] == b["Line"] and a["Span"][0] <= b["Span"][1] and b["Span"][0] <= a["Span"][1]


def _shadowed(finding: dict, findings: list[dict]) -> bool:
    winners = SHADOWED_BY.get(finding.get("Check", ""), ())
    return any(other.get("Check") in winners and _overlaps(finding, other) for other in findings)


def reconcile(findings: list[dict]) -> list[dict]:
    """Vale's alerts with each shadowed copy dropped and each vendored
    message ending in the section its rule implements.

    Judged against the alerts as Vale gave them, so a winner that is
    itself shadowed still removes its own losers: each pair in
    `SHADOWED_BY` is one decision, not a chain to follow.
    """
    kept = [f for f in findings if not _shadowed(f, findings)]
    for finding in kept:
        section = SECTIONS.get(finding.get("Check", ""))
        if section:
            finding["Message"] = f"{finding.get('Message', '')} (WRITING-STANDARDS.md §{section})"
    return kept
