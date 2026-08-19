"""The one `python -m chitragupta.draft style` finding this repository doesn't
hand to Vale.

Vale's `Acronyms.yml` can verify an acronym was expanded somewhere near
its first use; it cannot know what a user's own vocabulary currently
says an acronym expands to, because that vocabulary lives in a per-host
TOML file (`chitragupta.acronyms.load_vocabulary()`) Vale never reads. This is
that other half: a draft's own recorded glossary (`scope.md`'s
`## Glossary`), checked against the vocabulary right now, in plain
Python -- the first `style_check.py` finding not delegated to Vale.

**Reports only what it can see: the dossier's glossary, not the draft's
own prose.** A term whose glossary bullet still agrees with the
vocabulary but whose body text expands it differently produces no
finding here -- catching that would mean scanning the draft body the way
Vale's own regex-based rule does, a different and much more expensive
check this module does not attempt. See docs/WRITING-STANDARDS.md §9 and
GitHub issue #190.
"""

from pathlib import Path

from chitragupta import acronyms, dossier

RULE = "chitragupta.AcronymDrift"


def findings(draft: Path) -> list[dict]:
    """One finding per acronym whose glossary-recorded expansion
    disagrees with the vocabulary -- the same shape
    `style_check.collapse()` produces from Vale's own findings, so the
    two merge into one report without `style_report.py` needing to know
    which check produced which line.

    `line` is always 0: the mismatch is between two files (`scope.md`
    and the vocabulary file), not a position in the draft Vale could
    point at -- the message says so explicitly rather than let a `0`
    read as a line number nobody wrote at.

    `[]` for a draft with no dossier to compute a path for -- the same
    "a draft outside content/ has no dossier path to compute" case
    `style_check.language_of()` already guards against, not an error
    specific to this check.
    """
    try:
        glossary = dossier.glossary_terms(draft)
    except Exception:  # pylint: disable=broad-except
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
