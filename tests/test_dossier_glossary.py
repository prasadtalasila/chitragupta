"""`scope.md`'s `## Glossary`, read as entries with their symbols, and the
bullets that are not in the shape (#1138).

Every off-format fixture below is a bullet the real digital-twins book's
dossiers hold, quoted from them rather than invented: the colon form, a
qualifier after the bold, a qualifier inside it, a symbol outside the
bold, several terms in one bullet, a symbol with no brackets, and an
"as before" definition. A guard is tested against the exact shape it was
blind to.
"""

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


# --- the shapes that are read -------------------------------------------


def test_a_term_with_no_symbol(draft):
    write_glossary(draft, "- **Sensor** -- a component that turns a quantity into a number.")
    (entry,) = _glossary.glossary_entries(draft)
    assert (entry.term, entry.symbol) == ("Sensor", None)
    assert entry.definition == "a component that turns a quantity into a number."


def test_a_term_with_a_symbol_in_the_slot(draft):
    write_glossary(draft, "- **Baseline** (`M_0`) -- the measured present-day value.")
    (entry,) = _glossary.glossary_entries(draft)
    assert (entry.term, entry.symbol) == ("Baseline", "M_0")


def test_the_symbol_inside_the_bold_is_still_read(draft):
    write_glossary(draft, "- **Baseline (`M_0`)** -- the measured present-day value.")
    (entry,) = _glossary.glossary_entries(draft)
    assert (entry.term, entry.symbol) == ("Baseline", "M_0")


def test_a_symbol_on_its_own(draft):
    write_glossary(draft, "- **`x_k`** -- the state at step k.")
    (entry,) = _glossary.glossary_entries(draft)
    assert entry.symbol == "x_k"
    assert entry.name is None


def test_an_abbreviation_in_brackets_is_part_of_the_name(draft):
    write_glossary(draft, "- **Digital shadow (DS)** -- an automated flow from PT to DO.")
    (entry,) = _glossary.glossary_entries(draft)
    assert (entry.term, entry.symbol) == ("Digital shadow (DS)", None)


def test_a_definition_wraps_onto_indented_lines(draft):
    write_glossary(
        draft,
        "- **Twin state** -- the digital object's current best\n"
        "  estimate of the physical twin's condition.",
    )
    (entry,) = _glossary.glossary_entries(draft)
    assert "estimate of the physical twin's condition." in entry.definition


def test_a_definition_ends_at_a_line_at_the_margin(draft):
    """The old reading ran to the next *matching* bullet, so an
    off-format bullet after a good one was printed inside its
    definition."""
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
    """`glossary_terms()` keyed ``Baseline (`M_0`)`` before the split;
    the acronym checks print the key, so the change is pinned."""
    write_glossary(draft, "- **Baseline (`M_0`)** -- the measured value.")
    assert dossier.glossary_terms(draft) == {"Baseline": "the measured value."}


# --- what is a problem ---------------------------------------------------

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
        "- **Sensor** -- a component.\n- **Baseline** (`M_0`) -- a value.\n- **`x_k`** -- a state.",
    )
    assert _glossary.glossary_problems(draft) == []


# --- a glossary that is not there ---------------------------------------


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
    """The worked example lives in an HTML comment, which is not read."""
    assert _glossary.has_glossary(draft) is True
    assert _glossary.glossary_entries(draft) == []
    assert _glossary.glossary_problems(draft) == []


def test_the_template_shows_the_shape_it_asks_for(draft):
    scope = (dossier.dossier_dir(draft) / "scope.md").read_text(encoding="utf-8")
    assert "- **Baseline** (`M_0`) -- " in scope
    assert 'no "as before"' in scope


def test_the_digest_line_stamp_appends_is_not_a_glossary_bullet(draft):
    """`dossier stamp` appends `- draft digest:` at the end of a scope.md
    that lacks one, which puts it under `## Glossary`, the last section.
    Two of the real book's eight dossiers hold exactly this."""
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
    """What row e becomes once only its first colon is rewritten: the
    shape matches, and one bullet still defines two terms."""
    write_glossary(draft, bullet)
    (problem,) = _glossary.glossary_problems(draft)
    assert "one term per bullet" in problem.reason


def test_bold_inside_a_definition_that_defines_nothing_is_fine(draft):
    write_glossary(draft, "- **Physical twin** -- the chapter says **actual twin**, borrowed.")
    assert _glossary.glossary_problems(draft) == []
