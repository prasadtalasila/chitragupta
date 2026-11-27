"""Every way `render()` refuses or fails on a well-formed call, as one tuple.

Callers that degrade on a failed render catch `RENDER_FAILURES`, so they track
what `render()` raises now (#949). `tests/test_render_output_errors.py` checks
every raise site in this package; members raised by callees outside it
(`NoLedger`, `MissingCitekey`, `CalledProcessError`) are kept by hand.
"""

import subprocess

from chitragupta import ledger, reference_entries
from chitragupta.render_output._errors import ConversionError, MissingBinary, OutsideContentDir
from chitragupta.render_output._gate import UngatedDraft
from chitragupta.render_output._math import MathMappingError

RENDER_FAILURES: tuple[type[Exception], ...] = (
    MissingBinary,
    ConversionError,
    OutsideContentDir,
    UngatedDraft,
    MathMappingError,
    subprocess.CalledProcessError,
    ledger.NoLedger,
    reference_entries.MissingCitekey,
)
