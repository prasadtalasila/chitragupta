"""Function and module size, enforced as a ratchet over this repo's own tree.

[docs/CODE-STANDARDS.md](../docs/CODE-STANDARDS.md) states the two rules
this file enforces -- C1, at most 25 statements per function, and C2, at
most 250 lines of code per module -- and owns the reasoning. Two parts of
that reasoning are load-bearing here and are repeated rather than linked,
because someone reading a failure will be reading this file:

**Statements, not physical lines.** This repository requires *why*-comments
(CODE-STANDARDS.md's Override 1: rationale, rejected alternatives, the bug
that produced the current shape). Counting physical lines would put that
requirement in direct conflict with a size limit and would reward deleting
the rationale -- the one edit this project least wants. Counting statements
measures how much a function *does* and is blind to how well it is
explained. The difference is not cosmetic: at 5.7.1, 128 functions in
`chitragupta/` exceeded 25 physical lines and 26 exceeded 25 statements.

**A ratchet, not a wall.** Both rules are violated by code that exists
today, and a rule that fails on the day it lands is a rule that gets
switched off. Today's offenders are frozen in the register. Anything *not*
in it that crosses a threshold fails; anything in it that comes back
*under* its threshold also fails, saying to delete the entry. So the
register can only shrink, and every shrink is a visible diff. It is a debt
list, not an allowance.

What the ratchet deliberately does not do is cap the growth of a module
already on the C2 register. Pinning each to today's exact size would fail
on every ordinary edit and would be turned off within a week; growth in a
registered module is caught by C1 on its functions, and by review.

**Two things moved out of this file in issue 431, and neither changed.**
The scan itself is now `scripts/code_standards.py`, because the
edit-time hook needs a hand-runnable command and `tests/` does not ship
(see that module's docstring). The register is now
`code-standards-register.toml`, for the same reason and with its trailing
counts promoted to real values, since `tomllib` discards comments. **This
file is still the authority**: it is what fails a build, and every
assertion below is the one it made before the move.
"""

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_scanner():
    """`scripts/code_standards.py`, by path.

    Loaded rather than imported because `scripts/` is not a package and
    is not on `sys.path` -- the same `importlib.util.spec_from_file_location`
    dance `tests/test_check_version_bump.py` and `tests/test_release.py`
    already do for their own `scripts/` module.
    """
    spec = importlib.util.spec_from_file_location(
        "code_standards", REPO_ROOT / "scripts" / "code_standards.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


scan = _load_scanner()

MAX_STATEMENTS = scan.MAX_STATEMENTS
MAX_CODE_LINES = scan.MAX_CODE_LINES
STATEMENT_ROOTS = scan.STATEMENT_ROOTS
CODE_LINE_ROOTS = scan.CODE_LINE_ROOTS

statement_count = scan.statement_count
functions = scan.functions
code_lines = scan.code_lines
long_functions = scan.long_functions
long_files = scan.long_files
_python_files = scan._python_files
_relative = scan._relative

# The register, as this file has always spelled it. Two names rather than
# the scanner's two dicts, because that is what every assertion below and
# `tests/test_technical_debt_scan.py`'s import already read -- the move
# changed where the data lives, not what the ratchet is written against.
_C1_COUNTS, _C2_COUNTS = scan.register()
LEGACY_LONG_FUNCTIONS = set(_C1_COUNTS)
LEGACY_LONG_FILES = set(_C2_COUNTS)


def _new_offenders(found, register):
    return sorted(set(found) - register)


def _fixed_offenders(found, register):
    return sorted(register - set(found))


def test_no_new_function_exceeds_the_statement_limit():
    found = long_functions(STATEMENT_ROOTS)
    new = _new_offenders(found, LEGACY_LONG_FUNCTIONS)
    assert not new, (
        "Functions over the "
        f"{MAX_STATEMENTS}-statement limit that are not in the register:"
        + "".join(f"\n  {name} -- {found[name]} statements" for name in new)
        + "\n\nSplit the function, or -- if it genuinely cannot be split -- say why "
        "in the PR and add it to LEGACY_LONG_FUNCTIONS in this file. Statements, "
        "not lines: comments are free, so this is about what the function does, "
        "not how well it is explained. See docs/CODE-STANDARDS.md."
    )


def test_no_new_module_exceeds_the_code_line_limit():
    found = long_files(CODE_LINE_ROOTS)
    new = _new_offenders(found, LEGACY_LONG_FILES)
    assert not new, (
        f"Modules over the {MAX_CODE_LINES}-code-line limit that are not in the "
        "register:"
        + "".join(f"\n  {name} -- {found[name]} code lines" for name in new)
        + "\n\nA module this long is usually holding more than one responsibility; "
        'see DEVELOPER-AGENTS.md\'s "Module boundaries". Blank lines and comments '
        "are not counted, so this is not a limit on explaining yourself. If the "
        "split is genuinely wrong, add it to LEGACY_LONG_FILES in this file and "
        "say why in the PR. See docs/CODE-STANDARDS.md."
    )


def test_the_function_register_holds_no_entry_that_is_already_fixed():
    """The ratchet's other half, and the reason this is not an amnesty.

    Without it the register is a list that only ever grows stale: a
    function refactored back under the limit would keep its licence to go
    over again, silently, forever.
    """
    fixed = _fixed_offenders(long_functions(STATEMENT_ROOTS), LEGACY_LONG_FUNCTIONS)
    assert not fixed, (
        "These are now within the limit -- delete them from "
        "LEGACY_LONG_FUNCTIONS:" + "".join(f"\n  {name}" for name in fixed)
    )


def test_the_file_register_holds_no_entry_that_is_already_fixed():
    fixed = _fixed_offenders(long_files(CODE_LINE_ROOTS), LEGACY_LONG_FILES)
    assert not fixed, (
        "These are now within the limit -- delete them from LEGACY_LONG_FILES:"
        + "".join(f"\n  {name}" for name in fixed)
    )


def test_the_scan_reaches_the_source_tree():
    """Non-vacuity: a glob that silently matched nothing would make every
    assertion above pass for the wrong reason, forever."""
    scanned = {_relative(path) for path in _python_files(STATEMENT_ROOTS)}
    # One per root, so a root silently dropped from STATEMENT_ROOTS fails
    # here rather than quietly halving what the ratchet covers.
    assert "chitragupta/sync.py" in scanned
    assert "scripts/release.py" in scanned
    assert "tests/test_code_standards_scan.py" in scanned
    # Two *nested* modules, which is the specific thing the glob has to get
    # right: `**/*.py` degraded to `*.py` still finds all three paths above
    # -- they sit directly in their roots -- while silently dropping every
    # module in chitragupta/enrich/ and chitragupta/review/, half of which are on the
    # register. A count alone would only imply this; these name it.
    assert "chitragupta/enrich/docling_parse.py" in scanned
    assert "chitragupta/review/citation_provenance.py" in scanned
    assert not any(name.startswith("bench/") for name in scanned)


def test_the_registers_name_only_paths_that_still_exist():
    """A renamed module leaves an entry behind that can never be delisted,
    so the register would quietly stop covering it."""
    paths = {name.split("::")[0] for name in LEGACY_LONG_FUNCTIONS} | LEGACY_LONG_FILES
    missing = sorted(name for name in paths if not (REPO_ROOT / name).exists())
    assert not missing, f"register entries for files that no longer exist: {missing}"


def _recorded_counts():
    """`{register entry: the count recorded beside it}`.

    Read from `code-standards-register.toml`'s own values. It was a
    regex over this file's trailing `# 32` comments until issue 431 --
    the comment was what a reader saw when deciding which debt to take
    first, so the comment had to be true. `tomllib` discards comments, so
    the move promoted the number to a key; it is still the thing a reader
    sees, and this test is still what keeps it honest.
    """
    return {**_C1_COUNTS, **_C2_COUNTS}


def test_every_registered_offender_records_its_current_count():
    """The registers cannot drift; the numbers written beside them can.

    They already did. A merge that changed `verbatim_check.py` left three
    of these comments describing the previous release's code, and nothing
    noticed -- the entries were still offenders, so both ratchet tests
    stayed green. Since the whole point of the trailing count is to show
    how large each debt is, a stale one is worse than none.
    """
    counts = long_functions(STATEMENT_ROOTS) | long_files(CODE_LINE_ROOTS)
    recorded = _recorded_counts()
    assert set(recorded) == set(counts), (
        "the register comments and the registers themselves disagree about which entries exist"
    )
    drifted = {name: (was, counts[name]) for name, was in recorded.items() if was != counts[name]}
    assert not drifted, (
        "register entries whose recorded count is stale (recorded -> actual):"
        + "".join(f"\n  {n}: {w} -> {a}" for n, (w, a) in sorted(drifted.items()))
        + "\n\nUpdate the trailing comment to the current number. Ordering in the "
        "register is worst-first, so check whether the entry also needs moving."
    )


def test_the_registers_are_the_size_this_document_says():
    """CODE-STANDARDS.md quotes both register sizes in prose.

    The registers are checked on every run and cannot drift; the sentence
    describing them can, and did -- it said 27 functions against a
    register of 28. Pinning the two numbers to the two registers is the
    narrow form of the doc-drift detector that document's build order
    asks for.
    """
    text = (REPO_ROOT / "docs" / "CODE-STANDARDS.md").read_text(encoding="utf-8")
    expected = (
        f"**{len(LEGACY_LONG_FUNCTIONS)}\nfunctions** and **{len(LEGACY_LONG_FILES)} modules**"
    )
    assert " ".join(expected.split()) in " ".join(text.split()), (
        "docs/CODE-STANDARDS.md no longer states the register sizes correctly. "
        f"They are now {len(LEGACY_LONG_FUNCTIONS)} functions and "
        f"{len(LEGACY_LONG_FILES)} modules."
    )


def test_this_scanner_obeys_its_own_statement_limit():
    """The check that would be embarrassing to fail.

    Both files, since issue 431 split them: the scanner in `scripts/`,
    which is also covered by the whole-tree scan above, and this one,
    which is not -- `STATEMENT_ROOTS` includes `tests`, so it is, but
    asserting it here keeps the embarrassment check readable as one.
    """
    for path in (REPO_ROOT / "scripts" / "code_standards.py", Path(__file__)):
        source = path.read_text(encoding="utf-8")
        assert all(count <= MAX_STATEMENTS for _, count in functions(source)), path


def test_a_statement_is_counted_per_statement_not_per_line():
    """The whole basis of C1, on a synthetic case: same statements, very
    different physical length."""
    terse = "def f():\n    a = 1\n    b = 2\n    return a + b\n"
    explained = (
        "def f():\n"
        + "    # why a is 1: "
        + "x" * 40
        + "\n" * 1
        + "    a = 1\n"
        + "    # why b is 2, at length:\n" * 30
        + "    b = 2\n"
        + "    return a + b\n"
    )
    assert functions(terse) == functions(explained) == [("f", 3)]
    assert len(explained.splitlines()) > 30


def test_a_nested_function_is_charged_to_itself_not_to_its_parent():
    source = (
        "def outer():\n"
        "    def inner():\n"
        "        a = 1\n"
        "        b = 2\n"
        "        return a + b\n"
        "    return inner\n"
    )
    # `outer` does two things: define `inner`, and return it.
    assert dict(functions(source)) == {"outer": 2, "outer.inner": 3}


def test_the_methods_of_a_nested_class_are_not_charged_to_the_enclosing_function():
    """The bug the set-subtraction version of `statement_count` had.

    A method of a nested class is itself a nested definition, so it
    survived a skip set built by subtracting nested nodes from the walk --
    and `outer` below counted 4 rather than 2. The count of a function
    that merely declares a class must not move when a method is added to
    that class.
    """
    source = (
        "def outer():\n"
        "    class C:\n"
        "        def m(self):\n"
        "            pass\n"
        "        def n(self):\n"
        "            pass\n"
        "    return C\n"
    )
    # `outer` does two things: define `C`, and return it.
    assert dict(functions(source)) == {"outer": 2, "outer.C.m": 1, "outer.C.n": 1}


def test_a_method_is_counted_and_not_charged_to_its_class_body():
    source = "class C:\n    def m(self):\n        a = 1\n        return a\n"
    assert dict(functions(source)) == {"C.m": 2}


def test_two_same_named_methods_in_one_module_stay_distinct():
    """The collision `long_functions()`'s dict would otherwise hide.

    Keyed on the bare name, the second of these would overwrite the first
    -- so a colliding pair would report as one offender, and a register
    entry for one would license a different function of the same name
    added to that module later. `chitragupta/pdf_text.py` was the live
    case before #361 split it into a package: it defined `__init__` on
    both `interrupt_guard` and `_AnnotatedStream`.
    """
    source = (
        "class A:\n"
        "    def __init__(self):\n"
        "        self.x = 1\n"
        "class B:\n"
        "    def __init__(self):\n"
        "        self.y = 1\n"
        "        self.z = 2\n"
    )
    assert dict(functions(source)) == {"A.__init__": 1, "B.__init__": 2}


def test_a_function_defined_inside_a_conditional_keeps_its_enclosing_scope():
    """`if`/`try`/`with` are not scopes, so they must not extend the name --
    but they must still be descended into, or the function inside is
    invisible to the scan."""
    source = (
        "class A:\n    if True:\n        def m(self):\n            a = 1\n            return a\n"
    )
    assert dict(functions(source)) == {"A.m": 2}


def test_an_async_function_is_counted():
    assert functions("async def f():\n    a = 1\n    return a\n") == [("f", 2)]


def test_code_lines_ignores_blanks_and_whole_line_comments():
    source = "import os\n\n# a comment\n    # an indented comment\nx = 1\n"
    assert code_lines(source) == 2


def test_code_lines_counts_a_trailing_comment_on_a_real_line():
    """Only a *whole-line* comment is free. A line with code on it counts,
    however much explanation follows it."""
    assert code_lines("x = 1  # why x is 1\n") == 1


def test_a_new_offender_is_reported_and_a_registered_one_is_not():
    found = {"a.py::f": 40, "b.py::g": 30}
    assert _new_offenders(found, {"b.py::g"}) == ["a.py::f"]
    assert _fixed_offenders(found, {"b.py::g"}) == []


def test_a_registered_offender_that_no_longer_offends_is_reported():
    assert _fixed_offenders({"a.py::f": 40}, {"a.py::f", "b.py::g"}) == ["b.py::g"]
