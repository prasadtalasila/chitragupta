"""Tests for chitragupta/draft_diff's comparison core: views, sections, compare.

`compare()` is pure, so most tests build two `VersionView`s from short
inline texts and read the report. The weight is on the three places a
diff can misreport without anyone noticing: text above the first
heading, two sections sharing a title, and a figure named but not drawn.
"""

from pathlib import Path

from chitragupta.dossier._versions import Snapshot
from chitragupta.draft_diff import _sections
from chitragupta.draft_diff._compare import compare
from chitragupta.draft_diff._views import FigureForms, VersionView, from_draft, from_file
from chitragupta.draft_diff._views import from_snapshot

_BASE = """# A survey

Opening words.

## 1. Background

Digital twins mirror a physical asset [@sample_dt_overview_2024].

## 2. Methods

We synchronise the twin with its plant at a fixed rate.

## 3. Results

The estimator converges quickly [@sample_dt_sync_2023].

## 4. Discussion

Interoperability remains open [@sample_std_interop_2021].
"""


def _view(text, suffix=".md", figures=None, ref="001"):
    return VersionView(ref=ref, label="", date="", text=text, suffix=suffix, figures=figures)


def _status(key):
    return "still citable"


def _kinds(report):
    return {change.title: change.kind for change in report.sections}


def _swap(text, old, new):
    assert old in text
    return text.replace(old, new)


def test_reworded_section_is_changed_with_word_count():
    new = _swap(_BASE, "with its plant at a", "against the plant's")
    report = compare(_view(_BASE), _view(new), _status)
    change = next(c for c in report.sections if c.title == "2. Methods")
    assert change.kind == "changed"
    assert change.words_changed == 8
    assert report.words_changed == 8
    assert report.unlogged == ["2. Methods"]
    assert report.has_changes


def test_identical_drafts_have_no_changes():
    report = compare(_view(_BASE, figures={}), _view(_BASE, figures={}), _status)
    assert set(_kinds(report).values()) == {"unchanged"}
    assert report.words_changed == 0
    assert not report.has_changes
    assert report.citekeys_added == report.citekeys_dropped == []
    assert report.figures == []


def test_added_and_removed_sections():
    new = _swap(_BASE, "## 2. Methods\n", "## 2. Approach\n\nNew text here.\n\n## 2b. Methods\n")
    new = new.split("## 4. Discussion")[0]
    report = compare(_view(_BASE), _view(new), _status)
    kinds = _kinds(report)
    assert kinds["2. Approach"] == "added"
    assert kinds["4. Discussion"] == "removed"
    assert [c.title for c in report.sections][-1] == "4. Discussion"
    added = next(c for c in report.sections if c.title == "2. Approach")
    assert added.words_changed == 3


def test_moved_section_is_moved_not_changed():
    head, rest = _BASE.split("## 3. Results")
    results, discussion = rest.split("## 4. Discussion")
    new = f"{head}## 4. Discussion{discussion}\n## 3. Results{results}"
    report = compare(_view(_BASE), _view(new), _status)
    kinds = _kinds(report)
    assert kinds["4. Discussion"] == "moved"
    assert kinds["3. Results"] == "unchanged"
    assert kinds["1. Background"] == "unchanged"
    assert [c.title for c in report.sections][:4] == [
        "(before the first heading)",
        "1. Background",
        "2. Methods",
        "4. Discussion",
    ]
    assert report.unlogged == ["4. Discussion"]


def test_moved_and_edited_section_is_changed():
    text = "## A\n\none\n\n## B\n\ntwo\n\n## C\n\nthree\n"
    moved = "## A\n\none\n\n## C\n\nthree four\n\n## B\n\ntwo\n"
    report = compare(_view(text), _view(moved), _status)
    assert _kinds(report) == {"A": "unchanged", "C": "changed", "B": "unchanged"}


def test_renamed_section_is_removed_plus_added():
    new = _swap(_BASE, "## 3. Results", "## 3. Findings")
    kinds = _kinds(compare(_view(_BASE), _view(new), _status))
    assert kinds["3. Results"] == "removed"
    assert kinds["3. Findings"] == "added"


def test_text_before_first_heading_is_a_section():
    new = _swap(_BASE, "Opening words.", "Different opening words.")
    kinds = _kinds(compare(_view(_BASE), _view(new), _status))
    assert kinds["(before the first heading)"] == "changed"
    # The `#` title line is part of that leading section, not a heading.
    split = _sections.split(_BASE, ".md")
    assert split[0].title == "(before the first heading)"
    assert "# A survey" in split[0].body


def test_blank_leading_text_is_no_section_and_fences_hide_headings():
    text = "\n## A\n\n```\n## not a heading\n```\n"
    split = _sections.split(text, ".md")
    assert [s.title for s in split] == ["A"]
    assert "## not a heading" in split[0].body
    assert _sections.split("no headings at all\n", ".md")[0].body == "no headings at all"


def test_repeated_titles_pair_by_occurrence():
    old = "## Part\n\nalpha\n\n## Notes\n\none\n\n## Part\n\nbeta\n\n## Notes\n\ntwo\n"
    new = old.replace("two", "two three")
    split = _sections.split(old, ".md")
    assert [(s.title, s.occurrence) for s in split] == [
        ("Part", 0),
        ("Notes", 0),
        ("Part", 1),
        ("Notes", 1),
    ]
    report = compare(_view(old), _view(new), _status)
    assert [(c.title, c.kind) for c in report.sections] == [
        ("Part", "unchanged"),
        ("Notes", "unchanged"),
        ("Part", "unchanged"),
        ("Notes", "changed"),
    ]


def test_tex_sections_are_split_like_markdown():
    tex = (
        "Preamble words.\n\\chapter{Intro}\nA.\n"
        "\\section*{Scope}\nB \\citep{sample_dt_sync_2023}.\n"
        "\\subsection{Detail}\nC.\n\\subsubsection{Deep}\nD.\n"
    )
    split = _sections.split(tex, ".tex")
    assert [s.title for s in split] == ["(before the first heading)", "Intro", "Scope", "Detail"]
    assert "\\subsubsection{Deep}" in split[-1].body
    new = tex.replace("\\citep{sample_dt_sync_2023}", "\\citep{sample_ml_anomaly_2023}")
    report = compare(_view(tex, ".tex"), _view(new, ".tex"), _status)
    assert _kinds(report)["Scope"] == "changed"
    assert report.citekeys_added == [("sample_ml_anomaly_2023", "Scope")]
    assert report.citekeys_dropped == [("sample_dt_sync_2023", "still citable")]


def test_added_citekey_names_its_section():
    new = _swap(_BASE, "fixed rate.", "fixed rate [@sample_dt_factory_2022].")
    new = _swap(new, "Opening words.", "Opening words [@sample_ml_anomaly_2023].")
    report = compare(_view(_BASE), _view(new), _status)
    assert report.citekeys_added == [
        ("sample_ml_anomaly_2023", "(before the first heading)"),
        ("sample_dt_factory_2022", "2. Methods"),
    ]
    assert report.citekeys_dropped == []


def test_dropped_citekey_carries_its_status():
    new = _swap(_BASE, " [@sample_std_interop_2021]", "")
    new = _swap(new, " [@sample_dt_sync_2023]", "")
    statuses = {"sample_std_interop_2021": "no longer in the corpus"}
    report = compare(_view(_BASE), _view(new), lambda key: statuses.get(key, "still citable"))
    assert report.citekeys_dropped == [
        ("sample_dt_sync_2023", "still citable"),
        ("sample_std_interop_2021", "no longer in the corpus"),
    ]
    assert report.has_changes


_FIG_MD = "## A\n\n<!-- figure: figures/loop -->\n\n<!-- figure: figures/arch -->\n"


def _forms(tikz, ascii_):
    return FigureForms(tikz=tikz, ascii=ascii_)


def test_figure_redrawn_both_forms_and_one_form_only():
    third = _FIG_MD + "\n<!-- figure: figures/flow -->\n"
    old = {
        "figures/loop": _forms("t1", "a1"),
        "figures/arch": _forms("t1", "a1"),
        "figures/flow": _forms("t1", "a1"),
    }
    new = {
        "figures/loop": _forms("t2", "a2"),
        "figures/arch": _forms("t2", "a1"),
        "figures/flow": _forms("t1", "a2"),
    }
    report = compare(_view(third, figures=old), _view(third, figures=new), _status)
    assert [(f.name, f.kind, f.forms) for f in report.figures] == [
        ("figures/loop", "redrawn", "both"),
        ("figures/arch", "redrawn", "tikz only"),
        ("figures/flow", "redrawn", "ascii only"),
    ]
    assert report.has_changes


def test_figure_added_and_removed():
    old_text = "## A\n\n<!-- figure: figures/loop -->\n"
    new_text = "## A\n\n<!-- figure: figures/arch -->\n"
    report = compare(
        _view(old_text, figures={"figures/loop": _forms("t", "a")}),
        _view(new_text, figures={"figures/arch": _forms("t", None)}),
        _status,
    )
    assert [(f.name, f.kind) for f in report.figures] == [
        ("figures/loop", "removed"),
        ("figures/arch", "added"),
    ]


def test_figure_missing_on_one_side():
    same = {"figures/arch": _forms("t", "a")}
    old = {"figures/loop": _forms(None, None), **same}
    new = {"figures/loop": _forms("t", "a"), **same}
    report = compare(_view(_FIG_MD, figures=old), _view(_FIG_MD, figures=new), _status)
    assert [(f.name, f.kind, f.side) for f in report.figures] == [
        ("figures/loop", "missing", "old")
    ]
    report = compare(_view(_FIG_MD, figures=new), _view(_FIG_MD, figures=old), _status)
    assert [(f.name, f.kind, f.side) for f in report.figures] == [
        ("figures/loop", "missing", "new")
    ]


def test_unknown_baseline_figures_gives_none():
    figures = {"figures/loop": _forms("t", "a")}
    report = compare(_view(_FIG_MD), _view(_FIG_MD, figures=figures), _status)
    assert report.figures is None
    assert compare(_view(_FIG_MD, figures=figures), _view(_FIG_MD), _status).figures is None


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_from_draft_reads_text_and_both_figure_forms(tmp_path):
    draft = _write(tmp_path / "survey.md", _FIG_MD)
    _write(tmp_path / "figures" / "loop.tex", "tikz")
    _write(tmp_path / "figures" / "loop.txt", "ascii")
    view = from_draft(draft)
    assert (view.ref, view.label, view.date, view.suffix) == ("current draft", "", "", ".md")
    assert view.text == _FIG_MD
    assert view.figures == {
        "figures/loop": FigureForms(tikz="tikz", ascii="ascii"),
        "figures/arch": FigureForms(tikz=None, ascii=None),
    }


def test_from_file_reads_figures_only_when_a_figures_dir_is_beside_it(tmp_path):
    bare = from_file(_write(tmp_path / "old.md", _FIG_MD))
    assert (bare.ref, bare.date, bare.figures) == ("old.md", "", None)
    _write(tmp_path / "figures" / "arch.txt", "ascii")
    beside = from_file(tmp_path / "old.md")
    assert beside.figures["figures/arch"] == FigureForms(tikz=None, ascii="ascii")


def test_from_snapshot_takes_label_date_and_figures_from_the_version(tmp_path):
    version = tmp_path / "002"
    _write(version / "chapter.tex", "\\section{A}\nx\n")
    snap = Snapshot(
        number=2,
        label="",
        taken_at="2026-11-12T10:00:00",
        trigger="mark-revision",
        revision_label="tighten section 2",
        fingerprint="f",
        draft_name="chapter.tex",
        path=version,
    )
    view = from_snapshot(snap)
    assert (view.ref, view.label, view.date, view.suffix) == (
        "002",
        "tighten section 2",
        "2026-11-12",
        ".tex",
    )
    assert view.figures == {}
    named = Snapshot(**{**snap.__dict__, "label": "sent to supervisor"})
    assert from_snapshot(named).label == "sent to supervisor"


def test_citekeys_are_placed_by_the_gates_line_count():
    # U+2028 and a form feed are line breaks to `str.splitlines()` but not
    # to the gate, which counts "\n" alone; both must number lines alike.
    new = "Intro\u2028x\x0cy\n## A\nCited [@sample_dt_sync_2023].\n## B\nz\n"
    report = compare(_view("## A\n\nText.\n"), _view(new), _status)
    assert report.citekeys_added == [("sample_dt_sync_2023", "A")]
    split = _sections.split(new, ".md")
    assert [s.title for s in split] == ["(before the first heading)", "A", "B"]
    assert split[0].body == "Intro\u2028x\x0cy"


def test_a_citekey_under_blank_leading_lines_is_placed():
    report = compare(_view("x\n"), _view("  \n## A\n[@sample_dt_sync_2023]\n"), _status)
    assert report.citekeys_added == [("sample_dt_sync_2023", "A")]
    assert _sections.title_at([], 1) == "(before the first heading)"


def test_a_figure_undrawn_on_both_sides_is_no_change():
    figures = {"figures/loop": _forms(None, None), "figures/arch": _forms("t", "a")}
    report = compare(_view(_FIG_MD, figures=figures), _view(_FIG_MD, figures=figures), _status)
    assert report.figures == []
    assert not report.has_changes


# `draft references` rewrites this section on every pass; its entries are
# generated, not prose a reviser wrote.
_REFS = "\n## {heading}\n\n" "[@sample_dt_overview_2024] A. Author, \"Twins,\" 2024.\n\n{extra}"


def _with_refs(text, heading="References", extra=""):
    return text + _REFS.format(heading=heading, extra=extra)


def test_a_regenerated_references_section_is_reported_without_words():
    old = _with_refs(_BASE)
    new = _with_refs(
        _swap(_BASE, "quickly [@sample_dt_sync_2023].", "quickly [@sample_dt_sync_2023]. Done."),
        extra="[@sample_dt_sync_2023] B. Author, \"Clocks,\" 2023, pp. 1-40.\n",
    )
    report = compare(_view(old), _view(new), _status)
    refs = next(c for c in report.sections if c.title == "References")
    assert (refs.kind, refs.words_changed) == ("regenerated", 0)
    assert report.words_changed == 1
    assert report.unlogged == ["3. Results"]


def test_a_numbered_references_section_first_written_is_regenerated():
    report = compare(_view(_BASE), _view(_with_refs(_BASE, "5. References")), _status)
    assert _kinds(report)["5. References"] == "regenerated"
    assert report.words_changed == 0
    assert report.unlogged == []
    assert report.has_changes


def test_a_dropped_references_section_is_regenerated():
    report = compare(_view(_with_refs(_BASE)), _view(_BASE), _status)
    assert _kinds(report)["References"] == "regenerated"
    assert report.words_changed == 0


def test_an_unchanged_references_section_stays_unchanged():
    report = compare(_view(_with_refs(_BASE)), _view(_with_refs(_BASE)), _status)
    assert _kinds(report)["References"] == "unchanged"


def test_only_the_bibliography_heading_is_generated():
    """The heading rule render() drops the section by, anchored: a
    section that only starts with the word is prose."""
    old = _with_refs(_BASE, "References and notes")
    new = _with_refs(_BASE, "References and notes", extra="A note.\n")
    report = compare(_view(old), _view(new), _status)
    assert _kinds(report)["References and notes"] == "changed"
    assert report.unlogged == ["References and notes"]
