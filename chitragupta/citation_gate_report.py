"""The citation gate's PASS/FAIL lines, in one printer.

Split from `chitragupta/citation_gate.py`, which is at the 250-code-line
cap, when #1118 gave a FAIL two causes to tell apart. One printer, so a
caller gating a document it already holds in memory (`render`'s pre-gate,
`unit accept`) reports it identically to `run()` rather than
paraphrasing it. `citation_gate` imports `report` back, so
`citation_gate.report` stays the name every caller uses.
"""


def report(label: str, result) -> None:
    """Print one `citation_gate.GateResult` in the gate's own shape.

    An unresolved key is one of two things, and the line says which: no
    ledger row at all (not in the `.bib`, so as good as fabricated), or a
    real `.bib` entry whose PDF never parsed, which nothing in the corpus
    can ground (#1118). The second names the status, so the fix -- attach
    the PDF, or cite something else -- is on the line.
    """
    if result.ok:
        print(
            f"OK    {label}: {result.total_citations} citation(s), all verified against the ledger."
        )
        return
    print(f"FAIL  {label}: {len(result.unknown)} unresolved citekey(s):")
    for line_no, key in result.unknown:
        status = result.unparsed.get(key)
        if status is None:
            why = "not found in ledger -- not sourced from bib sync"
            print(f"        {label}:{line_no}: @{key} {why}")
        else:
            print(
                f"        {label}:{line_no}: @{key} is in the ledger but has no parsed PDF "
                f"(status {status}) -- attach its PDF in Zotero and run sync again"
            )
