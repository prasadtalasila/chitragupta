"""Front matter, appendices and back matter in a book's outline (#1137).

Three part ids are reserved, each with one legal position, and four
chapter ids name pages the assembler generates rather than prose anyone
writes. What is pinned here is that a misplaced one is a parse problem
named by its id -- a book whose `{#back}` sits in the middle would
otherwise assemble its glossary between two chapters -- and that the
default outline `spec init` writes obeys every rule it introduces.
"""

from chitragupta import spec

FULL = """# Composable Twins

- author: Prasad Talasila
- reader: practising engineers

## Front matter {#front}

### Preface {#preface}

### List of Figures {#figures}

## Part I {#part-i}

### What a twin is {#ch-what}

#### The model half {#sec-model}

#### The data half {#sec-data}

## Appendices {#appendices}

### Installing the toolchain {#app-install}

## Back matter {#back}

### Glossary {#glossary}

### List of Symbols {#symbols}

### List of Tables {#tables}

### About the author {#about}
"""


def _problems(text: str) -> list[str]:
    return spec.parse(text)["problems"]


def test_a_book_with_all_three_reserved_parts_in_place_parses_clean():
    parsed = spec.parse(FULL)
    assert parsed["problems"] == []
    assert parsed["author"] == "Prasad Talasila"


def test_each_entry_knows_which_matter_it_belongs_to():
    by_id = {entry["id"]: entry for entry in spec.parse(FULL)["units"]}
    assert spec.matter(by_id["preface"]) == "front"
    assert spec.matter(by_id["front"]) == "front"
    assert spec.matter(by_id["app-install"]) == "appendices"
    assert spec.matter(by_id["about"]) == "back"
    assert spec.matter(by_id["sec-model"]) is None
    assert spec.matter(by_id["ch-what"]) is None


def test_generated_pages_are_named_as_such():
    assert spec.GENERATED == ("glossary", "symbols", "figures", "tables")


def test_front_matter_after_a_part_is_a_problem():
    text = FULL.replace("## Front matter {#front}\n\n### Preface {#preface}\n\n", "")
    text = text.replace(
        "## Appendices", "## Front matter {#front}\n\n### Preface {#preface}\n\n## Appendices"
    )
    assert any("`front`" in problem and "first part" in problem for problem in _problems(text))


def test_back_matter_before_another_part_is_a_problem():
    text = FULL + "\n## Part II {#part-ii}\n\n### Later {#ch-later}\n"
    assert any("`back`" in problem and "last part" in problem for problem in _problems(text))


def test_appendices_before_an_ordinary_part_is_a_problem():
    text = FULL.replace(
        "## Back matter {#back}",
        "## Part II {#part-ii}\n\n### Later {#ch-later}\n\n## Back matter {#back}",
    )
    assert any("`appendices`" in problem for problem in _problems(text))


def test_a_generated_page_inside_an_ordinary_part_is_a_problem():
    text = FULL.replace(
        "### What a twin is {#ch-what}",
        "### Glossary {#glossary-x}\n\n### What a twin is {#ch-what}",
    )
    assert _problems(text) == []  # an ordinary id that only looks like one is fine
    text = FULL.replace("### List of Tables {#tables}\n\n", "").replace(
        "### What a twin is {#ch-what}",
        "### List of Tables {#tables}\n\n### What a twin is {#ch-what}",
    )
    assert any("`tables`" in problem and "generates" in problem for problem in _problems(text))


def test_a_generated_page_cannot_have_sections():
    text = FULL.replace(
        "### Glossary {#glossary}\n", "### Glossary {#glossary}\n\n#### Terms {#sec-terms}\n"
    )
    assert any("`glossary`" in problem and "no sections" in problem for problem in _problems(text))


def test_a_reserved_id_at_the_wrong_level_is_a_problem():
    text = FULL.replace("#### The data half {#sec-data}", "#### The data half {#back}")
    assert any("`back`" in problem and "`##`" in problem for problem in _problems(text))
    text = FULL.replace("## Part I {#part-i}", "## Glossary {#glossary}")
    assert any("`glossary`" in problem for problem in _problems(text))


def test_an_outline_with_no_reserved_parts_is_unchanged():
    text = "# T\n\n## Part I {#part-i}\n\n### One {#ch-1}\n\n#### A {#sec-a}\n"
    parsed = spec.parse(text)
    assert parsed["problems"] == []
    assert parsed["author"] is None


def test_the_author_line_is_read_only_from_the_preamble():
    text = "# T\n\n## Part I {#part-i}\n\n### One {#ch-1}\n\n- author: Not The Author\n"
    assert spec.parse(text)["author"] is None
    text = "# T\n\n-   author:   Jane  Doe  \n\n## Part I {#part-i}\n\n### One {#ch-1}\n"
    assert spec.parse(text)["author"] == "Jane  Doe"


def test_the_author_line_inside_a_fence_or_before_the_title_is_not_read():
    text = (
        "- author: Stray\n\n# T\n\n```\n- author: Fenced\n```\n\n"
        "## Part I {#part-i}\n\n### One {#ch-1}\n"
    )
    assert spec.parse(text)["author"] is None


# --- what `spec init`, `sign` and `show` do with them ----------------------


def test_init_writes_an_outline_with_the_matter_and_the_two_files_the_author_owns(
    book_dir, isolated_config, capsys
):
    assert (
        spec.main(["init", str(book_dir), "--title", "Composable Twins", "--author", "Jane Doe"])
        == 0
    )
    parsed = spec.parse(spec.spec_path(book_dir).read_text(encoding="utf-8"))
    assert parsed["problems"] == []
    assert parsed["author"] == "Jane Doe"
    ids = [entry["id"] for entry in parsed["units"]]
    assert ids[:2] == ["front", "preface"]
    assert ids[-5:] == ["back", "glossary", "symbols", "figures", "tables"]

    preface = book_dir / "preface.md"
    copyright_page = spec.spec_dir(book_dir) / "copyright.tex"
    assert preface.read_text(encoding="utf-8").startswith("# Preface\n")
    assert "All rights reserved." in copyright_page.read_text(encoding="utf-8")
    out = capsys.readouterr().out
    assert f"Wrote {preface}: the preface is yours to write." in out
    assert f"Wrote {copyright_page}: the copyright page is yours to edit." in out


def test_init_without_an_author_writes_no_author_line(book_dir):
    spec.main(["init", str(book_dir)])
    assert spec.parse(spec.spec_path(book_dir).read_text(encoding="utf-8"))["author"] is None


def test_init_never_overwrites_a_preface_or_copyright_page_already_there(book_dir, capsys):
    book_dir.mkdir(parents=True, exist_ok=True)
    (book_dir / "preface.md").write_text("# Preface\n\nMine.\n", encoding="utf-8")
    copyright_page = spec.spec_dir(book_dir) / "copyright.tex"
    copyright_page.parent.mkdir(parents=True, exist_ok=True)
    copyright_page.write_text("Mine.\n", encoding="utf-8")
    assert spec.main(["init", str(book_dir)]) == 0
    assert (book_dir / "preface.md").read_text(encoding="utf-8") == "# Preface\n\nMine.\n"
    assert copyright_page.read_text(encoding="utf-8") == "Mine.\n"
    assert "yours to" not in capsys.readouterr().out


def test_the_first_sign_off_writes_the_year_and_later_ones_leave_it(book_dir, capsys, monkeypatch):
    from chitragupta.spec import _scaffold

    spec.main(["init", str(book_dir)])
    copyright_page = spec.spec_dir(book_dir) / "copyright.tex"
    assert "<year>" in copyright_page.read_text(encoding="utf-8")
    monkeypatch.setattr(_scaffold, "_this_year", lambda: 2026)
    capsys.readouterr()
    assert spec.main(["sign", str(book_dir)]) == 0
    text = copyright_page.read_text(encoding="utf-8")
    assert "<year>" not in text and r"\copyright\ 2026 \BookAuthor" in text
    assert (
        f"Wrote the year 2026 into {copyright_page}; change it there by hand from now on."
        in capsys.readouterr().out
    )

    monkeypatch.setattr(_scaffold, "_this_year", lambda: 2027)
    spec.main(["sign", str(book_dir)])
    assert copyright_page.read_text(encoding="utf-8") == text
    assert "Wrote the year" not in capsys.readouterr().out


def test_signing_a_book_with_no_copyright_page_creates_none(book_dir):
    spec.main(["init", str(book_dir)])
    copyright_page = spec.spec_dir(book_dir) / "copyright.tex"
    copyright_page.unlink()
    assert spec.main(["sign", str(book_dir)]) == 0
    assert not copyright_page.exists()


def test_show_prints_the_author_under_the_title(book_dir, capsys):
    spec.main(["init", str(book_dir), "--title", "Composable Twins", "--author", "Jane Doe"])
    capsys.readouterr()
    spec.main(["show", str(book_dir)])
    assert capsys.readouterr().out.startswith("Composable Twins\n  author: Jane Doe\n")


def test_the_year_is_the_calendar_year_the_sign_off_runs_in():
    import datetime

    from chitragupta.spec import _scaffold

    assert _scaffold._this_year() == datetime.date.today().year
