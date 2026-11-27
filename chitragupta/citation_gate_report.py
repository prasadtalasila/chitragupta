"""The citation gate's PASS/FAIL lines, in one printer.

So `render`'s pre-gate and `unit accept` report exactly as `run()` does
(#1118); `citation_gate.report` is re-exported.
"""


def report(label: str, result) -> None:
    """Print one `citation_gate.GateResult` in the gate's own shape.

    An unresolved key either has no ledger row (as good as fabricated) or
    is a real `.bib` entry whose PDF never parsed (#1118); the line names
    the status, so the fix is on it.
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
