"""The two failures this stage reports, and the PATH probe behind one.

Its own module so every other module here can raise them without
importing the package root, which imports everything else.
"""

from chitragupta import config, programs


class MissingBinary(RuntimeError):
    pass


class ConversionError(RuntimeError):
    """`_pandoc.markdown_to_latex` could not return one LaTeX text per input (#1138)."""


# Re-exported for `review/citation_provenance.py`. It lives in config.py because
# citation_gate.py and references.py raise it too, and a home in either would close an
# import cycle with render_output.
OutsideContentDir = config.OutsideContentDir


def _require(binary: str) -> None:
    if programs.resolve_program(binary) is None:
        raise MissingBinary(
            f"'{binary}' is not on PATH. This stage needs Pandoc + TeX Live, "
            "which need root to install (apt) and aren't available here. "
            "Use the Docker target (docker/Dockerfile installs both)."
        )
