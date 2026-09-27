"""Which Vale rule implements which dialect, and how a dialect finding
may be repaired.

A table two modules need -- `style_check` to build Vale's `--filter`, and
`style_report` to tell a recorded tag this style cannot check from one it
can. Its own module so neither imports the other.
"""

# Which rule to keep for a given BCP-47 tag. Everything not named here is
# filtered out, so an unknown tag disables dialect checking rather than
# defaulting to one -- an unrecognised `language:` is a typo or a locale
# this style does not cover, and both deserve silence over a guess.
#
# en-IN is not an alias for en-GB. British English accepts both -ise and
# Oxford -ize, so DialectGB cannot flag -ize without reporting correct
# prose; Indian English prefers -ise, and DialectIN is that one check.
_DIALECT_GB = "chitragupta.DialectGB"
_DIALECT_US = "chitragupta.DialectUS"
_DIALECT_IN = "chitragupta.DialectIN"

DIALECT_RULES = {
    "en-GB": _DIALECT_GB,
    "en-US": _DIALECT_US,
    "en-IN": (_DIALECT_GB, _DIALECT_IN),
}

_ALL_DIALECT_RULES = (_DIALECT_GB, _DIALECT_US, _DIALECT_IN)

# The two places a dialect is the author's own statement. `config.toml`
# is a standing preference for the machine, not for this draft, and
# `style_check`'s own docstring says why it may be wrong for one.
_AUTHOR_SOURCES = ("scope.md", "--language")


def with_repair(findings: "list[dict]", language_source: str) -> "list[dict]":
    """Vale's collapsed `findings`, each stamped with the `repair` mode
    `style_elements.finding` gives the Python-side ones (issue 836).

    A dialect finding is `"review"` unless the dialect came from the
    author: re-spelling a whole draft to a host-wide default is not a
    repair to make unattended when the draft's own dialect may be the
    deliberate one. Every other Vale rule is an `"edit"`.
    """
    for finding in findings:
        dialect = finding["rule"] in _ALL_DIALECT_RULES
        review = dialect and language_source not in _AUTHOR_SOURCES
        finding["repair"] = "review" if review else "edit"
    return findings
