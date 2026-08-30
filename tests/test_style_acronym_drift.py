"""findings() -- the one `python -m chitragupta.draft style` finding not
delegated to Vale: a draft's recorded glossary checked against the
current acronym vocabulary. See chitragupta/style_acronym_drift.py and the
measurement behind it in chitragupta/acronyms.py.
"""

from chitragupta import acronyms, dossier, style_acronym_drift
from tests.conftest import content_draft


def _write_glossary(draft, body):
    scope_dir = dossier.dossier_dir(draft)
    scope_dir.mkdir(parents=True, exist_ok=True)
    (scope_dir / dossier.SCOPE_MD).write_text(
        f"# Scope\n\n- genre: survey\n- created: 2026-08-14\n\n## Glossary\n\n{body}\n",
        encoding="utf-8",
    )


def test_no_findings_without_a_dossier(isolated_config):
    draft = content_draft(isolated_config, "drafts/topic/survey.md")
    assert style_acronym_drift.findings(draft) == []


def test_no_findings_for_a_draft_outside_content_drafts(tmp_path):
    """dossier.dossier_dir() raises DossierError for a draft that isn't
    under content/drafts/ (test fixtures, an ad-hoc file) -- the same
    case style_check.language_of() already tolerates."""
    draft = tmp_path / "loose.md"
    draft.write_text("prose\n", encoding="utf-8")
    assert style_acronym_drift.findings(draft) == []


def test_no_findings_when_the_glossary_agrees_with_the_vocabulary(isolated_config, monkeypatch):
    monkeypatch.setattr(acronyms, "load_vocabulary", lambda: {"DT": "Digital twin"})
    draft = content_draft(isolated_config, "drafts/topic/survey.md")
    _write_glossary(draft, "- **Digital twin (DT)** -- was, in Chapter 1, a model.")
    assert style_acronym_drift.findings(draft) == []


def test_one_finding_when_the_glossary_has_drifted(isolated_config, monkeypatch):
    monkeypatch.setattr(acronyms, "load_vocabulary", lambda: {"DT": "Digital Twin System"})
    draft = content_draft(isolated_config, "drafts/topic/survey.md")
    _write_glossary(draft, "- **Digital twin (DT)** -- was, in Chapter 1, a model.")

    found = style_acronym_drift.findings(draft)

    assert len(found) == 1
    assert found[0]["rule"] == "chitragupta.AcronymDrift"
    assert found[0]["match"] == "DT"
    assert found[0]["line"] == 0
    assert found[0]["severity"] == "suggestion"
    assert found[0]["count"] == 1
    assert "Digital twin" in found[0]["message"]
    assert "Digital Twin System" in found[0]["message"]


def test_findings_are_sorted_by_term(isolated_config, monkeypatch):
    monkeypatch.setattr(
        acronyms,
        "load_vocabulary",
        lambda: {"DT": "Digital Twin System", "DS": "Digital Shadow System"},
    )
    draft = content_draft(isolated_config, "drafts/topic/survey.md")
    _write_glossary(
        draft,
        "- **Digital twin (DT)** -- a model.\n- **Digital shadow (DS)** -- a copy.",
    )

    found = style_acronym_drift.findings(draft)

    assert [f["match"] for f in found] == ["DS", "DT"]
