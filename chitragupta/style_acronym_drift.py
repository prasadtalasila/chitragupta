"""The one `python -m chitragupta.draft style` finding this repository doesn't
hand to Vale.

Vale never reads the per-host acronym vocabulary, so this checks a
draft's recorded glossary (`scope.md`'s `## Glossary`) against it in
plain Python. It does not scan the draft body for differing expansions;
see docs/WRITING-STANDARDS.md §9 and #190.
"""

from pathlib import Path

from chitragupta import acronyms, dossier

RULE = "chitragupta.AcronymDrift"


def findings(draft: Path) -> list[dict]:
    """One finding per acronym whose glossary expansion disagrees with the
    vocabulary, in `style_check.collapse()`'s shape so the two merge.

    `line` is always 0 (the mismatch is between two files, and the message
    says so). `[]` for a draft outside content/, which has no dossier.
    """
    try:
        glossary = dossier.glossary_terms(draft)
    except dossier.DossierError:
        return []
    stale = acronyms.stale_expansions(glossary)
    return [
        {
            "rule": RULE,
            "match": term,
            "line": 0,
            "message": (
                f"'{term}' is defined in this draft's glossary as "
                f"'{glossary_expansion}', but the current acronym "
                f"vocabulary defines it as '{vocabulary_expansion}' "
                "(WRITING-STANDARDS.md §9). Checked against the "
                "dossier's recorded glossary, not the draft's own prose."
            ),
            "severity": "suggestion",
            "count": 1,
        }
        for term, (glossary_expansion, vocabulary_expansion) in sorted(stale.items())
    ]
