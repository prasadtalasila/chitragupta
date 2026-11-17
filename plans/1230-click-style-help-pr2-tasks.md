# Click-style help, PR 2: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:executing-plans to implement this plan task by task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

Status: **built, not merged.** Written 2026-11-17. On the way: `[OPTIONS]`
shows whenever a parser has any option, `--help` included, as click's
does; positionals are named in upper case under `Arguments:` too.

**Goal:** give every leaf `--help` the click look PR 1 gave the
dispatchers. Examples are `chitragupta corpus discover --help`,
`chitragupta draft dossier --help` and `chitragupta review verbatim
scan --help`.

**Architecture:**

- One `argparse.ArgumentParser` subclass, `ClickParser`, in
  `chitragupta/help_format.py`. Every parser in `chitragupta/` is built
  from it.
- Subcommands get it automatically: argparse builds a subparser with its
  parent's class.
- PR 1's `_Dispatcher` folds into it. A dispatcher is a `ClickParser`
  given explicit rows.

**Tech stack:** Python 3.12 to 3.14, stdlib `argparse`, pytest.

**Spec:** [plans/1230-click-style-help.md](1230-click-style-help.md),
section "Design, PR 2", approved 2026-11-17. The rest of this file
assumes PR 1 (#1234, released as 6.175.0).

## Global constraints

The same constraints as PR 1:

- stdlib only;
- every verb, flag and exit code unchanged;
- the module form unchanged;
- help on stdout, errors on stderr with exit 2;
- C1 (25 statements per function) and C2 (250 code lines per module);
- 100% line and branch coverage;
- the commit format;
- no citekey anywhere.

Version: MINOR, to 6.176.0. The help output of every leaf command changes
shape; the CLI's argument shape does not.

## Review focus

1. A parser with a subcommand group **and** positionals or options of
   its own, for example `review verbatim`. Its usage line and sections
   must both read correctly. Pinned in Task 1.
2. A positional with `choices`, for example `install`'s stage. The
   `Arguments:` row must still show the choices, because
   `test_packaging_command_table.py` reads them. Pinned in Task 2.
3. A usage error from a leaf: still exit 2, with the collapsed usage line
   and the message on stderr. Pinned in Task 1.
4. `retrieve`'s epilog: it must still print, indented two spaces. Pinned
   in Task 1.
5. `draft gate --help`, which stays hand-written: the new look, with
   `citation_gate.py` still importing nothing new. Pinned in Task 3.

---

### Task 1: `ClickParser`

**Files:** modify `chitragupta/help_format.py`; test in
`tests/test_help_format.py`.

**Interfaces:**

- Produces `ClickParser(argparse.ArgumentParser)`. It takes the
  constructor keywords
  `command_rows: list[tuple[str, str]] | None = None` and
  `command_hint: str | None = None`. Its defaults are:
  - `formatter_class=ClickFormatter`;
  - `add_help=False`, plus its own `-h, --help` with the help
    `Show this message and exit.`;
  - group titles `Options` and `Arguments`;
  - every entry of `**parser_kwargs()`.
- `add_subparsers(**kw)` defaults `metavar="COMMAND"` and suppresses the
  group's own help row. `format_help` appends the `Commands:` block from
  the group's choices, plus a hint, exactly as a dispatcher does.
- Explicit `command_rows` win over a subparsers group.
- The hint defaults to `Run '<prog> COMMAND --help' for a command's
  flags.`
- When no `usage=` is given, `ClickFormatter` collapses the usage line to
  `Usage: <prog> [OPTIONS] <POSITIONALS>`, with `[OPTIONS]` only when the
  parser has a visible option. Each positional prints as its metavar, or
  as its dest in upper case. `nargs` decides the shape:
  - `?` gives `[X]`;
  - `*` gives `[X]...`;
  - `+` gives `X...`;
  - an integer `N` gives `X` repeated N times;
  - a subparsers group gives `COMMAND [ARGS]...`.
- Every argument's help is printed with its first letter capitalised.
- `dispatcher_parser(...)` keeps its signature and returns a
  `ClickParser`.

**Tests**, written first and watched fail:

- `test_a_leaf_collapses_its_usage`: pins `[PHRASE]...` for
  `nargs="*"`, `FILE...` for `nargs="+"`, `[X]` for `nargs="?"`, two
  copies of `X` for `nargs=2`, and a bare `X` for a single positional.
- `test_positionals_are_listed_under_arguments_and_options_capitalised`
- `test_subcommands_render_as_a_commands_block_in_registration_order`
- `test_a_subparser_is_a_click_parser`
- `test_a_usage_error_prints_the_collapsed_usage_on_stderr_and_exits_2`
- `test_an_epilog_still_prints`
- `test_explicit_rows_win_over_subparsers`
- `test_no_options_means_no_options_placeholder`

### Task 2: Every parser site, and the hard-coded progs

**Files:**

- Modify the 36 `argparse.ArgumentParser(` sites under `chitragupta/`,
  listed by
  `grep -rn "argparse.ArgumentParser(" chitragupta`.
- Replace each `prog="python -m chitragupta.<layer> <verb>"` (13 sites)
  with `f"{prog_for('<layer>')} <verb>"`.
- Test in `tests/test_help_format.py`, and update the tests that pin the
  old help.

**Tests:**

- `test_every_parser_is_a_click_parser`, a source scan. It has a
  non-vacuous guard, asserting that the glob matched at least 30 files.
  It fails on any `argparse.ArgumentParser(` under `chitragupta/` outside
  `help_format.py`.
- `test_no_parser_hardcodes_the_module_form`, a source scan: no
  `prog="python -m` under `chitragupta/`.
- Update the existing assertions that pin `usage:`, which becomes
  `Usage:`. The list:
  - `tests/test_review_entrypoint.py:106`;
  - `tests/test_verbatim_check.py`: lines 2984, 3140, 3145, 3150 and
    3225;
  - `tests/test_populate_bib_groups.py:437`, only if it parses through a
    `chitragupta/` parser; `scripts/` stays out of scope.
- Then run the whole suite and fix whatever else pinned the old shape.

### Task 3: `draft gate`'s hand-written help

**Files:** modify `chitragupta/citation_gate.py`'s `USAGE`; test in
`tests/test_citation_gate.py`.

- `USAGE` becomes
  `Usage: python -m chitragupta.draft gate FILE...`, then the existing
  paragraphs indented two spaces, then
  `Options:\n  -h, --help  Show this message and exit.`.
- No new import.
- Update the two `"usage:"` assertions at lines 815 and 826, and add
  `test_gate_help_reads_like_click`.

### Task 4: Docs, version, checks

- Update `docs/CLI.md`'s `--help` paragraph: every command's help now
  uses the same look. Then sweep `docs/` for the claims this touches:
  `grep -rn "argparse" docs/*.md DEVELOPER-AGENTS.md`.
- Name `ClickParser` as the rule for a new command where the code
  standards or the architecture doc say how to add one, so a new parser
  doesn't fall back to plain argparse.
- Set the `Status:` line in `plans/1230-click-style-help.md` and in this
  file.
- Bump `pyproject.toml` to 6.176.0.
- Run the full suite with coverage, `scripts/check_local.sh`, and OCR
  delegate-review.
