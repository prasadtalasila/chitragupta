"""The citekey union invariant over an assembled book (C5).

What is worth pinning here is the invariant itself and the honesty
around it: a citekey an accepted unit stands on and the assembled book
does not carry is *located* to its unit, the other direction is
withheld rather than guessed at while any unit is unassessed, and a unit
whose record no longer describes its prose is named as unchecked instead
of silently compared against stale text.
"""

import json

import pytest

from chitragupta import spec, unit
from chitragupta.review import citekey_union


# Two chapters, each describing its own sections -- so each *chapter* is
# the acceptance unit (#472: a chapter that declares section structure is
# one authored document, and that document is the unit). Two of them, so
# "this unit lost a citekey" and "that one did" are distinguishable,
# which is the whole point of a located finding.
SPEC_MD = """# Composable Digital Twins

## Part I: Foundations {#part-foundations}

### The model half {#ch-model}

Establish that a twin is a model plus a live data link.

#### What a model is {#sec-model-what}

The modelling half.

### The data half {#ch-data}

Establish the link, and why it is the hard half.

#### The link {#sec-data-link}

The wiring half.
"""


@pytest.fixture
def book(isolated_config):
    """A two-unit book with its outline in place and nothing written yet."""
    path = isolated_config.DRAFTS_DIR / "twins"
    spec_file = spec.spec_path(path)
    spec_file.parent.mkdir(parents=True, exist_ok=True)
    spec_file.write_text(SPEC_MD, encoding="utf-8")
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_record(book, unit_id, citekeys, *, draft_text=None):
    """An acceptance record as `unit accept` writes one.

    Written directly rather than through `unit.main(["accept", ...])`
    because that path runs the citation gate, which needs a real ledger
    -- and what this aid reads is the record on disk, not how it got
    there. `draft_text` defaults to text citing exactly `citekeys`, so
    the record and the prose agree and `unit.state` reports `accepted`.
    """
    if draft_text is None:
        draft_text = "\n".join(f"A claim [@{key}]." for key in citekeys) + "\n"
    unit.draft_path(book, unit_id).write_text(draft_text, encoding="utf-8")
    built = unit.contract(book, unit_id, sources=list(citekeys))
    path = unit.record_path(book, unit_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(unit.record_text(built, draft_text, sorted(citekeys)), encoding="utf-8")
    return path


def assemble(book, citekeys):
    """A `book.tex` citing exactly `citekeys`, as book-assembler composes one."""
    path = book / "book.tex"
    body = "\n".join(rf"A claim \citep{{{key}}}." for key in citekeys)
    path.write_text(f"\\documentclass{{book}}\n\\begin{{document}}\n{body}\n\\end{{document}}\n")
    return path


class TestTheInvariantHolds:
    def test_every_unit_citekey_present_reports_no_drop(self, book):
        write_record(book, "ch-model", ["smith_2024"])
        write_record(book, "ch-data", ["jones_2023"])
        assembled = assemble(book, ["smith_2024", "jones_2023"])

        result = citekey_union.compute(assembled)

        assert result.dropped == {}
        assert result.appeared == set()
        assert result.unchecked == []


class TestACitekeyTheBookLost:
    def test_a_dropped_citekey_is_located_to_its_unit(self, book):
        write_record(book, "ch-model", ["smith_2024"])
        write_record(book, "ch-data", ["jones_2023"])
        assembled = assemble(book, ["jones_2023"])

        result = citekey_union.compute(assembled)

        assert result.dropped == {"smith_2024": ["ch-model"]}

    def test_a_citekey_two_units_share_names_both(self, book):
        write_record(book, "ch-model", ["smith_2024"])
        write_record(book, "ch-data", ["smith_2024"])
        assembled = assemble(book, [])

        result = citekey_union.compute(assembled)

        assert result.dropped == {"smith_2024": ["ch-model", "ch-data"]}


class TestACitekeyFromNowhere:
    def test_reported_when_every_unit_is_accepted(self, book):
        write_record(book, "ch-model", ["smith_2024"])
        write_record(book, "ch-data", ["jones_2023"])
        assembled = assemble(book, ["smith_2024", "jones_2023", "nobody_1999"])

        result = citekey_union.compute(assembled)

        assert result.appeared == {"nobody_1999"}

    def test_withheld_while_any_unit_is_unassessed(self, book):
        """An unwritten unit could legitimately be where it came from, so
        the aid says it cannot tell rather than reporting a finding it
        has not earned."""
        write_record(book, "ch-model", ["smith_2024"])
        assembled = assemble(book, ["smith_2024", "nobody_1999"])

        result = citekey_union.compute(assembled)

        assert result.appeared is None
        assert [entry.unit for entry in result.unchecked] == ["ch-data"]


class TestAUnitItWillNotCompareAgainst:
    def test_a_unit_edited_since_acceptance_is_unchecked_not_dropped(self, book):
        write_record(book, "ch-model", ["smith_2024"])
        write_record(book, "ch-data", ["jones_2023"])
        # The prose moved on and nobody re-accepted it: the record's
        # citekeys describe text that no longer exists, so comparing
        # against them would report a drop that is not one.
        unit.draft_path(book, "ch-data").write_text(
            "Rewritten, and no longer citing anything.\n", encoding="utf-8"
        )
        assembled = assemble(book, ["smith_2024"])

        result = citekey_union.compute(assembled)

        assert result.dropped == {}
        assert [(e.unit, e.state) for e in result.unchecked] == [
            ("ch-data", "stale: draft changed since accepted")
        ]

    def test_a_unit_with_no_record_is_unchecked(self, book):
        write_record(book, "ch-model", ["smith_2024"])
        unit.draft_path(book, "ch-data").write_text("Prose.\n", encoding="utf-8")
        assembled = assemble(book, ["smith_2024"])

        result = citekey_union.compute(assembled)

        assert [(e.unit, e.state) for e in result.unchecked] == [("ch-data", "drafted")]


class TestWhatItRefuses:
    def test_a_draft_in_no_book_is_refused(self, isolated_config):
        stray = isolated_config.DRAFTS_DIR / "survey.md"
        stray.parent.mkdir(parents=True, exist_ok=True)
        stray.write_text("A claim [@smith_2024].\n", encoding="utf-8")

        assert citekey_union.main([str(stray)]) == 1

    def test_pointing_at_a_unit_rather_than_the_assembly_is_refused(self, book, capsys):
        """`union ch-model.md` would report every *other* unit's
        citekeys as dropped -- a confident, wholly wrong report."""
        write_record(book, "ch-model", ["smith_2024"])

        assert citekey_union.main([str(unit.draft_path(book, "ch-model"))]) == 1
        assert "ch-model" in capsys.readouterr().err


class TestTheReport:
    def test_json_payload_carries_the_envelope_and_both_directions(self, book):
        write_record(book, "ch-model", ["smith_2024"])
        write_record(book, "ch-data", ["jones_2023"])
        assembled = assemble(book, ["jones_2023"])

        assert citekey_union.main([str(assembled), "--json"]) == 0

    def test_written_report_lands_beside_the_other_aids(self, book, isolated_config):
        write_record(book, "ch-model", ["smith_2024"])
        write_record(book, "ch-data", ["jones_2023"])
        assembled = assemble(book, ["jones_2023"])

        assert citekey_union.main([str(assembled), "--write", "--formats", "md"]) == 0
        report = isolated_config.REVIEW_DIR / "twins" / "book.union.md"
        assert report.is_file()
        assert "smith_2024" in report.read_text(encoding="utf-8")
        payload = json.loads(
            (isolated_config.REVIEW_DIR / "twins" / "book.union.json").read_text(encoding="utf-8")
        )
        assert payload["aid"] == "union"
        assert payload["findings"][0]["citekey"] == "smith_2024"
