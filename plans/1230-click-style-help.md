# Click-style `--help`, one command per line (#1230)

Status: **PR 1 built, not merged; design approved by the owner 2026-11-17.**
PR 1 changed the truncation rule on the way: a line that fits is kept
whole, there are no sentence cuts (only ` -- ` clauses), and a word cut
that keeps under half the line becomes a hard cut.
Written 2026-11-17.

**Written for:** whoever implements #1230 (PR 1) and its follow-up (PR 2).

**Assumed:** the issue text, `chitragupta/__main__.py`, `chitragupta/corpus.py`,
`chitragupta/draft.py` and `chitragupta/progname.py` as of `4570438ab`.

**Not covered here:** shell completion (argcomplete, a new dependency) and
any change to a verb, flag, exit code or the module form.

## Intent

A new user runs `chitragupta --help` and sees every layer and every verb,
one per line, so they can find `draft gate` or `corpus discover` without
opening docs/CLI.md first. The output should look like Python click's:
`Usage:`, `Options:` and `Commands:` headings, aligned columns, and one
truncated line per command. The full text stays one level down, in
`COMMAND --help`.

## Goals, non-goals, anti-goals

- **Goals.** One command per line at every dispatcher. A two-level tree
  at the top. Click's look. On Python 3.14+, typo suggestions.
- **Non-goals.** Click itself or rich, because the core pipeline is
  stdlib plus `bibtexparser`. Argparse subparsers in the front door: the
  `__main__.py` docstring rules out restating layer flags there.
- **Anti-goals.** Any of these makes the change a failure even if the
  help looks right:
  - `draft gate` imports anything new.
  - `chitragupta --help` fails without the `enrich` extra.
  - A help string exists in two places that can drift apart.

## Constraint found while planning

The issue says the top-level tree should be built "from the same dicts".
That is unsafe as written:

- `chitragupta/draft.py` imports every verb module when it loads: 332
  modules under `-X importtime`, against 66 for the gate alone.
- `review/__main__.py`, `figure/__main__.py` and `enrich/__main__.py`
  load heavy code too, and `enrich` can fail outright without its extra.

So `chitragupta --help` cannot import the layers to read their verbs. It
needs an import-light table of verb names and help strings.

## Approaches

| | What | Trade-off |
| --- | --- | --- |
| **A. Light help index (picked)** | New stdlib-only module `chitragupta/command_help.py` holding `{layer: {verb: help}}`. `corpus.py` and `draft.py` read their help strings from it, and their `VERBS` keep only the module. One test checks that each layer's index keys equal its real verbs. | The help strings move out of `VERBS`. They stay single-sourced, and the drift test covers review, enrich and figure too. |
| B. Import the layers inside `--help` | Build the tree by importing each dispatcher, but only when `--help` is asked for. | `chitragupta --help` costs ~330 imports and breaks without the `enrich` extra. |
| C. Hand-written tree in `__main__.py` | A static string. | A second copy of every help string, with nothing to stop drift. |

Scope picked: **two PRs.**

1. **PR 1, #1230 as scoped (about half a day):** the front door plus the
   corpus and draft dispatchers.
2. **PR 2, follow-up (about a day):** every leaf parser gets the same
   look.

## Design, PR 1

1. **`chitragupta/command_help.py`** (stdlib only, imports nothing from
   this package). It holds:
   - `HELP`: `{layer_or_command: (one_line, {verb: help})}`, covering
     corpus, draft, review, enrich, figure, init, doctor and install.
   - `ClickFormatter(argparse.HelpFormatter)`:
     - `Usage:` prefix;
     - the description indented two spaces;
     - section titles `Options:` and `Commands:`;
     - `-h, --help  Show this message and exit.`
   - `commands_epilog(rows, width)`: the `Commands:` block, one aligned
     row per command, followed by the hint line
     `Run 'chitragupta <layer> COMMAND --help' for a command's flags.`
   - `truncate(text, limit)`: the click-style cut (rule below).
   - `make_dispatcher_parser(prog, description, rows)`: sets
     `metavar="COMMAND"` and, on 3.14 or later only, passes
     `suggest_on_error=True`. On 3.12 and 3.13 that keyword raises
     `TypeError`, so a `sys.version_info` check guards it.
2. **Truncation rule:**
   - The limit is click's: `terminal width - 6 - widest command name`,
     never below 45. Width comes from `shutil.get_terminal_size()`, which
     honours `COLUMNS`.
   - Take the first sentence, ending at a full stop and a space, or the
     first clause, ending at a spaced double hyphen, whichever comes
     first, and keep it if it fits.
   - Otherwise cut at the last word boundary that fits and append `...`.
   - The original string is never edited. Truncation happens only when
     rendering.
3. **`chitragupta --help`.** A two-level tree from `HELP`: each layer or
   command, then its verbs indented below it. For example:

   ```text
   Usage: chitragupta [OPTIONS] COMMAND [ARGS]...

     Turn a curated bibliography into grounded drafts, with every citekey
     verified against a real parse.

   Options:
     --version   Show the version and exit.
     -h, --help  Show this message and exit.

   Commands:
     corpus    Bring the ledger up to date, or read what it recorded.
       sync        ...
       discover    Resolve a phrase to a topic and walk its papers...
     draft     Work on one draft
       gate        Verify every citekey in a draft against the ledger
       ...

     Run 'chitragupta COMMAND --help' for a command's commands and flags.
   ```

4. **`chitragupta corpus --help` and `chitragupta draft --help`.** A flat
   `Commands:` list with the same formatter.
5. **Unchanged behaviour:**
   - every verb, flag and exit code;
   - the module form;
   - stdout for help and stderr for errors, exit 2 on bad usage;
   - no verb prints the usage and exits 0;
   - `prog_for` still names the command.

   On 3.14, argparse's own colour comes for free and honours `NO_COLOR`.
6. **Tests:**
   - Drift: for each layer, the `HELP` keys equal the real verb set:
     `VERBS` for corpus and draft, `AIDS` for review, `STAGE_ORDER` for
     enrich, figure's subcommands. This test may import the layers; the
     help path may not.
   - Truncation edge cases: fits, sentence cut, clause cut, word cut, one
     word longer than the limit.
   - Both arms of the 3.14 guard, by monkeypatching `sys.version_info`.
   - `draft gate` imports nothing new, read strictly: `draft.py` gains one
     import, `chitragupta.command_help`, which imports only stdlib. A
     test compares the `sys.modules` set before and after the change for
     `python -m chitragupta.draft gate`, and asserts the only difference is
     `command_help` plus stdlib modules. The bare-interpreter gate
     (`chitragupta/citation_gate.py`) must not import it at all.
   - `chitragupta --help` works with `enrich`'s imports made to fail.
   - Update the help-text assertions that pin the old ` / `-joined
     string.
   - Line and branch coverage stays at 100%.
7. **Docs.** Update every docs/CLI.md or docs/PACKAGING.md section that
   quotes the old help output.

## Design, PR 2 (outline only)

- All 36 `argparse.ArgumentParser(...)` call sites take
  `formatter_class=ClickFormatter` through one small factory in
  `command_help.py`.
- `draft gate` keeps its hand-written usage, because it must run on a
  bare `python3` and must not import the helper. Only its text is
  restyled, by hand, to `Usage:` and `Options:`.
- A test fails if a new parser skips the factory.
- Expect wide churn in the help-text assertions in `tests/`.
- A leaf's usage line collapses its flags to `[OPTIONS]`, as click's
  does. Today `corpus discover`'s usage line spans nine lines of flags.
- Positionals get an `Arguments:` heading. Every help line has its first
  letter capitalised when rendered; the source strings stay as they are.
- Flag help is wrapped, never truncated. Only command lists truncate.
- Subcommands list in the order they are registered, not alphabetically,
  so `dossier`'s `init` and `status` stay at the top.
- Fix `chitragupta/dossier/_cli.py`, whose `prog` is hard-coded to
  `python -m chitragupta.draft dossier` instead of `prog_for(...)`.
  Check the other subparser sites for the same hard-coding.

Agreed mock-ups, from real help strings at 80 columns:

```text
Usage: chitragupta draft dossier [OPTIONS] COMMAND [ARGS]...

  The working state behind a draft: create it, inspect it, back it up,
  restore it. Stdlib only; never writes to the corpus layer.

Options:
  -h, --help  Show this message and exit.

Commands:
  init              Create a dossier skeleton for a draft
  status            What a dossier holds, and corpus drift since
  mark-revision     Record a revision-session boundary, so retrieval cost...

  Run 'chitragupta draft dossier COMMAND --help' for a command's flags.
```

```text
Usage: chitragupta corpus discover [OPTIONS] [PHRASE]...

  Discover topics in the synced corpus: resolve a phrase to a topic, ...

Arguments:
  PHRASE  A topic to look up -- a known label, a near-miss, or any free
          phrase

Options:
  --paper CITEKEY       Show this paper's topics instead of resolving a
                        phrase
  --json                Machine-readable output
  -h, --help            Show this message and exit.
```

## Calls made in planning (correct any)

- The module name is `command_help.py`.
- The truncation limit follows click's formula, with a floor of 45.
- In PR 1, review's and enrich's own `--help` stay as they are. Review
  already lists one aid per line through subparsers, and PR 2 restyles
  both.
- The tree indents verbs under their layer instead of printing them as
  `draft gate` on one line.
- One-line help strings move from `VERBS` into `HELP`, and `VERBS`
  becomes `{verb: module}`.

## Left to the builder

- How `ClickFormatter` overrides argparse internals (`_format_usage`,
  `start_section`), within the one module.
- Exact column widths and the indent of the tree's second level.
