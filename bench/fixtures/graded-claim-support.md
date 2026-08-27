# Graded fixture for bench_claim_support.py's self-check

Not a draft to gate or render, and never staged under `content/` -- its two
citekeys are not real (they name no item in any ledger) and exist only to
give `citation_provenance.claims()` something to key its extraction on, the
same way `bench_overlap_embed.py`'s own graded fixture exists to give that
script's self-check a section to key on. Paired with the two source
fixtures under `bench/fixtures/graded-claim-support-sources/`, one per
citekey below, which `self_check()` reads directly rather than through
`chitragupta/passages.py`'s content-backed sidecar ladder.

## Entailed

The Great Barrier Reef, stretching more than 2,300 kilometres off the
coast of Queensland, is the largest coral reef system in the world
[@fixture_entailed_case].

## Contradicted

Municipal water fluoridation programmes in the study region had no
measurable effect on childhood cavity rates [@fixture_contradicted_case].
