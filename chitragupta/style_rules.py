"""Which rules `draft style` runs: the Python-side checks, which Vale
rule implements which dialect, and how a dialect finding may be
repaired. Shared by `style_check` and `style_report`.
"""

from chitragupta.style_acronym_case import findings as acronym_case_findings
from chitragupta.style_acronym_drift import findings as acronym_drift_findings
from chitragupta.style_bare_citekeys import findings as bare_citekey_findings
from chitragupta.style_equations import findings as equation_findings
from chitragupta.style_figures import findings as figure_findings
from chitragupta.style_headings import findings as heading_findings
from chitragupta.style_tables import findings as table_findings
from chitragupta.style_typeset import findings as typeset_findings
from chitragupta.style_vendored import SECTIONS

# Every Python-side rule, in report order: a module with
# `findings(draft) -> list[dict]`, each finding carrying its own `repair`
# mode (#836, #852). tests/test_style_check.py fails on a `style_*.py`
# defining `findings` that is missing here, as it would run nowhere.
PYTHON_CHECKS = (
    acronym_drift_findings,
    acronym_case_findings,
    table_findings,
    figure_findings,
    equation_findings,
    typeset_findings,
    heading_findings,
    bare_citekey_findings,
)

# Which rule to keep for a BCP-47 tag. An unknown tag disables dialect
# checking rather than guessing. en-IN is not en-GB: British English
# accepts Oxford -ize, while Indian English prefers -ise (DialectIN).
_DIALECT_GB = "chitragupta.DialectGB"
_DIALECT_US = "chitragupta.DialectUS"
_DIALECT_IN = "chitragupta.DialectIN"

DIALECT_RULES = {
    "en-GB": _DIALECT_GB,
    "en-US": _DIALECT_US,
    "en-IN": (_DIALECT_GB, _DIALECT_IN),
}

_ALL_DIALECT_RULES = (_DIALECT_GB, _DIALECT_US, _DIALECT_IN)

# Where a dialect is the author's own statement; `config.toml` is a host
# preference (see `style_check`'s docstring).
_AUTHOR_SOURCES = ("scope.md", "--language")

# Rules whose every finding needs a reader: `Just` cannot tell the filler
# adverb from the adjective, and the others' repairs rewrite a sentence
# around its claim (WRITING-STANDARDS.md §4).
_ALWAYS_REVIEW = (
    "chitragupta.Just",
    "chitragupta.BorrowedAuthority",
    "chitragupta.DeepSaying",
    "chitragupta.Inflated",
    "chitragupta.KnowledgeLimit",
    "chitragupta.PlainVerbs",
    "chitragupta.RunUp",
    "chitragupta.Strawman",
)


def with_repair(findings: "list[dict]", language_source: str) -> "list[dict]":
    """Vale's collapsed `findings`, each stamped with a `repair` mode
    (issue 836).

    `"review"` for: a dialect finding when the dialect did not come from
    the author; one whose match starts with a capital, as it may be a
    proper name (only the mode is downgraded, #1187); `_ALWAYS_REVIEW`;
    and every vendored rule (#1186). Every other Vale rule is `"edit"`.
    """
    for finding in findings:
        dialect = finding["rule"] in _ALL_DIALECT_RULES
        vendored = finding["rule"] in SECTIONS
        review = (
            finding["rule"] in _ALWAYS_REVIEW
            or vendored
            or (
                dialect
                and (language_source not in _AUTHOR_SOURCES or finding["match"][:1].isupper())
            )
        )
        finding["repair"] = "review" if review else "edit"
    return findings
