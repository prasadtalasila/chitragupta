"""Which module implements each review aid: the one name->module map (#850).

`review.AIDS` (`review/__init__.py`) names the aids and owns their report
suffixes, and stays import-light so `dossier` can read it without loading
eleven aids. This is the other half: the module that runs each one, and the
one-line description its subcommand shows in `--help`. It used to live
in `review/__main__.py`, which made it unreachable from
`agenda/_refresh.py` without a cycle -- `__main__` imports `agenda`,
which imports `_refresh` -- so `_refresh` kept a hand-copied map of its
own. Here, `_refresh` imports it at call time, after every aid module has
finished loading, and the entry point imports it at the top.
"""

from chitragupta import review
from chitragupta.command_help import verbs
from chitragupta.review import (
    agenda,
    citation_coverage,
    citation_provenance,
    citekey_union,
    claim_support,
    figure_layout,
    quotation,
    synthesis,
    uncited_prose,
    verbatim_check,
    verbatim_digest,
)

# Keyed by review.AIDS, so a new aid cannot appear here without also
# appearing in the dict that owns the report suffixes.
# The help strings live in chitragupta/command_help.py, so `chitragupta
# --help`'s tree can print them without importing a single aid.
AIDS = {
    aid: (module, verbs("review")[aid])
    for aid, module in {
        "provenance": citation_provenance,
        "verbatim": verbatim_check,
        "coverage": citation_coverage,
        "synthesis": synthesis,
        "figure": figure_layout,
        "uncited": uncited_prose,
        "quotation": quotation,
        "agenda": agenda,
        "support": claim_support,
        "union": citekey_union,
        "digest": verbatim_digest,
    }.items()
}

# A raise rather than an assert: `python -O` strips assertions, and this
# is the one check standing between a mistyped subcommand and a report
# filed under a name the rest of the layer cannot find. An invariant
# worth stating is worth stating in every interpreter mode.
if set(AIDS) != set(review.AIDS):
    raise RuntimeError(
        "the entry point's subcommands and review.AIDS have drifted apart: "
        f"{sorted(set(AIDS) ^ set(review.AIDS))}. AIDS owns the report suffixes, "
        "so a subcommand missing from it would write a report nothing can find."
    )
