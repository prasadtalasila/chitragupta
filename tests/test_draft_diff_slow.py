"""The redline end to end: the spike scenario of plans/draft-diff.md,
replayed on the sample project with the real toolchain.

pandoc renders both sides with deferred citations, latexdiff marks the
difference, LuaLaTeX and bibtexu compile it. What is pinned is what the
spike found could go wrong: a new citation renumbering every later one,
a redrawn figure leaving no mark, and a withdrawn key's token losing its
brackets. Everything else about the redline is tested with the toolchain
faked in tests/test_draft_diff_redline.py and tests/test_draft_diff_cli.py.
"""

import re
import shutil
from pathlib import Path

import pytest

from chitragupta import config, draft, ledger, programs
from chitragupta.dossier import _versions
from tests.conftest import add_citable, content_draft

_TOOLS = ("latexdiff", "lualatex", "bibtexu", "pandoc")

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        not all(programs.resolve_program(name) for name in _TOOLS),
        reason="the redline needs latexdiff, lualatex, bibtexu and pandoc",
    ),
]

_SAMPLE = Path(__file__).resolve().parents[1] / "docs" / "examples" / "sample-project"
_KEYS = (
    "sample_dt_overview_2024",
    "sample_dt_sync_2023",
    "sample_dt_factory_2022",
    "sample_ml_anomaly_2023",
    "sample_std_interop_2021",
)
_WITHDRAWN = "sample_std_interop_2021"

# The spike's extra section: an equation, a table and a captioned figure,
# so the math, table-cell and figure edits below each have something to touch.
_WORKED = r"""## 5a. A worked estimate

The twin's state estimate is corrected by the measurement in proportion to the gain:

$$
\hat{x}_k = \hat{x}_{k-1} + K_k\,(z_k - \hat{x}_{k-1}), \qquad K_k = \frac{P_k}{P_k + R}
$$

| Strategy | Volume | Worst staleness |
|---|---|---|
| Periodic pull | 100 % | 1.0 s |
| Threshold push | 31 % | 9.4 s |
| Event-driven | 29 % | 1.8 s |

<!-- figure: figures/estimator-loop -->
The estimator loop that keeps a twin's state honest.

"""

_FIGURE_TEX = "\\begin{tikzpicture}\\node[draw] (a) {Real system};\\end{tikzpicture}\n"
_FIGURE_TXT = "  +-------------+\n  | Real system |\n  +-------------+\n"

# (old, new) pairs applied in order to the snapshot's text. Every
# citation of the withdrawn key goes: the gate refuses the new side if
# it still cites a key the ledger no longer holds.
_EDITS = (
    # A reworded phrase.
    (
        "applied to systems with very different\nlevels of ambition",
        "applied to systems of widely differing\nambition",
    ),
    # A new citation early on, which under citeproc renumbers every later one.
    ("only through manual steps;", "only through manual steps [@sample_ml_anomaly_2023];"),
    # A dropped sentence, carrying one of the withdrawn key's citations.
    (
        "The practical instrument for the\nthird is a shared asset-model registry with named "
        "owners: sites that\nmaintained one integrated a new asset in a median of six days, "
        "against\nseven weeks where semantics were negotiated per project\n"
        "[@sample_std_interop_2021]. ",
        "",
    ),
    # The withdrawn key's other citations, dropped where they stand.
    ("standards [@sample_std_interop_2021].", "standards."),
    ("but never repurposed\n[@sample_std_interop_2021].", "but never repurposed."),
    ("owned semantics\n[@sample_std_interop_2021] are", "owned semantics are"),
    # An equation, a table cell, a multi-citation.
    (r"\frac{P_k}{P_k + R}", r"\frac{P_k}{P_k + R_k}"),
    ("| Threshold push | 31 % | 9.4 s |", "| Threshold push | 31 % | 11.2 s |"),
    (
        "[@sample_dt_overview_2024], yet no paper",
        "[@sample_dt_overview_2024; @sample_dt_factory_2022], yet no paper",
    ),
)


def _apply(text: str) -> str:
    for old, new in _EDITS:
        assert old in text, old
        text = text.replace(old, new)
    # Section 4 moved above section 3.
    s3 = re.search(r"## 3\. Using the state stream.*?(?=## 4\.)", text, re.S)
    s4 = re.search(r"## 4\. Integrating with everything else.*?(?=## 5a\.)", text, re.S)
    assert s3 and s4, "the sample survey no longer has sections 3 and 4 in order"
    return text.replace(s3.group(0) + s4.group(0), s4.group(0) + s3.group(0))


def _survey() -> Path:
    shutil.copy(_SAMPLE / "papers" / "bibliography.bib", config.BIB_FILE_PATH)
    path = content_draft(config, "drafts/dt-overview/survey.md")
    sample = (_SAMPLE / "content" / "drafts" / "dt-overview" / "survey.md").read_text("utf-8")
    path.write_text(sample.replace("## 5. Gaps", _WORKED + "## 5. Gaps"), encoding="utf-8")
    figures = path.parent / "figures"
    figures.mkdir()
    (figures / "estimator-loop.tex").write_text(_FIGURE_TEX, encoding="utf-8")
    (figures / "estimator-loop.txt").write_text(_FIGURE_TXT, encoding="utf-8")
    return path


def _marked(tex: str) -> "list[tuple[str, int, int]]":
    """(macro, start, end) of every `\\DIFadd{...}` and `\\DIFdel{...}`
    argument, braces matched and `\\{` `\\}` skipped."""
    spans = []
    for match in re.finditer(r"\\(DIFadd|DIFdel)(?:FL)?\{", tex):
        depth, at = 1, match.end()
        while depth and at < len(tex):
            if tex[at] == "\\":
                at += 2
                continue
            depth += {"{": 1, "}": -1}.get(tex[at], 0)
            at += 1
        spans.append((match.group(1), match.end(), at))
    return spans


def _inside(tex: str, macro: str, phrase: str) -> bool:
    """Whether `phrase` sits inside the argument of some `\\<macro>{...}`."""
    return any(phrase in tex[start:end] for name, start, end in _marked(tex) if name == macro)


def _cites(tex: str) -> "list[tuple[str | None, str]]":
    """(enclosing DIF macro or None, keys) for every `\\citep{keys}`."""
    spans = _marked(tex)
    return [
        (next((name for name, start, end in spans if start <= m.start() < end), None), m.group(1))
        for m in re.finditer(r"\\citep\{([^}]*)\}", tex)
    ]


def test_spike_scenario_redline(isolated_config, ledger_con, capsys):
    for key in _KEYS:
        add_citable(ledger_con, key)
    ledger_con.commit()
    path = _survey()
    assert _versions.take(path, trigger="mark-revision") is not None

    # The paper leaves the corpus after the snapshot that cites it.
    ledger.prune_missing(ledger_con, set(_KEYS) - {_WITHDRAWN})
    path.write_text(_apply(path.read_text(encoding="utf-8")), encoding="utf-8")
    redrawn = path.parent / "figures" / "estimator-loop.tex"
    redrawn.write_text(_FIGURE_TEX.replace("Real system", "Physical asset"), encoding="utf-8")

    assert draft.main(["diff", str(path), "--format", "pdf"]) == 0, capsys.readouterr().err

    review = config.REVIEW_DIR / "dt-overview"
    assert (review / "survey.diff.pdf").is_file()
    tex = (review / "survey.diff.tex").read_text(encoding="utf-8")
    # Only the citations the edits touched are marked: the one inserted
    # in section 1, and the single citation that became a multi-citation
    # in section 5. Every other `\citep{key}` is the same on both sides,
    # so the renumbering a resolved render would show is gone -- including
    # the moved section 3's, which latexdiff leaves in place.
    cites = _cites(tex)
    assert sorted((m, k) for m, k in cites if m) == [
        ("DIFadd", "sample_dt_overview_2024, sample_dt_factory_2022"),
        ("DIFadd", "sample_ml_anomaly_2023"),
        ("DIFdel", "sample_dt_overview_2024"),
    ], cites
    # Not vacuous: the unchanged section 2 and the conclusion cite it four times.
    assert [m for m, k in cites if k == "sample_dt_sync_2023"] == [None] * 4, cites
    assert "figure redrawn since 001" in tex
    assert _inside(tex, "DIFdel", "(citation withdrawn)"), tex
    report = (review / "survey.diff.md").read_text(encoding="utf-8")
    assert re.search(rf"{_WITHDRAWN}.*no longer in the corpus", report), report
