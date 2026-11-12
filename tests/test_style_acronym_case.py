"""`chitragupta.AcronymCase`: an expansion written before "(ACRO)" in a
different case from the vocabulary (#1187)."""

from pathlib import Path

import pytest

from chitragupta import config, style_acronym_case, style_rules


def _vocab(monkeypatch, tmp_path: Path, **entries: str) -> None:
    path = tmp_path / "acronyms.toml"
    path.write_text("".join(f'{k} = "{v}"\n' for k, v in entries.items()), encoding="utf-8")
    monkeypatch.setattr(config, "ACRONYMS_PATH", path)


def _run(tmp_path: Path, text: str, name: str = "d.md") -> list[dict]:
    draft = tmp_path / name
    draft.write_text(text, encoding="utf-8")
    return style_acronym_case.findings(draft)


SCADA = "supervisory control and data acquisition"


def test_wrong_case_mid_sentence_is_reported(monkeypatch, tmp_path):
    _vocab(monkeypatch, tmp_path, SCADA=SCADA)
    found = _run(tmp_path, "Intro.\n\nWe use Supervisory Control and Data Acquisition (SCADA).\n")
    assert len(found) == 1
    assert found[0]["repair"] == "review"
    assert found[0]["rule"] == "chitragupta.AcronymCase"
    assert found[0]["line"] == 3
    assert found[0]["match"] == "Supervisory Control and Data Acquisition"
    assert SCADA in found[0]["message"]


def test_matching_case_is_clean(monkeypatch, tmp_path):
    _vocab(monkeypatch, tmp_path, SCADA=SCADA)
    assert _run(tmp_path, f"We use {SCADA} (SCADA).\n") == []


def test_sentence_start_capital_is_tolerated(monkeypatch, tmp_path):
    _vocab(monkeypatch, tmp_path, SCADA=SCADA)
    cap = "Supervisory control and data acquisition (SCADA)"
    assert _run(tmp_path, f"{cap} is old.\n") == []
    assert _run(tmp_path, f"It is. {cap} is old.\n") == []
    assert _run(tmp_path, f"- {cap} is old.\n") == []


def test_heading_capital_is_tolerated(monkeypatch, tmp_path):
    _vocab(monkeypatch, tmp_path, SCADA=SCADA)
    assert _run(tmp_path, "## Supervisory control and data acquisition (SCADA)\n") == []
    tex = "\\section{Supervisory control and data acquisition (SCADA)}\n"
    assert _run(tmp_path, tex, "d.tex") == []


def test_mid_sentence_capital_is_not_a_sentence_start(monkeypatch, tmp_path):
    _vocab(monkeypatch, tmp_path, SCADA=SCADA)
    found = _run(tmp_path, "We use Supervisory control and data acquisition (SCADA).\n")
    assert len(found) == 1


def test_proper_name_written_lower_case_is_reported(monkeypatch, tmp_path):
    _vocab(monkeypatch, tmp_path, UML="Unified Modeling Language")
    found = _run(tmp_path, "See the unified modeling language (UML).\n")
    assert [f["match"] for f in found] == ["unified modeling language"]


def test_references_section_is_ignored(monkeypatch, tmp_path):
    _vocab(monkeypatch, tmp_path, UML="Unified Modeling Language")
    text = "Body.\n\n## References\n\nthe unified modeling language (UML).\n"
    assert _run(tmp_path, text) == []


def test_code_is_ignored_and_lines_stay_right(monkeypatch, tmp_path):
    _vocab(monkeypatch, tmp_path, UML="Unified Modeling Language")
    text = "```\nthe unified modeling language (UML)\n```\n\nuse unified modeling language (UML).\n"
    found = _run(tmp_path, text)
    assert [f["line"] for f in found] == [5]


def test_one_finding_per_distinct_phrase_at_first_line(monkeypatch, tmp_path):
    _vocab(monkeypatch, tmp_path, UML="Unified Modeling Language")
    text = (
        "a unified modeling language (UML)\nb unified modeling language (UML)\n"
        "c UNIFIED MODELING LANGUAGE (UML)\n"
    )
    found = _run(tmp_path, text)
    assert [(f["match"], f["line"]) for f in found] == [
        ("unified modeling language", 1),
        ("UNIFIED MODELING LANGUAGE", 3),
    ]


def test_wrapped_expansion_is_found(monkeypatch, tmp_path):
    _vocab(monkeypatch, tmp_path, UML="Unified Modeling Language")
    found = _run(tmp_path, "see unified modeling\nlanguage (UML).\n")
    assert [f["match"] for f in found] == ["unified modeling language"]


def test_metacharacters_in_an_expansion(monkeypatch, tmp_path):
    _vocab(monkeypatch, tmp_path, MAPE="Monitor, Analyse, Plan, Execute")
    assert _run(tmp_path, "the Monitor, Analyse, Plan, Execute (MAPE) loop\n") == []
    found = _run(tmp_path, "the monitor, analyse, plan, execute (MAPE) loop\n")
    assert len(found) == 1


def test_empty_vocabulary_or_no_acronym(monkeypatch, tmp_path):
    _vocab(monkeypatch, tmp_path)
    assert _run(tmp_path, "Plain text.\n") == []


def test_registered_in_python_checks():
    assert style_acronym_case.findings in style_rules.PYTHON_CHECKS


@pytest.mark.parametrize("text", ["no match here\n"])
def test_unrelated_text_is_clean(monkeypatch, tmp_path, text):
    _vocab(monkeypatch, tmp_path, SCADA=SCADA)
    assert _run(tmp_path, text) == []


def test_tolerated_first_use_does_not_hide_a_later_wrong_one(monkeypatch, tmp_path):
    _vocab(monkeypatch, tmp_path, SCADA=SCADA)
    cap = "Supervisory control and data acquisition (SCADA)"
    found = _run(tmp_path, f"{cap} is old.\n\nWe use {cap}.\n")
    assert [f["line"] for f in found] == [3]
