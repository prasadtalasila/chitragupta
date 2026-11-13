"""Which `chitragupta` commands a skill names, and which a run executed.

The Tier 2 score of `bench_skill_harnesses.py`: a skill that still names a
step's command but whose model no longer runs it is the failure a shrink
can cause and a unit test cannot see (plans/1091-skill-shrink.md, review
focus 2). Two halves, kept apart so each is checked on its own:

- `expected_commands` reads the commands a `SKILL.md` names, inline or
  fenced, as `module sub [sub]` keys ("draft dossier init").
- `commands_run` reads the commands a transcript's tool calls executed,
  in the same keys.

Both resolve subcommands against the module's own `--help`, never a
guessed word list, so `draft render twin-basics` is `draft render` (the
slug is an argument), while `draft dossier init` keeps both words. A
command counts as run only when a Python interpreter (or the
`chitragupta`/`cg` console script) is what the shell segment executes: a
`grep` for the command, or a quoted mention of it, is not a run.
"""

import functools
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

# Skills name these only as what never to run (survey-writer's read-only
# section, and every genre writer's "the user syncs, not you"), so they
# are never expected, and a run that executed one is reported instead.
FORBIDDEN = {"corpus sync", "enrich"}

# A command as a skill names it: the interpreter, optional flags, `-m`,
# the module, then the words after it. The words are trimmed against
# `--help` below; a word is a whole token, so `content/drafts/x.md` and
# `<draft>` are never one.
NAMED = re.compile(
    r"python3?(?:\s+-[A-Za-z]+)*\s+-m\s+chitragupta\.(\w+)"
    r"((?:\s+[a-z][\w-]*(?=[\s`'\")\]]|$))*)"
)
SHELLS = {"sh", "bash", "zsh", "dash"}
CONSOLE = {"chitragupta", "cg"}


@functools.lru_cache(maxsize=None)
def subcommands(path: tuple) -> frozenset:
    """The subcommand choices `python -m chitragupta.<path...> --help`
    prints in its usage line's first `{a,b}` group; empty for a leaf."""
    module, *rest = path
    proc = subprocess.run(
        [sys.executable, "-m", f"chitragupta.{module}", *rest, "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    usage = proc.stdout.split("\n\n")[0]
    found = re.search(r"\{([\w,-]+)\}", usage)
    return frozenset(found.group(1).split(",")) if found else frozenset()


def command_key(module: str, words: list) -> str:
    """`module` plus as many leading `words` as are real subcommands."""
    path = [module]
    for word in words:
        if word not in subcommands(tuple(path)):
            break
        path.append(word)
    return " ".join(path)


def expected_commands(*files: Path) -> list:
    """Every distinct command `files` name, in order of first appearance
    (the `SKILL.md` first, then each reference it points at), minus
    FORBIDDEN. A step cut to a pointer keeps its commands in the reference
    (survey-writer's render step), so reading `SKILL.md` alone would stop
    tracking exactly the step a shrink moved."""
    seen = []
    for path in files:
        for module, words in NAMED.findall(path.read_text(encoding="utf-8")):
            key = command_key(module, words.split())
            if key not in seen and key not in FORBIDDEN:
                seen.append(key)
    return seen


def _tokens(command: str) -> list:
    """Shell words with quotes honoured, and `;`, `&&`, `|`, `(` and `)`
    as words of their own, so `$(python -m ...)` and `a; b` both expose
    the interpreter. An unbalanced quote (a heredoc, a cut-off command)
    falls back to whitespace, which can split a quoted mention apart but
    never join one into an interpreter call."""
    # A newline ends a command like `;` does, so it is punctuation here,
    # not whitespace: line two of a multi-line Bash call is a command too.
    lexer = shlex.shlex(command, posix=True, punctuation_chars="();<>|&\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return command.split()


# What may stand before a command and leave the next word in command
# position: shell operators, the keywords that open a body, and wrappers
# that run their argument (`timeout`'s duration is skipped as well).
OPERATORS = {";", "&&", "||", "|", "&", "(", ")", "{", "}", "!", "\n"}
KEYWORDS = {"do", "then", "else", "elif", "time", "exec", "nohup", "env", "sudo", "xargs", "if"}


def _command_words(tokens: list):
    """(index, word) of each word in command position: the first word of a
    simple command, past `VAR=value` assignments and `timeout <n>`. `echo
    python -m ...` names an interpreter as an argument, not a command."""
    at_start = True
    for i, token in enumerate(tokens):
        bare = token.lstrip("$`")
        if token in OPERATORS or token.endswith("$") or bare in KEYWORDS:
            at_start = True
        elif at_start and (
            re.fullmatch(r"\w+=.*", token)
            or bare == "timeout"
            or re.fullmatch(r"[\d.]+[smhd]?", token)
        ):
            continue
        elif at_start:
            at_start = False
            yield i, bare


def commands_run_in(command: str) -> list:
    """Every command key one tool call's shell command executes, in order.

    `sh -c '<script>'` (Codex runs everything as `zsh -lc '...'`) is
    scored on the script inside the quotes."""
    tokens = _tokens(command)
    found = []
    for i, word in _command_words(tokens):
        name = Path(word).name
        after = tokens[i + 1 :]
        if name in SHELLS and len(after) >= 2 and re.fullmatch(r"-\w*c\w*", after[0]):
            found.extend(commands_run_in(after[1]))
        elif name in CONSOLE and after and after[0] in subcommands(("__main__",)):
            found.append(command_key(after[0], after[1:]))
        elif re.fullmatch(r"python[\d.]*", name):
            while after and after[0].startswith("-") and after[0] != "-m":
                after = after[1:]
            if len(after) >= 2 and after[0] == "-m" and after[1].startswith("chitragupta."):
                found.append(command_key(after[1].split(".", 1)[1], after[2:]))
    return found


def commands_run(tool_inputs: list) -> list:
    """Every command key a transcript's tool calls executed, in order of
    first run, one tool input at a time so one bad quote spoils only its
    own call."""
    seen = []
    for one in tool_inputs:
        for key in commands_run_in(one):
            if key not in seen:
                seen.append(key)
    return seen


PASS, FAIL, INCONCLUSIVE = 0, 1, 3


def _counts(rows: list) -> dict:
    """Per command, in how many of `rows` it ran; plus the gate and every
    forbidden command, under keys of their own."""
    counts = {"(gate passed)": sum(row.get("gate") == 0 for row in rows)}
    for row in rows:
        # Every command the run executed, not only those its own arm's
        # skill named: a command one arm moved out of the files the
        # scorer reads must not read as "stopped running".
        for key in row.get("ran_all", row.get("ran", [])):
            counts[key] = counts.get(key, 0) + 1
        for key in row.get("forbidden_ran", []):
            counts[f"(forbidden) {key}"] = counts.get(f"(forbidden) {key}", 0) + 1
    return counts


def judge(before: list, after: list) -> "tuple[int, list]":
    """The verdict for one (harness, skill), and its table rows.

    3 runs an arm can screen but not convict (docs/HARNESS.md has the
    arithmetic): at a true per-run rate of 0.8, a two-run drop between
    two unchanged arms happens for 1 command in 18, so over a skill's
    ~9 commands on 3 harnesses a 3-run "fail" would be noise most of the
    time. So at 3 against 3 only a command that ran in every before run
    and no after run fails (or the gate, or a new forbidden command); any
    other drop is inconclusive, and 3 more runs an arm settle it, where a
    drop of 4 in 6 fails and anything less passes. Drops are counted on
    the before arm's scale, so unequal arms compare rates.
    """
    n_b, n_a = len(before), len(after)
    scale = max(n_b, 1) / 3
    settled = n_b >= 6 and n_a >= 6
    b_counts, a_counts = _counts(before), _counts(after)
    keys = list(dict.fromkeys([k for row in before + after for k in row.get("expected", [])]))
    keys = (
        ["(gate passed)"]
        + keys
        + sorted(k for k in set(b_counts) | set(a_counts) if k.startswith("(forbidden)"))
    )
    verdict, table = PASS, []
    for key in keys:
        b, a = b_counts.get(key, 0), a_counts.get(key, 0)
        drop = b - a * n_b / max(n_a, 1)
        if key.startswith("(forbidden)"):
            bad = FAIL if a and not b else PASS
        elif (b == n_b > 0 or key == "(gate passed)" and b > 0) and a == 0:
            bad = FAIL
        elif settled:
            bad = FAIL if drop >= 2 * scale - 1e-9 else PASS
        elif drop > 1e-9:
            bad = INCONCLUSIVE
        else:
            bad = PASS
        verdict = max(verdict, bad, key=[PASS, INCONCLUSIVE, FAIL].index)
        table.append(
            (key, f"{b}/{n_b}", f"{a}/{n_a}", {PASS: "", INCONCLUSIVE: "drop?", FAIL: "FAIL"}[bad])
        )
    return verdict, table


def compare(before_path: Path, after_path: Path, quiet: bool = False) -> int:
    """`--compare`: one table per (harness, skill), then the worst verdict
    as the exit code -- 0 pass, 1 fail, 3 inconclusive (rerun 3 more on
    both arms and compare the merged files). A (harness, skill) in only one
    arm is inconclusive: there is nothing to compare it against."""
    load = lambda path: json.loads(Path(path).read_text(encoding="utf-8"))  # noqa: E731
    groups: dict = {}
    for arm, rows in (("before", load(before_path)), ("after", load(after_path))):
        for row in rows:
            groups.setdefault((row["harness"], row["skill"]), {"before": [], "after": []})[
                arm
            ].append(row)
    worst = PASS
    for (harness, skill), arms in sorted(groups.items()):
        if not arms["before"] or not arms["after"]:
            verdict, table = INCONCLUSIVE, [("(no runs in one arm)", "", "", "drop?")]
        else:
            verdict, table = judge(arms["before"], arms["after"])
        worst = max(worst, verdict, key=[PASS, INCONCLUSIVE, FAIL].index)
        if not quiet:
            name = {PASS: "pass", FAIL: "FAIL", INCONCLUSIVE: "inconclusive"}[verdict]
            print(f"\n{harness} / {skill}: {name}")
            width = max(len(row[0]) for row in table)
            for key, b, a, mark in table:
                print(f"  {key:<{width}}  {b:>5} -> {a:<5} {mark}")
    if not quiet:
        print(f"\nverdict: {({PASS: 'pass', FAIL: 'fail', INCONCLUSIVE: 'inconclusive'})[worst]}")
    return worst


def score_commands(expected: list, ran_all: list) -> dict:
    """The Tier 2 fields: what the skill names, what of it ran (in the
    order first run), what it missed, and any forbidden command run."""
    ran = [key for key in ran_all if key in expected]
    return {
        "expected": expected,
        "ran_all": ran_all,
        "ran": ran,
        "missed": [key for key in expected if key not in ran],
        "forbidden_ran": [key for key in ran_all if key in FORBIDDEN],
        "ran_unnamed": [key for key in ran_all if key not in expected and key not in FORBIDDEN],
    }
