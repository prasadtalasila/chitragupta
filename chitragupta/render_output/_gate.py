"""The citation gate, run on the text `draft render` is about to render (#812).

`--format md` used to be the only format that refused a key missing from
the ledger, and only as a side effect of numbering the reference list;
docx, pdf and tex went to pandoc, whose citeproc prints a warning and
writes the document anyway, and `--fragment` deferred every key to
bibtex. This runs the one gate on every draft before any format is
chosen, so no harness, hook or model can render around it.

It is the existing gate at a second point, not a new check: the same
`citation_gate.check_text`, the same report. There is deliberately no
flag to skip it (docs/HOOKS.md, "Deliberately not done").
"""

import contextlib
import io
from pathlib import Path

from chitragupta import citation_gate, ledger
from chitragupta.render_output._substitution import _draft_warnings


class UngatedDraft(ValueError):
    """The draft cites a key the ledger does not hold; str() is the gate's report."""


def gated_warnings(draft_text: str, input_path: Path) -> "list[tuple[str, str]]":
    """`_draft_warnings(draft_text, input_path)`, once the gate has passed the draft.

    A citation-free draft never opens the ledger, so a pre-sync teaching
    draft still renders with no ledger at all -- the property
    docs/HOOKS.md measured for the gate itself. A citing draft with no
    ledger raises `ledger.NoLedger`, whose message says to run `sync`:
    more use to the reader than a list of every key as unknown.
    """
    if citation_gate.extract_citekeys_for(input_path, draft_text):
        with ledger.reading() as con:
            known = ledger.known_citekeys(con)
        result = citation_gate.check_text(input_path, draft_text, known)
        if not result.ok:
            raise UngatedDraft(_report(input_path, result))
    return _draft_warnings(draft_text, input_path)


def _report(input_path: Path, result: citation_gate.GateResult) -> str:
    # The gate's own wording, not a paraphrase, so a skill that already
    # reacts to a gate failure reads the same lines here -- and so the
    # refusal names each bad key and its line, and never a "closest" one.
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        citation_gate.report(str(input_path), result)
    return "the citation gate refuses this draft, so it was not rendered.\n" + buffer.getvalue()
