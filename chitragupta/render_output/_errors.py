"""The two failures this stage reports, and the PATH probe behind one.

Split out of the single `render_output.py` module so that every other
module here can raise them without importing the package root, which
imports `render()`, which imports everything else.
"""

from chitragupta import config, programs


class MissingBinary(RuntimeError):
    pass


# Re-exported: this name shipped here first, and
# chitragupta/review/citation_provenance.py catches it as `render_output.OutsideContentDir`.
# It now lives in chitragupta/config.py, because chitragupta/citation_gate.py and
# chitragupta/references.py started raising it too and needed a home neither of
# them could import from -- render_output already imports citation_gate
# (`_gate.py`, `_chapter_number.py`), so a shared helper in either would close a
# cycle.
OutsideContentDir = config.OutsideContentDir


def _require(binary: str) -> None:
    if programs.resolve_program(binary) is None:
        raise MissingBinary(
            f"'{binary}' is not on PATH. This stage needs Pandoc + TeX Live, "
            "which need root to install (apt) and aren't available here. "
            "Use the Docker target (docker/Dockerfile installs both)."
        )
