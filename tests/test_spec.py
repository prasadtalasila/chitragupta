"""The spec artifact: parsing, the sign-off record, and the four commands.

The behaviours worth pinning are the ones a later session would
otherwise re-derive from the prose: an id is required rather than
derived from the heading text, the sign-off digest is taken over
`spec.md` alone (so signing cannot invalidate its own record), and
`status` is the one command whose exit code answers a question --
"may prose be generated from this outline yet?".
"""

import pytest

from chitragupta import spec


# A spec that parses cleanly: one part, one chapter, two sections.
GOOD = """# Composable Digital Twins

- reader: MSc students
- scope: composition, not deployment

## Part I: Foundations {#part-foundations}

### Chapter 1: What a twin is {#ch-what}

#### The model half {#sec-model}

Establish that a twin is a model plus a live data link.

#### The data half {#sec-data}

Establish the link, and why it is the hard half.
"""


@pytest.fixture
def book(isolated_config):
    """A book directory under content/drafts/, which need not exist yet --
    the outline is written before any prose, which is the whole point."""
    return isolated_config.DRAFTS_DIR / "twins"


def write_spec(book, text=GOOD):
    path = spec.spec_path(book)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# --- paths ---------------------------------------------------------------


def test_a_spec_mirrors_its_book_directory_under_content_specs(book, isolated_config):
    assert spec.spec_path(book) == isolated_config.SPECS_DIR / "twins" / "spec.md"
    assert spec.signoff_path(book) == isolated_config.SPECS_DIR / "twins" / "signoff.md"


def test_a_book_outside_content_drafts_is_refused(isolated_config, tmp_path):
    with pytest.raises(spec.SpecError, match="not under"):
        spec.spec_dir(tmp_path / "elsewhere")


def test_a_symlinked_topic_directory_that_leaves_content_specs_is_refused(
    book, isolated_config, tmp_path
):
    outside = tmp_path / "outside"
    outside.mkdir()
    isolated_config.SPECS_DIR.mkdir(parents=True)
    (isolated_config.SPECS_DIR / "twins").symlink_to(outside)
    with pytest.raises(spec.SpecError, match="outside"):
        spec.spec_dir(book)


# --- parsing -------------------------------------------------------------


def test_parsing_reads_the_title_and_every_unit_in_order():
    parsed = spec.parse(GOOD)
    assert parsed["title"] == "Composable Digital Twins"
    assert parsed["problems"] == []
    assert [(u["id"], u["kind"]) for u in parsed["units"]] == [
        ("part-foundations", "part"),
        ("ch-what", "chapter"),
        ("sec-model", "section"),
        ("sec-data", "section"),
    ]


def test_a_unit_carries_its_brief_and_its_ancestors():
    section = spec.parse(GOOD)["units"][2]
    assert section["title"] == "The model half"
    assert section["brief"] == "Establish that a twin is a model plus a live data link."
    assert section["ancestors"] == ["part-foundations", "ch-what"]


def test_a_hash_inside_a_fenced_block_is_not_a_heading():
    """A brief in a book about software will hold a code fence sooner or
    later. A `#` comment inside one read as a heading would refuse the
    whole outline over a unit that does not exist."""
    fenced = GOOD + "\n```python\n# not a heading\n```\n"
    parsed = spec.parse(fenced)
    assert parsed["problems"] == []
    assert len(parsed["units"]) == 4


def test_prose_before_the_first_heading_belongs_to_no_unit():
    """A spec's preamble is for whoever opens the file. Nothing generates
    from it, so it must not silently become the first unit's brief."""
    parsed = spec.parse("A note to the reader.\n\n" + GOOD)
    assert parsed["problems"] == []
    assert all("note to the reader" not in unit["brief"] for unit in parsed["units"])


def test_a_heading_without_an_id_is_a_problem():
    problems = spec.parse("# Book\n\n## Part I\n")["problems"]
    assert any("{#id}" in problem and "Part I" in problem for problem in problems)


def test_a_repeated_id_is_a_problem():
    text = "# B\n\n## P {#same}\n\n## Q {#same}\n"
    assert any("same" in problem for problem in spec.parse(text)["problems"])


def test_a_level_skipped_on_the_way_down_is_a_problem():
    text = "# B\n\n## P {#p}\n\n#### S {#s}\n"
    problems = spec.parse(text)["problems"]
    assert any("chapter" in problem for problem in problems)


def test_a_heading_deeper_than_a_section_is_a_problem():
    text = "# B\n\n## P {#p}\n\n### C {#c}\n\n#### S {#s}\n\n##### T {#t}\n"
    assert any("deeper" in problem for problem in spec.parse(text)["problems"])


def test_a_second_book_title_is_a_problem():
    assert any("title" in p for p in spec.parse("# One\n\n# Two\n")["problems"])


def test_a_spec_with_no_title_is_a_problem():
    assert any("title" in p for p in spec.parse("## P {#p}\n")["problems"])


def test_a_spec_with_no_units_is_a_problem():
    assert any("no units" in p for p in spec.parse("# Book\n")["problems"])


def test_the_digest_is_twelve_hex_characters_over_the_spec_text():
    first = spec.digest(GOOD)
    assert len(first) == 12 and first == spec.digest(GOOD)
    assert first != spec.digest(GOOD + "\n")


# --- init ----------------------------------------------------------------


def test_init_writes_a_template_that_parses_and_reports_its_own_problems(book, capsys):
    assert spec.main(["init", str(book)]) == 0
    parsed = spec.parse(spec.spec_path(book).read_text(encoding="utf-8"))
    assert parsed["problems"] == []
    assert parsed["title"] == "twins"
    assert "spec.md" in capsys.readouterr().out


def test_init_takes_the_title_when_one_is_given(book):
    spec.main(["init", str(book), "--title", "Composable Digital Twins"])
    assert spec.parse(spec.spec_path(book).read_text(encoding="utf-8"))["title"] == (
        "Composable Digital Twins"
    )


def test_init_refuses_to_overwrite_an_existing_spec(book, capsys):
    write_spec(book)
    assert spec.main(["init", str(book)]) == 1
    assert "already" in capsys.readouterr().err
    assert spec.spec_path(book).read_text(encoding="utf-8") == GOOD


def test_a_book_outside_content_drafts_is_refused_by_the_cli(tmp_path, isolated_config, capsys):
    assert spec.main(["init", str(tmp_path / "elsewhere")]) == 1
    assert "not under" in capsys.readouterr().err


# --- show ----------------------------------------------------------------


def test_show_prints_the_outline_as_a_tree(book, capsys):
    write_spec(book)
    assert spec.main(["show", str(book)]) == 0
    out = capsys.readouterr().out
    assert "Composable Digital Twins" in out
    assert "    [sec-model] The model half" in out


def test_show_of_one_unit_prints_the_slice_a_genre_skill_generates_from(book, capsys):
    write_spec(book)
    assert spec.main(["show", str(book), "--unit", "sec-model"]) == 0
    out = capsys.readouterr().out
    assert "The model half" in out
    assert "Part I: Foundations > Chapter 1: What a twin is" in out
    assert "a model plus a live data link" in out
    assert "signed off: no" in out


def test_a_slice_says_so_once_the_outline_is_signed_off(book, capsys):
    write_spec(book)
    spec.main(["sign", str(book)])
    capsys.readouterr()
    spec.main(["show", str(book), "--unit", "sec-model"])
    assert "signed off: yes" in capsys.readouterr().out


def test_show_of_an_unknown_unit_is_refused_and_names_what_is_there(book, capsys):
    write_spec(book)
    assert spec.main(["show", str(book), "--unit", "sec-nope"]) == 1
    err = capsys.readouterr().err
    assert "sec-nope" in err and "sec-model" in err


def test_show_refuses_a_spec_that_does_not_parse(book, capsys):
    write_spec(book, "# Book\n\n## Part I\n")
    assert spec.main(["show", str(book)]) == 1
    assert "{#id}" in capsys.readouterr().err


def test_a_missing_spec_is_refused_by_name(book, capsys):
    assert spec.main(["show", str(book)]) == 1
    err = capsys.readouterr().err
    assert "spec init" in err


# --- sign ----------------------------------------------------------------


def test_sign_records_the_digest_of_the_spec_it_signed(book, capsys):
    text = write_spec(book).read_text(encoding="utf-8")
    assert spec.main(["sign", str(book)]) == 0
    recorded = spec.signoff_path(book).read_text(encoding="utf-8")
    assert spec.digest(text) in recorded
    assert "units: 4" in recorded
    assert "Signed off" in capsys.readouterr().out


def test_sign_records_who_signed_when_told(book):
    write_spec(book)
    spec.main(["sign", str(book), "--by", "Prasad Talasila"])
    assert "Prasad Talasila" in spec.signoff_path(book).read_text(encoding="utf-8")


def test_signing_the_same_spec_twice_writes_the_same_bytes(book):
    write_spec(book)
    spec.main(["sign", str(book)])
    first = spec.signoff_path(book).read_text(encoding="utf-8")
    spec.main(["sign", str(book)])
    assert spec.signoff_path(book).read_text(encoding="utf-8") == first


def test_sign_refuses_a_spec_that_does_not_parse(book, capsys):
    write_spec(book, "# Book\n\n## Part I\n")
    assert spec.main(["sign", str(book)]) == 1
    assert not spec.signoff_path(book).exists()
    assert "{#id}" in capsys.readouterr().err


# --- status --------------------------------------------------------------


def test_status_refuses_an_outline_nobody_has_signed_off(book, capsys):
    write_spec(book)
    assert spec.main(["status", str(book)]) == 1
    out = capsys.readouterr().out
    assert "not signed off" in out
    assert "1 part" in out and "1 chapter" in out and "2 sections" in out


def test_status_accepts_a_signed_outline(book, capsys):
    write_spec(book)
    spec.main(["sign", str(book)])
    capsys.readouterr()
    assert spec.main(["status", str(book)]) == 0
    assert "signed off" in capsys.readouterr().out


def test_status_refuses_an_outline_that_changed_after_it_was_signed(book, capsys):
    write_spec(book)
    spec.main(["sign", str(book)])
    write_spec(book, GOOD + "\n#### Late addition {#sec-late}\n\nAdded after sign-off.\n")
    capsys.readouterr()
    assert spec.main(["status", str(book)]) == 1
    out = capsys.readouterr().out
    assert "changed since" in out


def test_status_refuses_a_spec_that_does_not_parse(book, capsys):
    write_spec(book, "# Book\n\n## Part I\n")
    assert spec.main(["status", str(book)]) == 1
    assert "{#id}" in capsys.readouterr().err


def test_a_signoff_file_nothing_wrote_a_digest_into_reads_as_unsigned(book, capsys):
    write_spec(book)
    spec.signoff_path(book).write_text("# Sign-off\n\nnothing machine-readable\n", encoding="utf-8")
    assert spec.main(["status", str(book)]) == 1
    assert "not signed off" in capsys.readouterr().out


# --- per-chapter sign-off ------------------------------------------------

# Two chapters, so "did *this* chapter move?" is a question with a wrong
# answer available. A single-chapter spec cannot tell a per-chapter digest
# apart from a whole-book one.
TWO_CHAPTERS = """# Composable Digital Twins

## Part I: Foundations {#part-foundations}

### Chapter 1: What a twin is {#ch-what}

#### The model half {#sec-model}

Establish that a twin is a model plus a live data link.

### Chapter 2: What a twin costs {#ch-cost}

#### The bill {#sec-bill}

Establish who pays, and for which half.
"""


def edit_one_chapter(text):
    """Revise chapter 2's brief and nothing else."""
    return text.replace("Establish who pays", "Establish precisely who pays")


def test_a_chapter_digest_is_taken_over_that_chapter_alone():
    digests = spec.chapter_digests(TWO_CHAPTERS)
    assert sorted(digests) == ["ch-cost", "ch-what"]
    after = spec.chapter_digests(edit_one_chapter(TWO_CHAPTERS))
    assert after["ch-cost"] != digests["ch-cost"]
    assert after["ch-what"] == digests["ch-what"]


def test_sign_records_a_digest_for_every_chapter(book):
    write_spec(book, TWO_CHAPTERS)
    spec.main(["sign", str(book)])
    assert spec.recorded_chapter_digests(book) == spec.chapter_digests(TWO_CHAPTERS)


def test_a_signoff_without_chapter_lines_records_nothing_per_chapter(book):
    """The retrofitted books already on disk: signed before this existed."""
    write_spec(book, TWO_CHAPTERS)
    spec.signoff_path(book).write_text(
        f"# Sign-off\n\n- spec digest: `{spec.digest(TWO_CHAPTERS)}`\n", encoding="utf-8"
    )
    assert spec.recorded_chapter_digests(book) == {}


def test_a_part_after_the_last_chapter_closes_that_chapters_span():
    """A part heading ends the chapter above it, so the last chapter is
    recorded even when nothing follows it but a `##`."""
    digests = spec.chapter_digests(TWO_CHAPTERS + "\n## Part II: Later {#part-later}\n")
    assert sorted(digests) == ["ch-cost", "ch-what"]
    assert digests["ch-what"] == spec.chapter_digests(TWO_CHAPTERS)["ch-what"]


def test_status_says_which_chapter_left_the_outline(book, capsys):
    write_spec(book, TWO_CHAPTERS)
    spec.main(["sign", str(book)])
    write_spec(book, TWO_CHAPTERS[: TWO_CHAPTERS.index("### Chapter 2")])
    capsys.readouterr()
    assert spec.main(["status", str(book)]) == 1
    assert "no longer in the outline: ch-cost" in capsys.readouterr().out


def test_status_says_so_when_the_edit_is_outside_every_chapter(book, capsys):
    """A preamble edit moves the file's digest but no chapter's. Saying
    that is the difference between "re-read fifteen chapters" and
    "re-approve; nothing you wrote has moved"."""
    write_spec(book, TWO_CHAPTERS)
    spec.main(["sign", str(book)])
    write_spec(book, TWO_CHAPTERS.replace("# Composable Digital Twins", "# Composable Twins"))
    capsys.readouterr()
    assert spec.main(["status", str(book)]) == 1
    assert "no chapter changed" in capsys.readouterr().out


def test_status_names_no_chapters_for_a_signoff_written_before_they_existed(book, capsys):
    write_spec(book, TWO_CHAPTERS)
    spec.signoff_path(book).parent.mkdir(parents=True, exist_ok=True)
    spec.signoff_path(book).write_text(
        f"# Sign-off\n\n- spec digest: `{spec.digest(TWO_CHAPTERS)}`\n", encoding="utf-8"
    )
    write_spec(book, edit_one_chapter(TWO_CHAPTERS))
    capsys.readouterr()
    assert spec.main(["status", str(book)]) == 1
    out = capsys.readouterr().out
    assert "changed since sign-off" in out
    # Nothing per-chapter is claimed either way: the file on disk records
    # no chapter digests, so there is no finer answer to give.
    assert "chapters changed:" not in out
    assert "no chapter changed" not in out


def test_status_names_only_the_chapter_that_moved(book, capsys):
    write_spec(book, TWO_CHAPTERS)
    spec.main(["sign", str(book)])
    write_spec(book, edit_one_chapter(TWO_CHAPTERS))
    capsys.readouterr()
    assert spec.main(["status", str(book)]) == 1
    out = capsys.readouterr().out
    assert "ch-cost" in out
    assert "ch-what" not in out


# --- the entry point -----------------------------------------------------


def test_the_verb_is_reachable_through_the_drafting_layers_front_door(book, capsys):
    from chitragupta import draft

    write_spec(book)
    assert draft.main(["spec", "show", str(book)]) == 0
    assert "Composable Digital Twins" in capsys.readouterr().out


def test_no_subcommand_is_a_malformed_invocation():
    with pytest.raises(SystemExit) as exit_info:
        spec.main([])
    assert exit_info.value.code == 2
