"""Which module implements each review aid: the one name->module map (#850).

`review.AIDS` owns the names and suffixes and stays import-light for
`dossier`; this maps each aid to its module and `--help` line. Kept out of
`__main__` so `agenda/_refresh.py` can import it at call time without a
cycle.
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

# Keyed by review.AIDS, so no aid appears without its report suffix. Help
# strings live in chitragupta/command_help.py, so `chitragupta --help`
# imports no aid.
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

# A raise, not an assert, which `python -O` strips: this alone stops a
# report being filed under a name the layer cannot find.
if set(AIDS) != set(review.AIDS):
    raise RuntimeError(
        "the entry point's subcommands and review.AIDS have drifted apart: "
        f"{sorted(set(AIDS) ^ set(review.AIDS))}. AIDS owns the report suffixes, "
        "so a subcommand missing from it would write a report nothing can find."
    )
