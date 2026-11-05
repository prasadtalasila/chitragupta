"""The index filter (#1168): one `\\index{<id>}` per term per chapter, and
the sidecar `registry index` reads.

The filter cases run the shipped `assets/pandoc/index_terms.lua` through
real pandoc with exactly the argv `_index_terms.pandoc_args` adds, as
`test_render_output_unit_labels.py` does: the filter is Lua, which
coverage cannot measure, so every rule it carries has a case here.
"""

import json
import subprocess
from pathlib import Path

import pytest

from chitragupta import render_output
from chitragupta.render_output import _index_terms
from chitragupta.render_output._cli import main
from tests.conftest import pandoc_available

needs_pandoc = pytest.mark.skipif(not pandoc_available, reason="pandoc not installed")

UNIT = "ch-one"


def terms_file(tmp_path: Path, terms: dict, min_mentions=2, skip=("Exercises",)) -> Path:
    path = tmp_path / "index-terms.json"
    table = {
        id_: {"spellings": spellings, "defined_in": defined, "always": always}
        for id_, (spellings, defined, always) in terms.items()
    }
    data = {"min_mentions": min_mentions, "skip_sections": list(skip), "terms": table}
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def fragment(tmp_path: Path, text: str, terms: Path) -> "tuple[str, dict]":
    """`text` as a fragment render's LaTeX, and the sidecar it wrote."""
    draft = tmp_path / f"{UNIT}.md"
    draft.write_text(text, encoding="utf-8")
    cmd = ["pandoc", str(draft), "-t", "latex", "--natbib", "--top-level-division=chapter"]
    cmd += _index_terms.pandoc_args(draft, terms, tmp_path)
    latex = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    sidecar = json.loads((tmp_path / f"{UNIT}.index.json").read_text(encoding="utf-8"))
    return latex, sidecar


TWIN = {"t1": (["digital twin"], [], [])}


# --- the argv -------------------------------------------------------------


def test_no_term_table_adds_nothing(tmp_path):
    assert _index_terms.pandoc_args(tmp_path / "ch.md", None, tmp_path) == []


def test_the_argv_names_the_filter_the_table_the_unit_and_the_sidecar(tmp_path):
    args = _index_terms.pandoc_args(tmp_path / "ch-two.md", tmp_path / "t.json", tmp_path / "out")
    assert args[:2] == ["--lua-filter", str(_index_terms.FILTER)]
    assert f"chitragupta-index-terms={(tmp_path / 't.json').resolve()}" in args
    assert "chitragupta-index-unit=ch-two" in args
    assert f"chitragupta-index-sidecar={(tmp_path / 'out' / 'ch-two.index.json').resolve()}" in args


def test_the_pandoc_command_carries_it_only_when_asked(tmp_path):
    def command(index_terms):
        names = ("in.md", "bib.bib", "ieee.csl", "out.tex", "ch-one.md")
        cmd, _ = render_output._pandoc_command(
            *(Path(name) for name in names),
            "tex", "article", "12pt", "a4", "1in", [], True, False, [], index_terms,
        )  # fmt: skip
        return cmd

    assert str(_index_terms.FILTER) not in command(None)
    assert str(_index_terms.FILTER) in command(tmp_path / "t.json")


def test_the_cli_refuses_index_terms_without_fragment(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        main([str(tmp_path / "ch.md"), "--format", "tex", "--index-terms", "t.json"])
    assert exc.value.code == 2
    assert "--index-terms needs --fragment" in capsys.readouterr().err


# --- the filter ------------------------------------------------------------


@needs_pandoc
class TestTheFilter:
    def test_a_term_twice_is_placed_once_at_its_first_mention(self, tmp_path):
        latex, side = fragment(
            tmp_path,
            "# One\n\nA digital twin here.\n\nA digital twin there.\n",
            terms_file(tmp_path, TWIN),
        )
        assert latex.count("\\index{t1}") == 1
        assert latex.index("\\index{t1}") < latex.index("there")
        assert side["unit"] == UNIT and side["terms"]["t1"]["count"] == 2
        assert side["terms"]["t1"]["indexed"] is True

    def test_one_mention_below_the_threshold_is_counted_not_placed(self, tmp_path):
        latex, side = fragment(tmp_path, "# One\n\nA digital twin.\n", terms_file(tmp_path, TWIN))
        assert "\\index" not in latex
        assert side["terms"]["t1"] == {
            "count": 1,
            "indexed": False,
            "midsentence": {"digital twin": 1},
            "spellings": {"digital twin": 1},
        }

    def test_the_defining_chapter_is_bold_even_once(self, tmp_path):
        terms = terms_file(tmp_path, {"t1": (["digital twin"], [UNIT], [])})
        latex, _ = fragment(tmp_path, "# One\n\nA digital twin.\n", terms)
        assert "\\index{t1|textbf}" in latex

    def test_always_places_a_single_mention(self, tmp_path):
        terms = terms_file(tmp_path, {"t1": (["digital twin"], [], [UNIT])})
        latex, _ = fragment(tmp_path, "# One\n\nA digital twin.\n", terms)
        assert "\\index{t1}" in latex

    def test_line_breaks_hyphens_plurals_possessives_and_emphasis_all_match(self, tmp_path):
        text = (
            "# One\n\nThe *digital* twin. Two digital\ntwins. A digital-twin. "
            "The digital twin's state.\n"
        )
        latex, side = fragment(tmp_path, text, terms_file(tmp_path, TWIN))
        assert side["terms"]["t1"]["count"] == 4
        assert "\\emph{digital}\\index{t1} twin" in latex

    def test_the_longer_term_wins_and_the_shorter_never_takes_its_place(self, tmp_path):
        terms = terms_file(tmp_path, {"t1": (["digital twin"], [], []), "t2": (["twin"], [], [])})
        text = "# One\n\nThe *digital* twin and the digital twin.\n"
        latex, side = fragment(tmp_path, text, terms)
        assert "t2" not in side["terms"]
        assert "\\index{t2}" not in latex

    def test_a_footnote_is_read_and_its_entry_stays_in_it(self, tmp_path):
        text = "# One\n\nBody.^[A digital twin, and a digital twin.]\n"
        latex, side = fragment(tmp_path, text, terms_file(tmp_path, TWIN))
        assert side["terms"]["t1"]["count"] == 2
        assert "\\footnote{A digital\\index{t1} twin" in latex

    def test_links_quotes_tables_lists_and_definitions_are_read(self, tmp_path):
        text = (
            '# One\n\nSee [the digital twin](#x) and "digital twin".\n\n'
            "- a digital twin\n\nTerm digital twin\n\n: a digital twin\n\n> a digital twin\n\n"
            "| a |\n|---|\n| digital twin |\n\n| line digital twin\n"
        )
        _, side = fragment(tmp_path, text, terms_file(tmp_path, TWIN))
        assert side["terms"]["t1"]["count"] == 8

    def test_headings_captions_code_maths_and_citations_are_not_read(self, tmp_path):
        text = (
            "# Digital twin\n\n![digital twin](x.png)\n\n`digital twin` $digital twin$ "
            "[@digital]\n\n```\ndigital twin\n```\n"
        )
        _, side = fragment(tmp_path, text, terms_file(tmp_path, TWIN))
        assert side["terms"] == {}

    def test_a_barrier_splits_a_phrase(self, tmp_path):
        _, side = fragment(tmp_path, "# One\n\ndigital `x` twin\n", terms_file(tmp_path, TWIN))
        assert side["terms"] == {}

    def test_a_skipped_section_runs_to_the_next_heading_as_high(self, tmp_path):
        text = (
            "# One\n\n## Exercises\n\nA digital twin.\n\n### Deeper\n\nA digital twin.\n\n"
            "## Back\n\nA digital twin.\n"
        )
        _, side = fragment(tmp_path, text, terms_file(tmp_path, TWIN))
        assert side["terms"]["t1"]["count"] == 1

    def test_a_skipped_title_matches_whatever_its_case(self, tmp_path):
        _, side = fragment(
            tmp_path, "# One\n\n## EXERCISES\n\nA digital twin.\n", terms_file(tmp_path, TWIN)
        )
        assert side["terms"] == {}

    def test_casing_is_recorded_only_away_from_a_sentence_start(self, tmp_path):
        terms = terms_file(tmp_path, {"t1": (["markov chain"], [], [])})
        text = "# One\n\nMarkov chains. A Markov chain and “Markov chain” too.\n"
        _, side = fragment(tmp_path, text, terms)
        assert side["terms"]["t1"]["midsentence"] == {"Markov chain": 2}

    def test_the_sidecar_carries_the_digest_of_the_table(self, tmp_path):
        import hashlib

        terms = terms_file(tmp_path, TWIN)
        _, side = fragment(tmp_path, "# One\n\nNothing.\n", terms)
        assert side["terms_digest"] == hashlib.sha1(terms.read_bytes()).hexdigest()

    def test_entries_in_one_paragraph_all_land(self, tmp_path):
        terms = terms_file(
            tmp_path,
            {"t1": (["digital twin"], [UNIT], []), "t2": (["model"], [UNIT], [])},
        )
        latex, _ = fragment(tmp_path, "# One\n\nA model and a digital twin.\n", terms)
        assert "model\\index{t2|textbf}" in latex
        assert "digital\\index{t1|textbf} twin" in latex

    def test_a_term_glossed_in_the_plural_matches_its_singular(self, tmp_path):
        """Found on the digital-twins book: the glossary's "lifecycle
        phases" against prose that says "lifecycle phase" eight times."""
        terms = terms_file(
            tmp_path, {"t1": (["lifecycle phases"], [], []), "t2": (["boxes"], [], [])}
        )
        text = "# One\n\nEach lifecycle phase and lifecycle phases. One box.\n"
        _, side = fragment(tmp_path, text, terms)
        assert side["terms"]["t1"]["count"] == 2
        assert side["terms"]["t2"]["count"] == 1
