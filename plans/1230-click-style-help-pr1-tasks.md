# Click-style help, PR 1: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task by task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

Status: **plan, not built.** Written 2026-11-17.

**Goal:** make `chitragupta --help`, `chitragupta corpus --help` and
`chitragupta draft --help` list one command per line in click's style,
and give the top level a two-level tree of every layer's verbs.

**Architecture:**

- `chitragupta/command_help.py` holds every layer's one-line help, as
  data only.
- `chitragupta/help_format.py` holds the formatter, the truncation rule
  and the parser factory.
- The dispatchers read their help strings from the first module and
  build their parsers with the second.
- Neither module imports anything from this package except `progname`.

**Tech stack:** Python 3.12 to 3.14, stdlib `argparse`, `textwrap`,
`shutil`, pytest.

**Spec:** [plans/1230-click-style-help.md](1230-click-style-help.md),
approved 2026-11-17. Read it first.

## Global constraints

- No new dependency. Both new modules import stdlib only, plus
  `chitragupta.progname`.
- Unchanged:
  - every verb, flag and exit code;
  - `python -m chitragupta.<layer>`;
  - help goes to stdout, errors to stderr, exit 2 on bad usage;
  - no verb prints the usage and exits 0;
  - the usage line still names `prog_for(...)`.
- `suggest_on_error=True` only when `sys.version_info >= (3, 14)`.
- The truncation limit is `max(width - 6 - widest_name, 45)`. The width
  comes from `shutil.get_terminal_size().columns`, which honours
  `COLUMNS`.
- At most 25 statements per function and 250 code lines per module.
  `tests/test_code_standards_scan.py` enforces both.
- 100% line and branch coverage. Run:

  ```bash
  /workspace/.venv-full/bin/python -m pytest -n auto --cov --cov-report=term-missing
  ```

- Commit messages: an imperative title with no PR number, then a body
  of verb-first bullets wrapped at 72 characters, then the
  `Co-Authored-By` line.
- No citekey anywhere: not in a fixture, a doc or a test.

## Review focus

1. A narrow terminal, `COLUMNS=40`: the limit floor of 45 keeps rows
   readable and nothing raises. Pinned in Task 1.
2. A help string with no clause break and a single word longer than the
   limit: cut it hard, append `...`, never loop. Pinned in Task 1.
3. `chitragupta --help` when `chitragupta.enrich` cannot be imported:
   the tree still prints. Pinned in Task 4.
4. `chitragupta draft bogus`: still exit 2, with `invalid choice` on
   stderr. The `metavar` change must not hide the choices in the
   message. Pinned in Task 3.
5. `python -m chitragupta.draft gate --help`, which is not argparse:
   still exits 0 with its own text. Pinned in Task 3; the existing test
   is kept.

## Calls made while planning (deviations from the spec, flagged)

- **Two modules instead of one.** Data and formatting split, to stay
  under C2's 250 lines and to keep the data file importable on its own.
- **`VERBS` keeps its `(module, help)` tuple shape,** with the help read
  from `command_help`. Three tests index `VERBS[...][0]`, and keeping the
  shape keeps the diff small. The help still has one source.
- **Review and figure also read their help from `command_help`.** That
  is a one-line change each in `review/_registry.py` and
  `figure/__main__.py`, so the tree's strings cannot drift from the
  layers' own.
- **Only corpus, draft, review and figure show verbs in the tree.**
  enrich, init, doctor and install have no subcommands; enrich takes
  `--stages`, and install's stages are a positional argument. They show
  one line each.

---

### Task 1: The help index and the truncation rule

**Files:**

- Create: `chitragupta/command_help.py`
- Create: `chitragupta/help_format.py`. This task adds only `truncate`
  and `commands_block`.
- Test: `tests/test_help_format.py`

**Interfaces:**

- Produces `command_help.HELP: dict[str, tuple[str, dict[str, str]]]`:
  `{name: (one_line, {verb: help})}`, in today's `CHOICES` order (the
  four layers, then init, doctor, install, figure). Verb dicts are in
  today's registration order. Every string is copied verbatim from
  today's `LAYERS`, `COMMANDS`, `corpus.VERBS`, `draft.VERBS`,
  `review/_registry.AIDS` and figure's `add_parser(help=...)`.
- Produces `command_help.verbs(name: str) -> dict[str, str]`, which
  returns `HELP[name][1]`.
- Produces `help_format.truncate(text: str, limit: int) -> str`.
- Produces
  `help_format.commands_block(rows: list[tuple[str, str]], width: int) -> str`.
  - Names may carry leading spaces, which is how the tree nests verbs.
  - Each row is `"  " + name.ljust(widest) + "  " + truncate(help, limit)`.
  - `limit = max(width - 6 - widest, 45)`.
  - Rows are joined with `"\n"`, with no trailing newline.

- [ ] **Step 1: Write the failing tests**

```python
from chitragupta.help_format import commands_block, truncate

def test_a_clause_that_fits_is_kept_and_the_rest_dropped():
    assert truncate("read-only view of what that run recorded -- takes no lock", 66) == \
        "Read-only view of what that run recorded"

def test_a_first_sentence_is_kept():
    assert truncate("Create a skeleton. Then more text.", 60) == "Create a skeleton"

def test_text_that_fits_whole_is_capitalised_and_loses_its_full_stop():
    assert truncate("what changed.", 60) == "What changed"

def test_overlong_text_is_cut_at_a_word_and_marked():
    out = truncate("the working state behind a draft: create it, inspect it, back it up, restore it", 64)
    assert out == "The working state behind a draft: create it, inspect it..."
    assert len(out) <= 64

def test_one_word_longer_than_the_limit_is_cut_hard():
    out = truncate("x" * 100, 45)
    assert out == "X" * 42 + "..."

def test_the_limit_never_drops_below_45():
    block = commands_block([("discover", "y " * 40)], width=40)
    assert len(block.splitlines()[0]) == 2 + 8 + 2 + 45

def test_nested_rows_align_on_the_widest_name():
    block = commands_block([("corpus", "a"), ("  sync", "b")], width=80)
    assert block == "  corpus  A\n    sync  B"
```

Also add `test_help_index_is_import_light`: run `python -c "import
chitragupta.command_help, chitragupta.help_format, sys; print(sorted(m for
m in sys.modules if m.startswith('chitragupta')))"` through `run_python`.
Assert the output lists only `chitragupta`, `chitragupta.command_help`,
`chitragupta.help_format` and `chitragupta.progname`.

- [ ] **Step 2: Run the tests and check they fail**

Run: `/workspace/.venv-full/bin/python -m pytest tests/test_help_format.py -v`

Expected: FAIL with `ModuleNotFoundError: chitragupta.help_format`.

- [ ] **Step 3: Implement both modules.** This is the algorithm for
  `truncate`, because the tests alone don't pin its order:

```python
def truncate(text: str, limit: int) -> str:
    text = text.strip()
    breaks = [i for i in (text.find(". "), text.find(" -- ")) if i > 0]
    if breaks and min(breaks) <= limit:
        out = text[: min(breaks)]
    elif len(text) <= limit:
        out = text.rstrip(".")
    else:
        head = text[: limit - 3]
        out = (head.rsplit(" ", 1)[0] if " " in head else head).rstrip(",:;") + "..."
    return out[:1].upper() + out[1:]
```

  Each module gets a docstring saying why it is stdlib-only: the tree
  must not import a layer.

- [ ] **Step 4: Run the tests and check they pass.** Same command.
  Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add chitragupta/command_help.py chitragupta/help_format.py tests/test_help_format.py
git commit -m "Add an import-light help index and a click-style truncation rule" # + bullets
```

### Task 2: The click-style formatter and the dispatcher parser

**Files:**

- Modify: `chitragupta/help_format.py`
- Test: `tests/test_help_format.py`

**Interfaces:**

- Consumes `commands_block` and `truncate` from Task 1.
- Produces `help_format.parser_kwargs() -> dict`. It returns
  `{"suggest_on_error": True}` when `sys.version_info >= (3, 14)` and
  `{}` otherwise.
- Produces `help_format.dispatcher_parser(prog: str, description: str,
  rows: list[tuple[str, str]], dest: str, choices: list[str] | None = None,
  hint: str | None = None) -> argparse.ArgumentParser`.
  - `choices=None` means the row names. The front door passes the
    top-level names, because its rows also hold the indented verbs.
  - `hint=None` means `Run '<prog> COMMAND --help' for a command's flags.`
  The parser it returns has:
  - `add_help=False`, plus its own `-h, --help` with the help
    `Show this message and exit.`;
  - the usage `%(prog)s [OPTIONS] COMMAND [ARGS]...`;
  - the positional `dest` with `nargs="?"`, `choices=` the row names,
    `metavar="COMMAND"` and `help=argparse.SUPPRESS`;
  - the `rest` argument as today: `REMAINDER`, suppressed;
  - every entry of `**parser_kwargs()`;
  - help text laid out as below.
- The help layout, top to bottom:
  - the prefix `Usage:` followed by one space;
  - the description wrapped to `width - 2`, indented two spaces;
  - an `Options:` heading;
  - a `Commands:` heading over `commands_block(rows, width)`;
  - a blank line;
  - the hint `Run '<prog> COMMAND --help' for a command's flags.`,
    indented two spaces.
- How `format_help` appends the `Commands:` section is the builder's
  call: an `ArgumentParser` subclass, or a formatter.

- [ ] **Step 1: Write the failing tests**

```python
def test_parser_kwargs_suggests_only_on_314(monkeypatch):
    monkeypatch.setattr(sys, "version_info", (3, 14, 0))
    assert help_format.parser_kwargs() == {"suggest_on_error": True}
    monkeypatch.setattr(sys, "version_info", (3, 13, 5))
    assert help_format.parser_kwargs() == {}

def test_dispatcher_help_matches_click(monkeypatch, capsys):
    monkeypatch.setenv("COLUMNS", "80")
    p = help_format.dispatcher_parser("chitragupta corpus", "The corpus layer.",
                                      [("sync", "bib file -> ledger"), ("ledger", "read it -- no lock")], "verb")
    p.print_help()
    assert capsys.readouterr().out == (
        "Usage: chitragupta corpus [OPTIONS] COMMAND [ARGS]...\n\n"
        "  The corpus layer.\n\n"
        "Options:\n  -h, --help  Show this message and exit.\n\n"
        "Commands:\n  sync    Bib file -> ledger\n  ledger  Read it\n\n"
        "  Run 'chitragupta corpus COMMAND --help' for a command's flags.\n"
    )

def test_choices_and_hint_override_the_rows(capsys):
    p = help_format.dispatcher_parser("x", "d", [("a", "s"), ("  b", "t")], "verb",
                                      choices=["a"], hint="Go.")
    p.print_help()
    out = capsys.readouterr().out
    assert out.endswith("\n  Go.\n")
    with pytest.raises(SystemExit):
        p.parse_args(["b"])

def test_an_unknown_command_still_names_the_choices(capsys):
    p = help_format.dispatcher_parser("x", "d", [("sync", "s")], "verb")
    with pytest.raises(SystemExit) as e:
        p.parse_args(["bogus"])
    assert e.value.code == 2
    assert "invalid choice: 'bogus'" in capsys.readouterr().err
```

- [ ] **Step 2: Run the tests and check they fail.**
  `pytest tests/test_help_format.py -v` should fail with
  `AttributeError: ... 'parser_kwargs'`.
- [ ] **Step 3: Implement `parser_kwargs`, the formatter and
  `dispatcher_parser`.**
- [ ] **Step 4: Run the tests and check they pass.**
- [ ] **Step 5: Commit**, titled "Add a click-style help formatter for
  the command dispatchers".

### Task 3: The corpus and draft dispatchers

**Files:**

- Modify: `chitragupta/corpus.py`, from `VERBS` through `build_parser`
- Modify: `chitragupta/draft.py`, from `VERBS` through `build_parser`
- Test: `tests/test_corpus_entrypoint.py`, `tests/test_draft_entrypoint.py`

**Interfaces:**

- Consumes `command_help.verbs(name)` and
  `help_format.dispatcher_parser(...)`.
- `VERBS` keeps the shape `{verb: (module_or_path, help)}`. Each help
  string becomes `verbs("corpus")[verb]` or `verbs("draft")[verb]`.
- `build_parser()` keeps its name and returns
  `dispatcher_parser(prog_for(layer), DESCRIPTION, rows, "verb")`.

- [ ] **Step 1: Write the failing tests.** Add to each entrypoint test
  file:
  - `test_help_lists_one_command_per_line`: run `main(["--help"])` with
    `COLUMNS=80` and `sys.argv[0]` set to `"chitragupta"`. Assert that
    each verb in `VERBS` starts its own line (`"\n  <verb> "`). Assert
    that `" / "` is no longer in the output. Assert that the output ends
    with `Run 'chitragupta <layer> COMMAND --help' for a command's flags.\n`.
  - `test_verbs_and_help_index_agree`:
    `list(VERBS) == list(command_help.verbs("<layer>"))`.

  Pin the full corpus help as a golden string. These are the rows at 80
  columns:

  ```text
  Commands:
    sync      Bib file -> ledger -> PDF text: the deterministic corpus run
    ledger    Read-only view of what that run recorded
    topics    Read-only view of which papers each seed topic matched
    discover  Resolve a phrase to a topic and walk its papers and neighbours
  ```

  Keep the existing `test_an_unknown_verb_is_a_usage_error` (exit 2,
  `invalid choice`), the `gate --help` test and
  `test_no_verb_prints_the_layers_usage_and_exits_zero` as they are.
- [ ] **Step 2: Run the tests and check they fail.**

  ```bash
  pytest tests/test_corpus_entrypoint.py tests/test_draft_entrypoint.py -v
  ```

  The new tests should fail, with `" / "` still present.
- [ ] **Step 3: Rewire both dispatchers.** Remove the
  `" / ".join(...)` lines. `DESCRIPTION` and `main()` stay unchanged.
- [ ] **Step 4: Run the tests and check they pass.** Then run
  `tests/test_draft_diff_cli.py`, `tests/test_draft_figures.py` and
  `tests/test_seed_topics.py`, which index `VERBS[...][0]`. They must
  pass unchanged.
- [ ] **Step 5: Commit**, titled "List the corpus and draft verbs one
  per line in click's style".

### Task 4: The top-level tree, and review and figure reading the index

**Files:**

- Modify: `chitragupta/__main__.py`, from `LAYERS` through `build_parser`
- Modify: `chitragupta/review/_registry.py`, `AIDS` help strings
- Modify: `chitragupta/figure/__main__.py`, the four
  `add_parser(help=...)` calls
- Test: `tests/test_package_entrypoint.py`

**Interfaces:**

- `LAYERS` and `COMMANDS` keep the shape `{name: (module_path, help)}`,
  with help read from `command_help.HELP[name][0]`. `CHOICES` is
  unchanged.
- Produces `__main__.tree_rows() -> list[tuple[str, str]]`. For each name
  in `HELP` order it yields `(name, one_line)`, then
  `("  " + verb, help)` for each verb.
- `build_parser()` returns
  `dispatcher_parser(prog_for(""), DESCRIPTION, tree_rows(), "layer")`,
  plus `--version` as today with the help `Show the version and exit.`.
  It passes `choices=sorted(CHOICES)`, and
  `hint="Run '<prog> COMMAND --help' for a command's commands and flags."`.

- [ ] **Step 1: Write the failing tests**
  - `test_help_shows_every_layers_verbs`: for each `(name, (_, verbs))`
    in `HELP`, assert `"\n  " + name + " "` is in the output. For each
    verb, assert `"\n    " + verb + " "` is in the output.
  - `test_help_does_not_import_any_layer`: run `-c` through
    `run_python`, calling `__main__.main(['--help'])` inside
    `try/except SystemExit` and then printing the sorted `sys.modules`.
    Assert that none of these appear: `chitragupta.draft`,
    `chitragupta.corpus`, `chitragupta.review.__main__`,
    `chitragupta.enrich.__main__`, `chitragupta.figure.__main__`.
  - `test_help_survives_a_broken_enrich`: set
    `sys.modules['chitragupta.enrich'] = None`, then call
    `main(['--help'])`. It should exit 0 with `enrich` in stdout.
  - `test_review_and_figure_help_come_from_the_index`. Assert:
    - `{k: v[1] for k, v in _registry.AIDS.items()} == command_help.verbs("review")`;
    - the names and help of figure's subparsers equal
      `command_help.verbs("figure")`, read from
      `build_parser()._subparsers._group_actions[0]._choices_actions`.
  - Update `test_the_review_line_counts_the_aids_the_registry_holds` to
    read `command_help.HELP["review"][0]`. The `LAYERS["review"][1]`
    assertion still holds, so keep it.
- [ ] **Step 2: Run the tests and check they fail.**
  `pytest tests/test_package_entrypoint.py -v`
- [ ] **Step 3: Implement.** Rewire `__main__.py`, `_registry.py` and
  `figure/__main__.py`. The figure layer's own `--help` keeps its
  argparse look until PR 2.
- [ ] **Step 4: Run the tests and check they pass.** Then run
  `tests/test_review_entrypoint.py` and the figure tests:
  `pytest tests -k "figure or review_entrypoint" -q`.
- [ ] **Step 5: Commit**, titled "Show every layer's verbs from
  chitragupta --help".

### Task 5: Draft gate's imports, docs, and the whole suite

**Files:**

- Test: `tests/test_draft_entrypoint.py`
- Modify: every place in `docs/CLI.md` and `docs/PACKAGING.md` that
  quotes the old ` / `-joined help. Find them with
  `grep -n "positional arguments" docs/*.md`. If none quote it, record
  that in the commit body.
- Modify: `plans/1230-click-style-help.md`, its `Status:` line

- [ ] **Step 1: Write the test.**
  `test_gate_adds_only_the_stdlib_help_modules`. It pins "draft gate
  imports nothing new" as two properties that together cover it.
  Task 1's import-light test already proves the two new modules pull in
  nothing but stdlib and `progname`. This test proves the dispatch path
  loads them and nothing third-party.

  Through `run_python("-c", SNIPPET)`, where `SNIPPET` is:

  ```python
  import runpy, sys
  sys.argv = ["x", "gate", "--help"]
  try:
      runpy.run_module("chitragupta.draft", run_name="__main__")
  except SystemExit:
      pass
  print(sorted({m.split(".")[0] for m in sys.modules}
               - set(sys.stdlib_module_names) - {"chitragupta", "__main__"}))
  print("chitragupta.help_format" in sys.modules)
  ```

  Then assert:
  - the first line equals the same line printed by a child that runs
    only the final `print(sorted(...))`. That holds the interpreter's
    start-up shims, for example `sitecustomize` and `_distutils_hack`,
    so the test is the same in any venv. Today both lines are
    `['_distutils_hack', 'sitecustomize']`.
  - the second line is `True`, so the help path really went through the
    new module.

- [ ] **Step 2: Run it and check it passes.** This one is a guard, not
  test-first: it should pass already, because of Tasks 1 and 3.
- [ ] **Step 3: Update the docs.** Then run markdownlint over the
  changed files:

  ```bash
  markdownlint-cli2 docs/CLI.md docs/PACKAGING.md plans/1230-click-style-help*.md
  ```

  Expected: `0 issues`.
- [ ] **Step 4: Run the whole suite with coverage.**

  ```bash
  /workspace/.venv-full/bin/python -m pytest -n auto --cov --cov-report=term-missing
  ```

  Expected: all pass, 100% line and branch coverage, and
  `test_code_standards_scan.py` green.
- [ ] **Step 5: Check by eye.** Run
  `COLUMNS=80 /workspace/.venv-full/bin/python -m chitragupta --help`
  and the same for `corpus --help` and `draft --help`. Compare each with
  the spec's mock-ups.
- [ ] **Step 6: Commit**, titled "Pin draft gate's imports and update
  the CLI docs for the new help". Set the spec's `Status:` to "PR 1
  built".
