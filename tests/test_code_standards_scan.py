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
`src/` exceed 25 physical lines and 26 exceed 25 statements.

**A ratchet, not a wall.** Both rules are violated by code that exists
today, and a rule that fails on the day it lands is a rule that gets
switched off. Today's offenders are frozen in the two registers below.
Anything *not* in a register that crosses a threshold fails; anything in a
register that comes back *under* its threshold also fails, saying to delete
the entry. So the register can only shrink, and every shrink is a visible
diff. It is a debt list, not an allowance.

What the ratchet deliberately does not do is cap the growth of a module
already on the C2 register. Pinning each to today's exact size would fail
on every ordinary edit and would be turned off within a week; growth in a
registered module is caught by C1 on its functions, and by review.
"""

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

MAX_STATEMENTS = 25
MAX_CODE_LINES = 250

# C1 covers the tests, C2 does not -- see CODE-STANDARDS.md. In short: the
# tests already hold C1 (1 offender in 1926 functions), so including them
# locks in a bar that is met; a test module's *length* tracks the surface
# of the module under test rather than a count of responsibilities, so C2
# would push tests into new files for no reason other than the cap.
#
# `bench/` is out of scope for both: it is the parser measurement harness,
# it is one of the trees scripts/release.py excludes from the release
# archive, and its scripts are one-shot analysis code whose `main()` reads
# top to bottom on purpose.
STATEMENT_ROOTS = ("src", "scripts", "tests")
CODE_LINE_ROOTS = ("src", "scripts")

# Every offender as of 5.7.1 that remains, frozen. Ordered worst-first,
# with today's count in a trailing comment so the size of each debt is
# visible without running anything. The original register held 28
# functions, worst of them src/sync.py::run at 117 statements -- the
# 5.8.x SonarCloud-debt series split the worst offenders and delisted
# each as it came back under the limit.
LEGACY_LONG_FUNCTIONS = {
    "src/dossier.py::main",  # 42
    "src/enrich/embed_index.py::build_index",  # 40
    "src/enrich/docling_parse.py::parse_doc",  # 36
    "src/sync.py::_parse_parallel",  # 33
    "src/enrich/topic_model.py::run_topic_model",  # 32
    "src/render_output.py::render",  # 31
    "tests/test_release.py::make_repo",  # 30
    "src/retrieval.py::_windows",  # 28
    "src/overlap_index.py::build_corpus_index",  # 27
    "src/overlap_skipgram.py::build_corpus_index",  # 27
    "src/review/verbatim_check.py::render_scan_markdown",  # 27
    "scripts/release.py::build_release",  # 26
}

# Ten of these grew by a line or six when pylint's `line-too-long` was
# enabled: wrapping a 105-character line necessarily spends a physical
# line to save a column, so C0301 and C2 pull against each other and C0301
# won. The trade is deliberate and one-way -- the wraps are permanent,
# the growth is bounded by the 34 lines that were over 100 columns, and
# no file entered the register that was not already on it.
LEGACY_LONG_FILES = {
    "src/dossier.py",  # 1667
    "src/review/verbatim_check.py",  # 1588
    "src/pdf_text.py",  # 1001
    "src/enrich/docling_parse.py",  # 522
    "src/overlap_index.py",  # 492
    "src/render_output.py",  # 456
    "src/sync.py",  # 519
    "src/review/citation_provenance.py",  # 392
    "src/ledger.py",  # 395
    "src/retrieval.py",  # 376
    "src/references.py",  # 366
    "src/overlap_skipgram.py",  # 305
    "src/config.py",  # 292
}


def statement_count(node):
    """Statements in a function body, not descending into nested definitions.

    A nested `def` is reached by `functions()` in its own right and checked
    on its own account, so counting its body here too would charge it to
    both and make an inner helper look like a way to fail its parent. The
    nested `def` or `class` statement itself still counts as one statement
    of the parent, which is correct -- declaring it is something the parent
    does.

    Stopping the descent is what makes that true at any depth. An earlier
    version subtracted a set of nested nodes from the walk instead, which
    got a nested *class* wrong: its methods were themselves nested
    definitions, so they survived the subtraction and were charged to the
    enclosing function. The parent's count then moved when a method was
    added to a class it merely declared.
    """
    count = 0
    pending = list(ast.iter_child_nodes(node))
    while pending:
        child = pending.pop()
        if isinstance(child, ast.stmt):
            count += 1
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        pending.extend(ast.iter_child_nodes(child))
    return count


def _definitions(node, prefix):
    """`(qualified_name, statement_count)` for every function under `node`.

    A class or an enclosing function extends the prefix; any other
    statement -- `if`, `try`, `with` -- leaves it alone, so a conditionally
    defined function is still found and still named for its real scope.
    """
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = prefix + child.name
            yield name, statement_count(child)
            yield from _definitions(child, name + ".")
        elif isinstance(child, ast.ClassDef):
            yield from _definitions(child, prefix + child.name + ".")
        else:
            yield from _definitions(child, prefix)


def functions(source):
    """Every function in `source` as `(qualified_name, statement_count)`.

    The caller prefixes the path. Nested and method definitions are
    yielded too -- each is a function someone has to read, and C1 is about
    reading.

    Qualified (`Class.method`, `outer.inner`), not the bare name, because
    the bare name is not unique within a file: `src/pdf_text.py` defines
    `__init__` twice. `long_functions()` keys a dict on this, so a
    collision would drop one offender of a colliding pair -- and, worse,
    would let a register entry for one `main` silently license a *different*
    `main` added to the same module later.
    """
    return list(_definitions(ast.parse(source), ""))


def code_lines(source):
    """Physical lines that are neither blank nor a whole-line comment.

    Deliberately counts docstrings, which are neither. Stripping them
    would need the rule to distinguish a module's prose header from a
    string constant, and the point of C2 is module size rather than a
    precise accounting of what fills it.
    """
    return sum(
        1
        for line in source.splitlines()
        if line.strip() and not line.strip().startswith("#")
    )


def _python_files(roots):
    """Every `.py` file under `roots` in the working tree, path-sorted.

    The working tree, not `git ls-files`: an untracked scratch file under
    `src/` is scanned and can fail the suite. That is deliberate -- it is
    the state the code is actually in -- but it means a local-only failure
    naming a file you never committed is a stray file, not a bug here.

    encoding="utf-8" is passed on every read below. Without it `read_text()`
    uses the locale codec, which is cp1252 on the Windows CI leg, and these
    files are full of em dashes -- so the scan would die with a
    UnicodeDecodeError there while passing on Linux. Same reason
    tests/test_command_depth_scan.py pins it.
    """
    return sorted(
        path
        for root in roots
        for path in (REPO_ROOT / root).glob("**/*.py")
    )


def _relative(path):
    return path.relative_to(REPO_ROOT).as_posix()


def long_functions(roots):
    """`{qualified_name: statement_count}` for everything over C1."""
    found = {}
    for path in _python_files(roots):
        source = path.read_text(encoding="utf-8")
        for name, count in functions(source):
            if count > MAX_STATEMENTS:
                found[f"{_relative(path)}::{name}"] = count
    return found


def long_files(roots):
    """`{path: code_line_count}` for everything over C2."""
    found = {}
    for path in _python_files(roots):
        count = code_lines(path.read_text(encoding="utf-8"))
        if count > MAX_CODE_LINES:
            found[_relative(path)] = count
    return found


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
        "see DEVELOPER-AGENTS.md's \"Module boundaries\". Blank lines and comments "
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
    assert "src/sync.py" in scanned
    assert "scripts/release.py" in scanned
    assert "tests/test_code_standards_scan.py" in scanned
    # Two *nested* modules, which is the specific thing the glob has to get
    # right: `**/*.py` degraded to `*.py` still finds all three paths above
    # -- they sit directly in their roots -- while silently dropping every
    # module in src/enrich/ and src/review/, half of which are on the
    # register. A count alone would only imply this; these name it.
    assert "src/enrich/docling_parse.py" in scanned
    assert "src/review/verbatim_check.py" in scanned
    assert not any(name.startswith("bench/") for name in scanned)


def test_the_registers_name_only_paths_that_still_exist():
    """A renamed module leaves an entry behind that can never be delisted,
    so the register would quietly stop covering it."""
    paths = {name.split("::")[0] for name in LEGACY_LONG_FUNCTIONS} | LEGACY_LONG_FILES
    missing = sorted(name for name in paths if not (REPO_ROOT / name).exists())
    assert not missing, f"register entries for files that no longer exist: {missing}"


def _recorded_counts():
    """`{register entry: the count in its trailing comment}`.

    Read out of this file's own source rather than kept as a second data
    structure, because the comment is what a reader sees when deciding
    which debt to take first -- so the comment is the thing that has to be
    true.
    """
    pattern = re.compile(r'^\s+"([^"]+)",\s+#\s+(\d+)\s*$')
    recorded = {}
    for line in Path(__file__).read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            recorded[match.group(1)] = int(match.group(2))
    return recorded


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
        "the register comments and the registers themselves disagree about "
        "which entries exist"
    )
    drifted = {
        name: (was, counts[name])
        for name, was in recorded.items()
        if was != counts[name]
    }
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
    """The check that would be embarrassing to fail."""
    source = Path(__file__).read_text(encoding="utf-8")
    assert all(count <= MAX_STATEMENTS for _, count in functions(source))


def test_a_statement_is_counted_per_statement_not_per_line():
    """The whole basis of C1, on a synthetic case: same statements, very
    different physical length."""
    terse = "def f():\n    a = 1\n    b = 2\n    return a + b\n"
    explained = (
        "def f():\n"
        + "    # why a is 1: " + "x" * 40 + "\n" * 1
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
    source = (
        "class C:\n"
        "    def m(self):\n"
        "        a = 1\n"
        "        return a\n"
    )
    assert dict(functions(source)) == {"C.m": 2}


def test_two_same_named_methods_in_one_module_stay_distinct():
    """The collision `long_functions()`'s dict would otherwise hide.

    Keyed on the bare name, the second of these would overwrite the first
    -- so a colliding pair would report as one offender, and a register
    entry for one would license a different function of the same name
    added to that module later. `src/pdf_text.py` is the live case: it
    defines `__init__` on both `interrupt_guard` and `_AnnotatedStream`.
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
        "class A:\n"
        "    if True:\n"
        "        def m(self):\n"
        "            a = 1\n"
        "            return a\n"
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
