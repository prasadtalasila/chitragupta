"""chitragupta/draft_figures.py: the read-only per-citekey figure lookup a
drafting session consults while writing (#654).

The one modality with no route to the drafting stage before this. Prose,
table cell text and (since #651) decoded equations all reach a draft
through `content/parsed/<citekey>.txt`, which is the only artefact
`chitragupta/retrieval.py` indexes. A bitmap cannot be, so figures needed
a route rather than a widening.
"""

import ast
import json
from pathlib import Path

import pytest

from chitragupta import config, draft_figures, ledger

from tests.conftest import make_reference

RECORDS = [
    {
        "page": 7,
        "caption": "Figure 3. Sensor placement",
        "cite": "Figure 3 of [@a2024], p.7",
        "image": "a2024_artifacts/picture_000002.png",
        "bbox": [10.0, 120.0, 130.0, 40.0],
    },
    {
        "page": 9,
        "caption": None,
        "cite": "the figure on p.9 of [@a2024]",
        "image": None,
        "bbox": [5.0, 90.0, 200.0, 10.0],
    },
]


@pytest.fixture
def seeded(ledger_con, tmp_path):
    """One citekey in the ledger; its figure index written or not per
    test."""
    ledger.upsert_reference(ledger_con, make_reference(citekey="a2024", title="A Paper"))
    config.DOCLING_DIR.mkdir(parents=True, exist_ok=True)
    return ledger_con


def _write_index(records) -> Path:
    path = config.DOCLING_DIR / "a2024.figures.json"
    path.write_text(json.dumps(records), encoding="utf-8")
    return path


class TestFigures:
    def test_returns_the_recorded_figures(self, seeded):
        _write_index(RECORDS)
        found, reason = draft_figures.figures("a2024")
        assert reason is None
        assert [f["caption"] for f in found] == ["Figure 3. Sensor placement", None]

    def test_resolves_the_image_to_a_path_a_caller_can_open(self, seeded):
        """The record stores a name relative to the .md's own directory,
        which is what keeps content/docling/ movable as a unit -- so a
        caller handed the raw value cannot open it without knowing that.
        """
        _write_index(RECORDS)
        found, _ = draft_figures.figures("a2024")
        assert found[0]["image_path"] == str(
            config.DOCLING_DIR / "a2024_artifacts" / "picture_000002.png"
        )
        assert found[1]["image_path"] is None

    def test_an_unenriched_citekey_says_so_and_names_the_command(self, seeded):
        """Distinct from "this paper has no figures", because only one of
        the two is something the reader can act on -- and acting on the
        wrong one means a corpus-wide enrichment run for nothing."""
        found, reason = draft_figures.figures("a2024")
        assert found is None
        assert "chitragupta.enrich" in reason

    def test_a_paper_with_no_figures_is_not_an_unenriched_one(self, seeded):
        _write_index([])
        found, reason = draft_figures.figures("a2024")
        assert found == []
        assert reason is None

    def test_a_citekey_the_ledger_lacks_is_reported_as_that(self, seeded):
        """Not as "not enriched": a typo would otherwise send someone off
        to re-run the enrichment layer over the whole corpus."""
        with pytest.raises(KeyError, match="not in the ledger"):
            draft_figures.figures("nosuchkey_2024")

    @pytest.mark.parametrize(
        "name", ["../../outside.png", "a2024_artifacts/../../../outside.png", "/etc/passwd"]
    )
    def test_an_image_name_that_leaves_the_docling_directory_is_refused(self, seeded, name):
        """Issue 875. The sidecar is a file on disk like any other, and its
        `image` value was joined into a path unchecked -- so a tampered one
        pointed `image_path` anywhere on the host, which this command then
        printed as a figure to look at. Refused, not rewritten: a
        sanitised name would hide that the index is not what was written.
        """
        _write_index([{**RECORDS[0], "image": name}])
        with pytest.raises(draft_figures.FigureIndexError, match="outside"):
            draft_figures.figures("a2024")

    def test_an_image_name_with_a_nul_byte_is_refused_rather_than_crashing(self, seeded):
        """Resolving such a name raises `ValueError`; that is a refusal of
        the index, not a traceback."""
        _write_index([{**RECORDS[0], "image": "a\u0000b.png"}])
        with pytest.raises(draft_figures.FigureIndexError, match="outside"):
            draft_figures.figures("a2024")

    def test_a_nested_name_inside_the_directory_is_not_refused(self, seeded):
        """The enrichment layer writes `<stem>_artifacts/picture_N.png`,
        two components, so "one path component" would be the wrong rule:
        it would refuse every real index. Where the name *lands* is the
        rule."""
        _write_index(RECORDS)
        found, _ = draft_figures.figures("a2024")
        assert found[0]["image_path"].endswith("picture_000002.png")


class TestCli:
    def test_it_prints_each_figure_with_its_citation(self, seeded, capsys):
        _write_index(RECORDS)
        assert draft_figures.main(["a2024"]) == 0
        out = capsys.readouterr().out
        assert "Figure 3 of [@a2024], p.7" in out
        assert "picture_000002.png" in out

    def test_json_output_carries_the_records(self, seeded, capsys):
        """One envelope shape whether or not there are figures, so a
        machine caller never has to sniff the type of what came back."""
        _write_index(RECORDS)
        assert draft_figures.main(["a2024", "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert [f["page"] for f in payload["figures"]] == [7, 9]
        assert payload["reason"] is None

    def test_an_unenriched_citekey_exits_zero(self, seeded, capsys):
        """A real answer about the corpus, not a failure of this command."""
        assert draft_figures.main(["a2024"]) == 0
        assert "chitragupta.enrich" in capsys.readouterr().out

    def test_a_paper_with_no_figures_exits_zero_and_says_so(self, seeded, capsys):
        _write_index([])
        assert draft_figures.main(["a2024"]) == 0
        assert "no figures" in capsys.readouterr().out

    def test_an_unknown_citekey_is_an_error_on_stderr(self, seeded, capsys):
        assert draft_figures.main(["nosuchkey_2024"]) == 1
        assert "not in the ledger" in capsys.readouterr().err

    def test_a_refused_index_is_an_error_on_stderr_naming_the_value(self, seeded, capsys):
        """Named and non-zero, and nothing on stdout: a `--json` caller
        must not get a half-trusted list of figures."""
        _write_index([{**RECORDS[0], "image": "../../outside.png"}])
        assert draft_figures.main(["a2024", "--json"]) == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "[error]" in captured.err
        assert "../../outside.png" in captured.err

    def test_json_reports_an_unenriched_citekey_too(self, seeded, capsys):
        """A machine caller must not read "no index yet" as "no figures"."""
        assert draft_figures.main(["a2024", "--json"]) == 0
        assert json.loads(capsys.readouterr().out)["reason"]


class TestLayerBoundary:
    def test_it_imports_nothing_from_the_enrichment_layer(self):
        """AGENTS.md: the enrichment layer imports nothing from the
        drafting or review layers. A drafting module reaching the other
        way would be the mirror-image violation and would make the
        optional enrich dependencies load on an ordinary drafting run.

        `chitragupta/passages.py`'s rung 1 is the precedent this follows:
        read `content/docling/` as a *path*, never through its writer.
        """
        source = Path(draft_figures.__file__).read_text(encoding="utf-8")
        imported = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        assert not [name for name in imported if "enrich" in name], imported

    def test_the_verb_is_registered(self):
        from chitragupta.draft import VERBS

        assert VERBS["figures"][0] is draft_figures
