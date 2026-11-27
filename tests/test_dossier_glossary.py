import pytest

from chitragupta import config, dossier
from chitragupta.dossier import _draft_fingerprint, _glossary


@pytest.fixture
def draft(isolated_config):
    path = config.DRAFTS_DIR / "book" / "ch-1.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Chapter\n", encoding="utf-8")
    dossier.init(path, "textbook")
    return path


def write_glossary(draft, body: str) -> None:
    scope = dossier.dossier_dir(draft) / "scope.md"
    text = scope.read_text(encoding="utf-8")
    head, _, _ = text.partition("## Glossary")
    scope.write_text(f"{head}## Glossary\n\n{body}\n", encoding="utf-8")


def test_a_term(draft):
    write_glossary(draft, "- **Sensor** -- a component that turns a quantity into a number.")
    (entry,) = _glossary.glossary_entries(draft)
    assert entry.term == "Sensor"
    assert entry.definition == "a component that turns a quantity into a number."


def test_an_abbreviation_in_brackets_is_part_of_the_name(draft):
    write_glossary(draft, "- **Digital shadow (DS)** -- an automated flow from PT to DO.")
    (entry,) = _glossary.glossary_entries(draft)
    assert entry.term == "Digital shadow (DS)"


@pytest.mark.parametrize(
    "bullet",
    [
        "- **Baseline** (`M_0`) -- the measured present-day value.",
        "- **Baseline (`M_0`)** -- the measured present-day value.",
    ],
)
def test_a_symbol_beside_a_term_is_a_problem_naming_its_row(draft, bullet):
    write_glossary(draft, bullet)
    (problem,) = _glossary.glossary_problems(draft)
    assert problem.reason == (
        "symbols live in math.md now: add | `M_0` | **Baseline** | under its "
        "## Symbols and drop the symbol here"
    )
    (entry,) = _glossary.glossary_entries(draft)
    assert entry.term == "Baseline"


def test_a_bullet_that_is_only_a_symbol_is_a_problem_and_no_entry(draft):
    write_glossary(draft, "- **`x_k`** -- the state at step k.")
    (problem,) = _glossary.glossary_problems(draft)
    assert problem.reason == (
        "symbols live in math.md now: add | `x_k` | <its meaning in words> | under its "
        "## Symbols and drop this bullet"
    )
    assert _glossary.glossary_entries(draft) == []


def test_a_definition_wraps_onto_indented_lines(draft):
    write_glossary(
        draft,
        "- **Twin state** -- the digital object's current best\n"
        "  estimate of the physical twin's condition.",
    )
    (entry,) = _glossary.glossary_entries(draft)
    assert "estimate of the physical twin's condition." in entry.definition


def test_a_definition_ends_at_a_line_at_the_margin(draft):
    write_glossary(
        draft,
        "- **Model** -- a description of how something behaves.\n"
        "- **Simulation**: one execution of a model over time.",
    )
    (entry,) = _glossary.glossary_entries(draft)
    assert "Simulation" not in entry.definition


def test_every_definition_of_a_term_is_kept_in_file_order(draft):
    write_glossary(
        draft,
        "- **Solver** -- the program that turns an equation into a trajectory.\n"
        "- **Solver** -- the program that chooses the step and runs the loop.",
    )
    first, second = _glossary.glossary_entries(draft)
    assert first.definition.startswith("the program that turns")
    assert second.definition.startswith("the program that chooses")
    assert second.line > first.line


def test_the_line_is_the_scope_files_own(draft):
    write_glossary(draft, "- **Sensor** -- a component.")
    (entry,) = _glossary.glossary_entries(draft)
    scope = (dossier.dossier_dir(draft) / "scope.md").read_text(encoding="utf-8")
    assert scope.splitlines()[entry.line - 1].startswith("- **Sensor**")


def test_the_dict_view_keys_a_bold_symbol_by_its_name(draft):
    write_glossary(draft, "- **Baseline (`M_0`)** -- the measured value.")
    assert dossier.glossary_terms(draft) == {"Baseline": "the measured value."}


OFF_FORMAT = [
    "- **Residual**: the difference between what the sensor reports and the model.",
    "- **Digital twin (DT)**, definition for the rest of the book: a DO paired with a PT.",
    "- **Digital twin (DT), working definition for Part I**: software that keeps a model.",
    "- **Baseline** (`M_0`): the measured present-day value of the value metric.",
    "- **Gain** (`k`), **cap** (`V_max`), **check interval** (`T_c`): the controller's knobs.",
    "- **Step size** `h`, **macro step** `H`: the time one step advances.",
    "- **Physical twin (PT)**: as before, and in this chapter read broadly.",
]


@pytest.mark.parametrize("bullet", OFF_FORMAT)
def test_a_real_off_format_bullet_is_a_problem(draft, bullet):
    write_glossary(draft, bullet)
    (problem,) = _glossary.glossary_problems(draft)
    assert problem.text == bullet
    assert "- **Term** -- definition" in problem.reason
    assert _glossary.glossary_entries(draft) == []


def test_a_bullet_with_no_definition_is_a_problem(draft):
    write_glossary(draft, "- **DTaaS** --\n- **FMU** -- Functional Mock-up Unit.")
    (problem,) = _glossary.glossary_problems(draft)
    assert "no definition" in problem.reason
    assert dossier.glossary_terms(draft) == {"FMU": "Functional Mock-up Unit."}


@pytest.mark.parametrize(
    "citation", ["as argued in [@smith_example_2024]", r"as argued by \citep{smith_example_2024}"]
)
def test_a_citekey_in_a_definition_is_a_problem(draft, citation):
    write_glossary(draft, f"- **Model** -- a description, {citation}.")
    (problem,) = _glossary.glossary_problems(draft)
    assert "citekey" in problem.reason


def test_a_paragraph_is_not_a_bullet(draft):
    write_glossary(
        draft,
        "Chapters 1 and 2's terms carry forward unchanged (PT, DT, residual).\n\n"
        "- **Model** -- a description of how something behaves.",
    )
    assert _glossary.glossary_problems(draft) == []


def test_a_well_formed_glossary_has_no_problems(draft):
    write_glossary(
        draft,
        "- **Sensor** -- a component.\n- **Baseline** -- a value.\n"
        "- **Digital twin (DT)** -- a DO.",
    )
    assert _glossary.glossary_problems(draft) == []


def test_no_dossier_means_no_glossary(isolated_config):
    draft = config.DRAFTS_DIR / "book" / "nowhere.md"
    assert _glossary.has_glossary(draft) is False
    assert _glossary.glossary_entries(draft) == []
    assert _glossary.glossary_problems(draft) == []


def test_a_scope_without_the_heading_has_no_glossary(draft):
    scope = dossier.dossier_dir(draft) / "scope.md"
    scope.write_text(scope.read_text().replace("## Glossary", "## Not a glossary"))
    assert _glossary.has_glossary(draft) is False


def test_the_shipped_template_has_a_glossary_and_no_entries_or_problems(draft):
    assert _glossary.has_glossary(draft) is True
    assert _glossary.glossary_entries(draft) == []
    assert _glossary.glossary_problems(draft) == []


def test_the_template_shows_the_shape_it_asks_for(draft):
    scope = (dossier.dossier_dir(draft) / "scope.md").read_text(encoding="utf-8")
    assert "- **Baseline** -- " in scope and "(`M_0`)" not in scope
    assert "| `M_0` | **Baseline** |" in scope
    assert 'no "as before"' in scope


def test_the_digest_line_stamp_appends_is_not_a_glossary_bullet(draft):
    write_glossary(draft, "- **Sensor** -- a component.")
    scope = dossier.dossier_dir(draft) / "scope.md"
    scope.write_text(
        scope.read_text(encoding="utf-8").replace("- draft digest: not recorded", "- old: x")
    )
    _draft_fingerprint.stamp(draft)
    assert "- draft digest: `" in scope.read_text(encoding="utf-8").split("## Glossary")[1]
    assert _glossary.glossary_problems(draft) == []
    assert [entry.term for entry in _glossary.glossary_entries(draft)] == ["Sensor"]


@pytest.mark.parametrize(
    "bullet",
    [
        "- **Solver** -- the part that advances one step. **Event scheduler**: the part"
        " that advances to the next event.",
        "- **Distribution** -- a named family; **uniform** -- flat on an interval.",
    ],
)
def test_a_second_term_inside_a_definition_is_a_problem(draft, bullet):
    write_glossary(draft, bullet)
    (problem,) = _glossary.glossary_problems(draft)
    assert "one term per bullet" in problem.reason


def test_bold_inside_a_definition_that_defines_nothing_is_fine(draft):
    write_glossary(draft, "- **Physical twin** -- the chapter says **actual twin**, borrowed.")
    assert _glossary.glossary_problems(draft) == []


def test_a_definition_continued_at_the_margin_is_a_problem(draft):
    write_glossary(draft, "- **Term** -- a long definition that\ncontinues at the margin.")
    (problem,) = _glossary.glossary_problems(draft)
    assert "indent" in problem.reason


def test_a_maths_term_is_a_problem_rather_than_vanishing(draft):
    write_glossary(draft, "- **$x$** -- a maths term.")
    (problem,) = _glossary.glossary_problems(draft)
    assert "math.md's ## Symbols" in problem.reason


@pytest.mark.parametrize("marker", ["*", "+"])
def test_a_bullet_not_written_with_a_hyphen_says_so(draft, marker):
    write_glossary(draft, f"{marker} **Term** -- a definition.")
    (problem,) = _glossary.glossary_problems(draft)
    assert "starts with `-`" in problem.reason


def test_a_draft_outside_content_drafts_still_raises_for_the_acronym_checks(tmp_path):
    with pytest.raises(dossier.DossierError):
        dossier.glossary_terms(tmp_path / "stray.md")
