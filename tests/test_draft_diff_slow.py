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
    s3 = re.search(r"## 3\. Using the state stream.*?(?=## 4\.)", text, re.S).group(0)
    s4 = re.search(r"## 4\. Integrating with everything else.*?(?=## 5a\.)", text, re.S).group(0)
    return text.replace(s3 + s4, s4 + s3)


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


def _inside_del(tex: str, phrase: str) -> bool:
    """Whether `phrase` sits inside the argument of some `\\DIFdel{...}`."""
    for match in re.finditer(r"\\DIFdel\{", tex):
        depth, at = 1, match.end()
        while depth and at < len(tex):
            depth += {"{": 1, "}": -1}.get(tex[at], 0)
            at += 1
        if phrase in tex[match.end() : at]:
            return True
    return False


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
    # The one inserted citation is marked, and only it. latexdiff boxes a
    # whole added command: `\DIFadd{\mbox{%DIFAUXCMD` and a line break.
    added = re.findall(
        r"\\DIFadd\{\s*(?:\\mbox\{%DIFAUXCMD\s*)?\\citep\{\s*sample_ml_anomaly_2023\s*\}", tex
    )
    assert len(added) == 1, tex
    # A citation in an unchanged paragraph is the same `\citep{key}` on
    # both sides, so the renumbering a resolved render would show is gone.
    for line in tex.splitlines():
        if "\\citep{sample_dt_sync_2023}" in line:
            assert "\\DIF" not in line, line
    assert "figure redrawn since 001" in tex
    assert _inside_del(tex, "(citation withdrawn)"), tex
    report = (review / "survey.diff.md").read_text(encoding="utf-8")
    assert re.search(rf"{_WITHDRAWN}.*no longer in the corpus", report), report
