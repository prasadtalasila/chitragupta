"""Which module implements each review aid: the one name->module map (#850).

`review.AIDS` (`review/__init__.py`) names the aids and owns their report
suffixes, and stays import-light so `dossier` can read it without loading
ten aids. This is the other half: the module that runs each one, and the
one-line description its subcommand shows in `--help`. It used to live
in `review/__main__.py`, which made it unreachable from
`agenda/_refresh.py` without a cycle -- `__main__` imports `agenda`,
which imports `_refresh` -- so `_refresh` kept a hand-copied map of its
own. Here, `_refresh` imports it at call time, after every aid module has
finished loading, and the entry point imports it at the top.
"""

from chitragupta import review
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
)

# Keyed by review.AIDS, so a new aid cannot appear here without also
# appearing in the dict that owns the report suffixes.
AIDS = {
    "provenance": (citation_provenance, "what in the source supports this claim?"),
    "verbatim": (verbatim_check, "verbatim overlap with one source, or with the whole corpus"),
    "coverage": (citation_coverage, "retrieval surfaced it -- did the draft cite it?"),
    "synthesis": (synthesis, "how many sources does each unit of the draft rest on?"),
    "figure": (figure_layout, "what a TikZ figure's own geometry says about it"),
    "uncited": (uncited_prose, "which sentences of the draft carry no citation?"),
    "quotation": (quotation, "is each quoted span really in the source it cites?"),
    "agenda": (agenda, "one ranked, deduplicated worklist across every other aid"),
    "support": (claim_support, "does the cited source entail this claim?"),
    "union": (citekey_union, "does the assembly still carry every unit's citekeys?"),
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
