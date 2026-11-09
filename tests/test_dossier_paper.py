"""The `research-paper` genre and the `paper.md` its dossier is given.

See plans/1179-research-paper-genre.md: a research paper's paper-level inputs
(the software, the venue, the message, the contributions) have no home
in `outline.md`, whose parser takes only `brief:`/`claim:`/`queries:`
per section, so `init` writes them a file of their own.
"""

import pytest

from chitragupta import config, dossier
from chitragupta.dossier import PAPER_MD, _outline
from chitragupta.review import _units


@pytest.fixture
def paper(isolated_config):
    draft = config.DRAFTS_DIR / "tool-paper" / "main.tex"
    draft.parent.mkdir(parents=True)
    draft.write_text("x\n", encoding="utf-8")
    return draft


def _paper_md(draft):
    return (dossier.dossier_dir(draft) / PAPER_MD).read_text(encoding="utf-8")


def test_research_paper_is_a_genre_init_records(paper):
    assert "research-paper" in dossier.GENRES
    assert dossier.main(["init", str(paper), "--genre", "research-paper"]) == 0
    scope = (dossier.dossier_dir(paper) / "scope.md").read_text(encoding="utf-8")
    assert "- genre: research-paper" in scope


def test_init_writes_paper_md_for_a_research_paper(paper):
    written = dossier.init(paper, "research-paper")
    assert dossier.dossier_dir(paper) / PAPER_MD in written
    text = _paper_md(paper)
    for heading in ("## Message", "## Problem", "## Contributions", "## Research questions"):
        assert heading in text
    assert "- software: sources/" in text


@pytest.mark.parametrize("genre", [g for g in dossier.GENRES if g != "research-paper"])
def test_no_other_genre_gets_a_paper_md(paper, genre):
    dossier.init(paper, genre)
    assert not (dossier.dossier_dir(paper) / PAPER_MD).exists()


def test_init_never_overwrites_a_filled_paper_md(paper):
    dossier.init(paper, "research-paper")
    (dossier.dossier_dir(paper) / PAPER_MD).write_text("mine\n", encoding="utf-8")
    assert dossier.init(paper, "research-paper") == []
    assert _paper_md(paper) == "mine\n"


def test_the_template_declares_no_query_a_skill_would_run():
    """A skill runs declared queries verbatim, so the template's example
    must sit inside a comment rather than ship as a real query."""
    from chitragupta.dossier._paper import PAPER_TEMPLATE

    assert not any(s.queries for s in _outline.parse(PAPER_TEMPLATE).sections.values())


def test_the_genre_is_measured_like_a_thesis_chapter_and_uncited_like_a_textbook():
    assert _units.UNITS["research-paper"] == "paragraph"
    assert _units.UNCITED_PROSE["research-paper"] == "ordinary"
