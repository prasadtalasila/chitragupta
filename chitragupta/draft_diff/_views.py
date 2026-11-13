"""The three things `draft diff` can compare, made to look alike.

A snapshot, the live draft and a bare `--against` file are each a source
text plus, where they can be found, both forms of every figure the text
names. Figures are read with the same sibling resolution the snapshot
store and the renderer use, so a figure path that escapes the draft's
directory is never read here either.
"""

from dataclasses import dataclass
from pathlib import Path

from chitragupta.dossier._versions import _FIGURE_FORMS, Snapshot, figure_names
from chitragupta.render_output._figures import _resolve_sibling


@dataclass(frozen=True)
class FigureForms:
    """A figure's TikZ (`.tex`) and ASCII (`.txt`) text, None where absent."""

    tikz: str | None
    ascii: str | None


@dataclass(frozen=True)
class VersionView:
    """One side of a comparison."""

    ref: str  # "004", "current draft", or a file name
    label: str  # manual label or revision label, may be ""
    date: str  # "YYYY-MM-DD", or "" for a file
    text: str
    suffix: str  # ".md" | ".tex"
    # None when the figures are unknown: a bare `--against` file with no
    # `figures/` beside it, which says nothing about what was drawn.
    figures: "dict[str, FigureForms] | None"


def _read_form(base: Path, ref: str) -> str | None:
    path = _resolve_sibling(base, ref)
    return path.read_text(encoding="utf-8") if path is not None else None


def _figures(base: Path, text: str, suffix: str) -> dict[str, FigureForms]:
    tikz_form, ascii_form = _FIGURE_FORMS
    return {
        name: FigureForms(
            tikz=_read_form(base, f"{name}{tikz_form}"),
            ascii=_read_form(base, f"{name}{ascii_form}"),
        )
        for name in figure_names(text, suffix)
    }


def _view(source: Path, ref: str, label: str, date: str, *, figures: bool) -> VersionView:
    text = source.read_text(encoding="utf-8")
    found = _figures(source.parent, text, source.suffix) if figures else None
    return VersionView(ref, label, date, text, source.suffix, found)


def from_snapshot(snap: Snapshot) -> VersionView:
    """A dossier snapshot, which holds its figures beside its text."""
    label = snap.label or snap.revision_label
    return _view(snap.source, snap.ref, label, snap.taken_at[:10], figures=True)


def from_draft(draft: Path) -> VersionView:
    """The live draft, as it is now."""
    return _view(draft, "current draft", "", "", figures=True)


def from_file(path: Path) -> VersionView:
    """Any file; its figures are read only if a `figures/` sits beside it."""
    return _view(path, path.name, "", "", figures=(path.parent / "figures").is_dir())
