import json


from chitragupta import unit
from chitragupta.review import citekey_union


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


BOOK_SPEC = SPEC_MD


def write_record(book, unit_id, citekeys, *, draft_text=None):
    if draft_text is None:
        draft_text = "\n".join(f"A claim [@{key}]." for key in citekeys) + "\n"
    unit.draft_path(book, unit_id).write_text(draft_text, encoding="utf-8")
    built = unit.contract(book, unit_id, sources=list(citekeys))
    path = unit.record_path(book, unit_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(unit.record_text(built, draft_text, sorted(citekeys)), encoding="utf-8")
    return path


def assemble(book, unit_ids, *, beside=None, unresolved=(), missing_units=()):
    names = list(unresolved) + list(beside or {}) + [f"{u}.tex" for u in unit_ids]
    for name, text in (beside or {}).items():
        (book / name).write_text(text, encoding="utf-8")
    for unit_id in unit_ids:
        if unit_id not in missing_units:
            (book / f"{unit_id}.tex").write_text(
                f"Rendered prose for {unit_id}.\n", encoding="utf-8"
            )
    body = "\n".join("\\input{" + name + "}" for name in names)
    path = book / "book.tex"
    path.write_text(
        "\\documentclass{book}\n\\begin{document}\n" + body + "\n\\end{document}\n",
        encoding="utf-8",
    )
    return path


class TestTheInvariantHolds:
    def test_a_book_including_every_unit_reports_no_drop(self, book):
        write_record(book, "ch-model", ["smith_2024"])
        write_record(book, "ch-data", ["jones_2023"])
        assembled = assemble(book, ["ch-model", "ch-data"])

        result = citekey_union.compute(assembled)

        assert result.dropped == {}
        assert result.appeared == set()
        assert result.unchecked == []
        assert result.omitted == []

    def test_a_skeleton_stating_no_citekey_is_not_read_as_a_total_loss(self, book):
        write_record(book, "ch-model", ["smith_2024"])
        write_record(book, "ch-data", ["jones_2023"])
        assembled = assemble(book, ["ch-model", "ch-data"])

        assert citekey_union._citekeys(assembled.read_text(encoding="utf-8"), assembled) == set()
        assert citekey_union.compute(assembled).dropped == {}


class TestAUnitTheBookLeftOut:
    def test_an_omitted_unit_locates_the_citekeys_that_went_with_it(self, book):
        write_record(book, "ch-model", ["smith_2024"])
        write_record(book, "ch-data", ["jones_2023"])
        assembled = assemble(book, ["ch-data"])

        result = citekey_union.compute(assembled)

        assert result.dropped == {"smith_2024": ["ch-model"]}
        assert [entry.unit for entry in result.omitted] == ["ch-model"]

    def test_a_citekey_another_included_unit_shares_is_not_dropped(self, book):
        write_record(book, "ch-model", ["smith_2024"])
        write_record(book, "ch-data", ["smith_2024"])
        assembled = assemble(book, ["ch-data"])

        result = citekey_union.compute(assembled)

        assert result.dropped == {}
        assert [entry.unit for entry in result.omitted] == ["ch-model"]

    def test_two_omitted_units_sharing_a_citekey_name_both(self, book):
        write_record(book, "ch-model", ["smith_2024"])
        write_record(book, "ch-data", ["smith_2024"])
        assembled = assemble(book, [])

        result = citekey_union.compute(assembled)

        assert result.dropped == {"smith_2024": ["ch-model", "ch-data"]}


class TestACitekeyFromOutsideEveryUnit:
    def test_a_citekey_in_the_front_matter_is_reported(self, book):
        write_record(book, "ch-model", ["smith_2024"])
        write_record(book, "ch-data", ["jones_2023"])
        assembled = assemble(
            book,
            ["ch-model", "ch-data"],
            beside={"titlepage.tex": "A dedication \\citep{nobody_1999}.\n"},
        )

        result = citekey_union.compute(assembled)

        assert result.appeared == {"nobody_1999"}
        assert result.outside_units == ["titlepage.tex"]

    def test_an_empty_answer_is_earned_by_reading_the_non_unit_files(self, book):
        write_record(book, "ch-model", ["smith_2024"])
        write_record(book, "ch-data", ["jones_2023"])
        assembled = assemble(
            book,
            ["ch-model", "ch-data"],
            beside={"titlepage.tex": "A dedication citing nothing.\n"},
        )

        result = citekey_union.compute(assembled)

        assert result.appeared == set()
        assert result.outside_units == ["titlepage.tex"]

    def test_a_commented_out_citekey_in_the_front_matter_is_not_reported(self, book):
        write_record(book, "ch-model", ["smith_2024"])
        write_record(book, "ch-data", ["jones_2023"])
        assembled = assemble(
            book,
            ["ch-model", "ch-data"],
            beside={"titlepage.tex": "% Dropped: \\citep{nobody_1999}\nA dedication.\n"},
        )

        assert citekey_union.compute(assembled).appeared == set()

    def test_each_file_is_read_by_its_own_suffix(self):
        assert citekey_union._citekeys("% \\citep{nobody_1999}\n", "book.tex") == set()
        assert citekey_union._citekeys("30% [@nobody_1999]\n", "front.md") == {"nobody_1999"}

    def test_withheld_while_any_unit_is_unassessed(self, book):
        write_record(book, "ch-model", ["smith_2024"])
        assembled = assemble(
            book, ["ch-model"], beside={"titlepage.tex": "See \\citep{nobody_1999}.\n"}
        )

        result = citekey_union.compute(assembled)

        assert result.appeared is None
        assert [entry.unit for entry in result.unchecked] == ["ch-data"]


class TestResolvingWhatTheAssemblyNames:
    def test_a_suffixless_input_finds_the_file(self, book):
        write_record(book, "ch-model", ["smith_2024"])
        write_record(book, "ch-data", ["jones_2023"])
        (book / "titlepage.tex").write_text("See \\citep{nobody_1999}.\n", encoding="utf-8")
        assembled = book / "book.tex"
        assembled.write_text(
            "\\input{titlepage}\n\\input{ch-model.tex}\n\\input{ch-data.tex}\n", encoding="utf-8"
        )

        result = citekey_union.compute(assembled)

        assert result.outside_units == ["titlepage.tex"]
        assert result.appeared == {"nobody_1999"}

    def test_a_repeated_include_is_read_once_and_a_url_is_not_followed(self, book):
        write_record(book, "ch-model", ["smith_2024"])
        write_record(book, "ch-data", ["jones_2023"])
        (book / "front.tex").write_text("Front matter.\n", encoding="utf-8")
        assembled = book / "book.md"
        assembled.write_text(
            "[front](front.tex)\n[again](front.tex)\n[home](https://example.org/x.md)\n"
            "[one](ch-model.md)\n[two](ch-data.md)\n",
            encoding="utf-8",
        )

        result = citekey_union.compute(assembled)

        assert result.outside_units == ["front.tex"]
        assert result.unresolved == []
        assert result.dropped == {}


class TestAUnitStemWithNoFileBehindIt:
    def test_a_renamed_or_deleted_chapter_file_is_not_read_as_included(self, book):
        write_record(book, "ch-model", ["smith_2024"])
        write_record(book, "ch-data", ["jones_2023"])
        assembled = assemble(book, ["ch-model", "ch-data"], missing_units=["ch-data"])

        result = citekey_union.compute(assembled)

        assert result.dropped == {"jones_2023": ["ch-data"]}
        assert [entry.unit for entry in result.omitted] == ["ch-data"]


class TestItSaysWhatItCouldNotRead:
    def test_an_include_with_no_file_behind_it_is_named(self, book):
        write_record(book, "ch-model", ["smith_2024"])
        write_record(book, "ch-data", ["jones_2023"])
        assembled = assemble(book, ["ch-model", "ch-data"], unresolved=["appendix.tex"])

        assert citekey_union.compute(assembled).unresolved == ["appendix.tex"]

    def test_an_include_that_is_not_text_is_named_rather_than_crashing(self, book):
        write_record(book, "ch-model", ["smith_2024"])
        write_record(book, "ch-data", ["jones_2023"])
        (book / "cover.pdf").write_bytes(b"%PDF-1.7\n\xff\xfe\x00 not utf-8")
        assembled = book / "book.md"
        assembled.write_text(
            "[cover](cover.pdf)\n[one](ch-model.md)\n[two](ch-data.md)\n", encoding="utf-8"
        )

        result = citekey_union.compute(assembled)

        assert result.unresolved == ["cover.pdf"]
        assert result.outside_units == []
        assert result.dropped == {}

    def test_the_text_report_lists_both_kinds_of_coverage_gap(self, book, capsys):
        write_record(book, "ch-model", ["smith_2024"])
        write_record(book, "ch-data", ["jones_2023"])
        assembled = assemble(
            book,
            ["ch-model", "ch-data"],
            beside={"titlepage.tex": "See \\citep{nobody_1999}.\n"},
            unresolved=["appendix.tex"],
        )

        assert citekey_union.main([str(assembled)]) == 0
        out = capsys.readouterr().out
        assert "read outside the units: titlepage.tex" in out
        assert "named but not read: appendix.tex" in out
        assert "Cited outside any unit:\n  - nobody_1999" in out

    def test_the_written_report_itemises_a_citekey_from_outside(self, book, isolated_config):
        write_record(book, "ch-model", ["smith_2024"])
        write_record(book, "ch-data", ["jones_2023"])
        assembled = assemble(
            book,
            ["ch-model", "ch-data"],
            beside={"titlepage.tex": "See \\citep{nobody_1999}.\n"},
        )

        assert citekey_union.main([str(assembled), "--write", "--formats", "md"]) == 0
        body = (isolated_config.REVIEW_DIR / "twins" / "book.union.md").read_text(encoding="utf-8")
        assert "## Cited outside any unit" in body
        assert "- `nobody_1999`" in body
        assert "read outside the units: titlepage.tex" in body

    def test_a_unit_edited_since_acceptance_is_unchecked_not_dropped(self, book):
        write_record(book, "ch-model", ["smith_2024"])
        write_record(book, "ch-data", ["jones_2023"])
        unit.draft_path(book, "ch-data").write_text(
            "Rewritten, and no longer citing anything.\n", encoding="utf-8"
        )
        assembled = assemble(book, ["ch-model"])

        result = citekey_union.compute(assembled)

        assert result.dropped == {}
        assert [(e.unit, e.state) for e in result.unchecked] == [
            ("ch-data", "stale: draft changed since accepted")
        ]

    def test_a_unit_with_no_record_is_unchecked(self, book):
        write_record(book, "ch-model", ["smith_2024"])
        unit.draft_path(book, "ch-data").write_text("Prose.\n", encoding="utf-8")
        assembled = assemble(book, ["ch-model"])

        result = citekey_union.compute(assembled)

        assert [(e.unit, e.state) for e in result.unchecked] == [("ch-data", "drafted")]

    def test_unchecked_wins_over_omitted_and_both_facts_survive(self, book):
        write_record(book, "ch-model", ["smith_2024"])
        unit.draft_path(book, "ch-data").write_text("Prose.\n", encoding="utf-8")
        assembled = assemble(book, ["ch-model"])

        result = citekey_union.compute(assembled)

        assert result.dropped == {}
        assert [(e.unit, e.included) for e in result.unchecked] == [("ch-data", False)]


class TestWhatItRefuses:
    def test_a_draft_in_no_book_is_refused(self, isolated_config):
        stray = isolated_config.DRAFTS_DIR / "survey.md"
        stray.parent.mkdir(parents=True, exist_ok=True)
        stray.write_text("A claim [@smith_2024].\n", encoding="utf-8")

        assert citekey_union.main([str(stray)]) == 1

    def test_pointing_at_a_unit_rather_than_the_assembly_is_refused(self, book, capsys):
        write_record(book, "ch-model", ["smith_2024"])

        assert citekey_union.main([str(unit.draft_path(book, "ch-model"))]) == 1
        assert "ch-model" in capsys.readouterr().err


class TestTheReport:
    def test_json_prints_and_exits_zero(self, book):
        write_record(book, "ch-model", ["smith_2024"])
        write_record(book, "ch-data", ["jones_2023"])
        assembled = assemble(book, ["ch-data"])

        assert citekey_union.main([str(assembled), "--json"]) == 0

    def test_written_report_lands_beside_the_other_aids(self, book, isolated_config):
        write_record(book, "ch-model", ["smith_2024"])
        write_record(book, "ch-data", ["jones_2023"])
        assembled = assemble(book, ["ch-data"])

        assert citekey_union.main([str(assembled), "--write", "--formats", "md"]) == 0
        report = isolated_config.REVIEW_DIR / "twins" / "book.union.md"
        assert report.is_file()
        assert "smith_2024" in report.read_text(encoding="utf-8")
        payload = json.loads(
            (isolated_config.REVIEW_DIR / "twins" / "book.union.json").read_text(encoding="utf-8")
        )
        assert payload["aid"] == "union"
        assert payload["findings"][0]["citekey"] == "smith_2024"
        assert payload["units_omitted"] == ["ch-model"]
        assert payload["appeared_determinable"] is True

    def test_the_payload_marks_the_withheld_direction(self, book, isolated_config):
        write_record(book, "ch-model", ["smith_2024"])
        assembled = assemble(book, ["ch-model"])

        assert citekey_union.main([str(assembled), "--write", "--formats", "md"]) == 0
        payload = json.loads(
            (isolated_config.REVIEW_DIR / "twins" / "book.union.json").read_text(encoding="utf-8")
        )
        assert payload["appeared_determinable"] is False
        assert payload["units_unchecked"] == [
            {"unit": "ch-data", "state": "unwritten", "included": False}
        ]

    def test_the_text_report_names_what_it_did_not_check(self, book, capsys):
        write_record(book, "ch-model", ["smith_2024"])
        assembled = assemble(book, ["ch-model"])

        assert citekey_union.main([str(assembled)]) == 0
        out = capsys.readouterr().out
        assert "Not checked:" in out and "ch-data -- unwritten" in out
        assert "not determinable" in out


class TestAnAssemblyUnderRendered:
    def test_a_rendered_book_is_checked_against_its_drafts_records(self, book, isolated_config):
        write_record(book, "ch-model", ["smith_2024"])
        write_record(book, "ch-data", ["jones_2023"])
        rendered = isolated_config.RENDERED_DIR / "twins"
        rendered.mkdir(parents=True, exist_ok=True)
        assembled = assemble(rendered, ["ch-model", "ch-data"])

        result = citekey_union.compute(assembled)

        assert result.dropped == {}
        assert result.omitted == []
        assert [entry.unit for entry in result.checked] == ["ch-model", "ch-data"]

    def test_a_unit_the_rendered_book_left_out_is_still_located(self, book, isolated_config):
        write_record(book, "ch-model", ["smith_2024"])
        write_record(book, "ch-data", ["jones_2023"])
        rendered = isolated_config.RENDERED_DIR / "twins"
        rendered.mkdir(parents=True, exist_ok=True)
        assembled = assemble(rendered, ["ch-data"])

        result = citekey_union.compute(assembled)

        assert result.dropped == {"smith_2024": ["ch-model"]}
        assert result.omitted[0].unit == "ch-model"

    def test_a_rendered_unit_gets_the_refusal_rather_than_an_error(self, book, isolated_config):
        write_record(book, "ch-model", ["smith_2024"])
        rendered = isolated_config.RENDERED_DIR / "twins"
        rendered.mkdir(parents=True, exist_ok=True)
        assemble(rendered, ["ch-model"])

        refusal = citekey_union.refuse_a_unit(rendered / "ch-model.tex")

        assert refusal is not None
        assert "is unit `ch-model`" in refusal

    def test_the_written_report_mirrors_the_book_instead_of_landing_flat(
        self, book, isolated_config
    ):
        write_record(book, "ch-model", ["smith_2024"])
        write_record(book, "ch-data", ["jones_2023"])
        rendered = isolated_config.RENDERED_DIR / "twins"
        rendered.mkdir(parents=True, exist_ok=True)
        assembled = assemble(rendered, ["ch-model", "ch-data"])

        assert citekey_union.main([str(assembled), "--write", "--formats", "md"]) == 0

        assert (isolated_config.REVIEW_DIR / "twins" / "book.union.md").is_file()
        assert not (isolated_config.REVIEW_DIR / "book.union.md").exists()

    def test_a_path_in_no_book_is_refused_rather_than_raising(self, isolated_config, capsys):
        stray = isolated_config.CONTENT_DIR / "stray.tex"
        stray.parent.mkdir(parents=True, exist_ok=True)
        stray.write_text("\\documentclass{book}\n", encoding="utf-8")

        assert citekey_union.main([str(stray)]) == 1
        assert "spec" in capsys.readouterr().err.lower()

    def test_an_authored_preamble_is_read_as_the_assembly_s_own_material(
        self, book, isolated_config
    ):
        write_record(book, "ch-model", ["smith_2024"])
        write_record(book, "ch-data", ["jones_2023"])
        rendered = isolated_config.RENDERED_DIR / "twins"
        rendered.mkdir(parents=True, exist_ok=True)
        assembled = assemble(
            rendered,
            ["ch-model", "ch-data"],
            beside={"preamble.tex": "\\newcommand{\\house}{\\citep{house_2020}}\n"},
        )
        assembled.write_text(
            assembled.read_text(encoding="utf-8").replace(
                "\\input{preamble.tex}", "\\input{preamble}"
            ),
            encoding="utf-8",
        )

        result = citekey_union.compute(assembled)

        assert result.unresolved == []
        assert "preamble.tex" in result.outside_units
        assert result.appeared == {"house_2020"}

    def test_the_books_bib_is_not_read_as_an_include(self, book, isolated_config):
        write_record(book, "ch-model", ["smith_2024"])
        write_record(book, "ch-data", ["jones_2023"])
        rendered = isolated_config.RENDERED_DIR / "twins"
        rendered.mkdir(parents=True, exist_ok=True)
        assembled = assemble(rendered, ["ch-model", "ch-data"])
        (rendered / "bibliography.bib").write_text(
            "@article{never_cited_1999, title={A}}\n", encoding="utf-8"
        )
        assembled.write_text(
            assembled.read_text(encoding="utf-8").replace(
                "\\end{document}", "\\bibliography{bibliography}\n\\end{document}"
            ),
            encoding="utf-8",
        )

        result = citekey_union.compute(assembled)

        assert result.appeared == set()
        assert result.outside_units == []
        assert result.unresolved == []
