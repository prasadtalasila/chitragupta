"""The citation gate, run on the text `draft render` is about to render (#812).

Runs on every draft before any format is chosen, so nothing can render
around it; pandoc's citeproc only warns. Deliberately no flag to skip it
(docs/HOOKS.md, "Deliberately not done").
"""

import contextlib
import io
from pathlib import Path

from chitragupta import citation_gate, ledger
from chitragupta.ledger_citable import citable_citekeys, unparsed_citekeys
from chitragupta.render_output._substitution import _draft_warnings


class UngatedDraft(ValueError):
    """The draft cites a key the ledger does not hold; str() is the gate's report."""


def gated_warnings(draft_text: str, input_path: Path) -> "list[tuple[str, str]]":
    """`_draft_warnings(draft_text, input_path)`, once the gate has passed the draft.

    A citation-free draft never opens the ledger, so it renders pre-sync. A
    citing draft with no ledger raises `ledger.NoLedger`, which says to sync.
    """
    if citation_gate.extract_citekeys_for(input_path, draft_text):
        with ledger.reading() as con:
            known, unparsed = citable_citekeys(con), unparsed_citekeys(con)
        result = citation_gate.check_text(input_path, draft_text, known, unparsed)
        if not result.ok:
            raise UngatedDraft(_report(input_path, result))
    return _draft_warnings(draft_text, input_path)


def _report(input_path: Path, result: citation_gate.GateResult) -> str:
    # The gate's own wording, so skills react the same way, and the refusal
    # names each bad key and line, never a "closest" one.
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        citation_gate.report(str(input_path), result)
    return "the citation gate refuses this draft, so it was not rendered.\n" + buffer.getvalue()
