"""Which Vale rule implements which dialect, and nothing else.

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
