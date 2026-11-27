"""The third-party Vale rules `draft style` runs, and how their findings
meet the house rules' (#1183, #1186).

The rule files under `assets/vale/styles/` (other than `chitragupta/`)
are byte-identical copies of pinned releases, so what cannot be edited
into them lives here: the WRITING-STANDARDS section each implements
(appended to the message), that none is repaired unattended (they flag
words a draft uses correctly), and which rule wins an overlap.
tests/test_style_vendored.py fails on an overlap not recorded here.
"""

# Rule -> the section of docs/WRITING-STANDARDS.md it implements
# (assets/vale/README.md has the reasons).
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

# Rule -> the rules that win over it on an overlapping span, same line:
# the more specific check, or the one that says what to write instead.
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
    message ending in its section. Judged against Vale's own alerts, so
    each `SHADOWED_BY` pair is one decision, not a chain.
    """
    kept = [f for f in findings if not _shadowed(f, findings)]
    for finding in kept:
        section = SECTIONS.get(finding.get("Check", ""))
        if section:
            finding["Message"] = f"{finding.get('Message', '')} (WRITING-STANDARDS.md §{section})"
    return kept
