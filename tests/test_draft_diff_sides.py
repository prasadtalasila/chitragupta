"""Tests for chitragupta/draft_diff/_sides.py: the two sides a redline compares.

The old side is rewritten in one way only: a citation whose key is not
citable now becomes `(citation withdrawn)`, so the unchanged gate passes
it. The weight is on the rewrite removing exactly that -- a key still
citable beside a withdrawn one stays cited (Review Focus 5), and text
with nothing withdrawn comes back byte for byte.
"""

import pytest

from chitragupta import citation_gate, ledger
from chitragupta.draft_diff._sides import WITHDRAWN, key_status, prepare, withdraw
from chitragupta.draft_diff._views import FigureForms, VersionView
from chitragupta.render_output import OutsideContentDir
from tests.conftest import add_citable, make_reference

_GONE = "sample_std_interop_2021"


def _citable(key):
    return key != _GONE


def _view(text, suffix=".md", figures=None, ref="001"):
    return VersionView(ref=ref, label="", date="", text=text, suffix=suffix, figures=figures)


def _keys(text, suffix=".md"):
    return [key for _, key in citation_gate.extract_citekeys_for(f"x{suffix}", text)]


def test_withdraw_whole_bracket_group_becomes_token():
    text = "Interfaces are agreed per project [@sample_std_interop_2021].\n"

    assert (
        withdraw(text, ".md", _citable)
        == "Interfaces are agreed per project (citation withdrawn).\n"
    )


def test_withdraw_mixed_group_drops_only_the_withdrawn_key():
    text = "Clocks drift [@sample_dt_sync_2023; @sample_std_interop_2021].\n"

    assert withdraw(text, ".md", _citable) == "Clocks drift [@sample_dt_sync_2023].\n"


def test_withdraw_mixed_group_keeps_the_kept_keys_own_prefix_and_locator():
    text = "As argued [see @sample_std_interop_2021, p. 3; also @sample_dt_sync_2023, sec. 2].\n"

    out = withdraw(text, ".md", _citable)

    assert out == "As argued [also @sample_dt_sync_2023, sec. 2].\n"


def test_withdraw_a_group_whose_keys_are_all_gone():
    text = "Gone [@sample_std_interop_2021; -@sample_std_interop_2021].\n"

    assert withdraw(text, ".md", _citable) == f"Gone {WITHDRAWN}.\n"


def test_withdraw_narrative_citation():
    text = "As @sample_std_interop_2021 shows, and @sample_dt_sync_2023 agrees.\n"

    out = withdraw(text, ".md", _citable)

    assert out == f"As {WITHDRAWN} shows, and @sample_dt_sync_2023 agrees.\n"


def test_withdraw_narrative_citation_in_link_text_keeps_the_link():
    text = "See [what @sample_std_interop_2021 said](https://example.org).\n"

    assert withdraw(text, ".md", _citable) == f"See [what {WITHDRAWN} said](https://example.org).\n"


def test_withdraw_reads_a_blank_line_as_closing_a_bracket():
    # pandoc closes an open bracket at a paragraph break, so the `]` after
    # it closes nothing and the citation before it is narrative.
    text = "A [stray\n\nB @sample_std_interop_2021].\n"

    assert withdraw(text, ".md", _citable) == f"A [stray\n\nB {WITHDRAWN}].\n"


def test_withdraw_an_item_citing_a_kept_and_a_withdrawn_key():
    text = "Both [@sample_dt_sync_2023 @sample_std_interop_2021].\n"

    out = withdraw(text, ".md", _citable)

    assert out == f"Both [@sample_dt_sync_2023 {WITHDRAWN}].\n"


def test_withdraw_reaches_a_citation_nested_in_another_edit():
    # The raw `\citep` and the group around it are two overlapping edits;
    # the second waits for the next pass.
    text = "X [\\citep{sample_std_interop_2021} @sample_std_interop_2021].\n"

    assert withdraw(text, ".md", _citable) == f"X {WITHDRAWN}.\n"


@pytest.mark.parametrize(
    "text",
    [
        "A [see \\citep{sample_dt_sync_2023}; @sample_std_interop_2021].\n",
        "A [\\citep{sample_dt_sync_2023} @sample_std_interop_2021; @sample_dt_overview_2024].\n",
    ],
)
def test_withdraw_keeps_a_citable_raw_latex_citation_inside_a_group(text):
    # The item's only kept key is a raw `\citep{}`: it is not
    # citation-free, so neither the item nor the group may go.
    out = withdraw(text, ".md", _citable)

    assert "sample_dt_sync_2023" in _keys(out)
    assert _GONE not in _keys(out)


def test_withdraw_drops_the_pandoc_item_beside_a_raw_latex_one():
    text = "A [see \\citep{sample_dt_sync_2023}; @sample_std_interop_2021].\n"

    assert withdraw(text, ".md", _citable) == "A [see \\citep{sample_dt_sync_2023}].\n"


def test_withdraw_tex_citep_whole_and_mixed():
    whole = "Agreed per project \\citep{sample_std_interop_2021}.\n"
    mixed = "Drift \\citep{sample_dt_sync_2023, sample_std_interop_2021}.\n"
    first = "Drift \\citep{sample_std_interop_2021, sample_dt_sync_2023}.\n"

    assert withdraw(whole, ".tex", _citable) == f"Agreed per project {WITHDRAWN}.\n"
    assert withdraw(mixed, ".tex", _citable) == "Drift \\citep{sample_dt_sync_2023}.\n"
    assert withdraw(first, ".tex", _citable) == "Drift \\citep{sample_dt_sync_2023}.\n"


def test_withdraw_tex_drops_the_optional_arguments_with_the_command():
    text = "Agreed \\citep[see][p.~3]{sample_std_interop_2021}.\n"

    assert withdraw(text, ".tex", _citable) == f"Agreed {WITHDRAWN}.\n"


def test_withdraw_a_multicite_drops_only_the_withdrawn_group():
    text = "Both \\textcites[p.~1]{sample_dt_sync_2023}[p.~2]{sample_std_interop_2021}.\n"

    assert withdraw(text, ".tex", _citable) == "Both \\textcites[p.~1]{sample_dt_sync_2023}.\n"


def test_withdraw_raw_latex_in_markdown_too():
    # The gate reads a raw `\citep{}` in a Markdown draft, so the rewrite
    # must too, or the old side is refused.
    text = "Raw \\citep{sample_std_interop_2021} and [@sample_dt_sync_2023].\n"

    assert withdraw(text, ".md", _citable) == f"Raw {WITHDRAWN} and [@sample_dt_sync_2023].\n"


def test_withdraw_leaves_code_alone():
    text = "Code `@sample_std_interop_2021` here, then [@sample_std_interop_2021].\n"

    out = withdraw(text, ".md", _citable)

    assert out == f"Code `@sample_std_interop_2021` here, then {WITHDRAWN}.\n"


def test_withdraw_leaves_citable_text_byte_identical():
    text = (
        "# T\n\nOne [@sample_dt_sync_2023;@sample_dt_overview_2024].\r\n"
        "Two @sample_dt_factory_2022 and \\citep{ sample_ml_anomaly_2023 ,sample_dt_sync_2023 }.\n"
    )

    assert withdraw(text, ".md", _citable) == text
    assert withdraw(text, ".tex", _citable) == text


@pytest.mark.parametrize("suffix", [".md", ".tex"])
def test_withdraw_leaves_no_withdrawn_key_for_the_gate(suffix):
    text = (
        "A [@sample_std_interop_2021]. B [x @sample_std_interop_2021; @sample_dt_sync_2023]. "
        "C @sample_std_interop_2021. D \\citet{sample_std_interop_2021,sample_dt_sync_2023}. "
        "E \\citep{sample_std_interop_2021}{sample_std_interop_2021}.\n"
    )

    out = withdraw(text, suffix, _citable)

    assert _GONE not in _keys(out, suffix)
    assert "sample_dt_sync_2023" in _keys(out, suffix)


def _figures():
    return {
        "figures/flow": FigureForms(
            tikz="\\begin{tikzpicture}\\end{tikzpicture}\n", ascii="A -> B\n"
        )
    }


def test_prepare_writes_both_sides_with_figures(isolated_config):
    work = isolated_config.REVIEW_DIR / "dt" / "survey.diff"
    old = _view("# Old\n\n<!-- figure: figures/flow -->\n", figures=_figures())
    new = _view(
        "# New\n",
        figures={
            "figures/flow": FigureForms(tikz="% new\n", ascii=None),
            "figures/gone": FigureForms(None, None),
        },
    )

    old_path, new_path = prepare(old, new, work, _citable, "survey")

    assert old_path == work / "old" / "survey.md"
    assert new_path == work / "new" / "survey.md"
    assert old_path.read_text(encoding="utf-8") == old.text
    assert new_path.read_text(encoding="utf-8") == "# New\n"
    assert (work / "old" / "figures" / "flow.tex").read_text() == _figures()["figures/flow"].tikz
    assert (work / "old" / "figures" / "flow.txt").read_text() == "A -> B\n"
    assert (work / "new" / "figures" / "flow.tex").read_text() == "% new\n"
    assert not (work / "new" / "figures" / "flow.txt").exists()
    assert not (work / "new" / "figures" / "gone.tex").exists()


def test_prepare_starts_each_side_afresh(isolated_config):
    # A figure an earlier run wrote must not survive into a side that no
    # longer has it, or the redline would show a figure that is gone.
    work = isolated_config.REVIEW_DIR / "survey.diff"
    stale = work / "old" / "figures" / "stale.tex"
    stale.parent.mkdir(parents=True)
    stale.write_text("old run\n")

    prepare(_view("# A\n"), _view("# B\n", figures=None), work, _citable, "survey")

    assert not stale.exists()


def test_prepare_keeps_a_tex_suffix(isolated_config):
    work = isolated_config.REVIEW_DIR / "thesis.diff"

    old_path, new_path = prepare(
        _view("\\section{A}\n", ".tex"), _view("\\section{B}\n", ".tex"), work, _citable, "ch2"
    )

    assert (old_path.name, new_path.name) == ("ch2.tex", "ch2.tex")


def test_prepare_applies_withdraw_to_old_side_only(isolated_config):
    work = isolated_config.REVIEW_DIR / "dt" / "survey.diff"
    text = "Claim [@sample_std_interop_2021].\n"

    old_path, new_path = prepare(_view(text), _view(text), work, _citable, "survey")

    assert old_path.read_text() == f"Claim {WITHDRAWN}.\n"
    # The new side is the draft as it stands: if it cites a withdrawn
    # key, the gate refuses it, as it would refuse the draft itself.
    assert new_path.read_text() == text


def test_prepare_refuses_a_work_dir_outside_content(isolated_config, tmp_path):
    with pytest.raises(OutsideContentDir):
        prepare(_view("# A\n"), _view("# B\n"), tmp_path / "elsewhere", _citable, "survey")


def test_prepare_never_writes_a_figure_outside_its_side(isolated_config):
    work = isolated_config.REVIEW_DIR / "survey.diff"
    old = _view("# A\n", figures={"../../escape": FigureForms(tikz="x\n", ascii=None)})

    prepare(old, _view("# B\n"), work, _citable, "survey")

    assert not (isolated_config.REVIEW_DIR / "escape.tex").exists()


def test_prepare_refuses_a_stem_that_is_not_a_file_name(isolated_config):
    work = isolated_config.REVIEW_DIR / "survey.diff"

    with pytest.raises(ValueError, match="not a file name"):
        prepare(_view("# A\n"), _view("# B\n"), work, _citable, "../../survey")


def test_key_status_reads_the_ledger(ledger_con):
    add_citable(ledger_con, "sample_dt_sync_2023")
    ledger.upsert_reference(ledger_con, make_reference(citekey="sample_dt_overview_2024"))

    status = key_status(ledger_con)

    assert status("sample_dt_sync_2023") == "still citable"
    assert status("sample_dt_overview_2024") == "no longer parsed"
    assert status("sample_std_interop_2021") == "no longer in the corpus"
