"""Every way `render()` refuses or fails on a well-formed call, as one tuple.

A caller that degrades on a failed render catches `RENDER_FAILURES`, so it
catches what `render()` raises now rather than what it raised when the
caller was written: `review.write` listed three classes and missed the
four added since (`MathMappingError`, `MissingCitekey`, `NoLedger`,
`UngatedDraft`), so a review report quoting an unknown `[@key]` crashed
the aid (#949). `review.write` catches exactly this tuple; `_cli.main`
reports each member by name.

`tests/test_render_output_errors.py` walks every raise site in this
package and fails on a class that is not in here. The members raised from
outside it (`ledger.NoLedger` from the gate's ledger read,
`reference_entries.MissingCitekey` from `--format md`'s numbering,
pandoc's `CalledProcessError`) are kept by hand, so a new raise in one of
those callees still has to be added here.

Its own module rather than beside `render()` in the package root only
because that file is at the code-line limit (docs/CODE-STANDARDS.md).
"""

import subprocess

from chitragupta import ledger, reference_entries
from chitragupta.render_output._errors import MissingBinary, OutsideContentDir
from chitragupta.render_output._gate import UngatedDraft
from chitragupta.render_output._math import MathMappingError

RENDER_FAILURES: tuple[type[Exception], ...] = (
    MissingBinary,
    OutsideContentDir,
    UngatedDraft,
    MathMappingError,
    subprocess.CalledProcessError,
    ledger.NoLedger,
    reference_entries.MissingCitekey,
)
