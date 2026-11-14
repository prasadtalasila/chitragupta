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
    prints in its usage line's first positional `{a,b}` group; empty for a
    leaf, or when `--help` fails."""
    module, *rest = path
    proc = subprocess.run(
        [sys.executable, "-m", f"chitragupta.{module}", *rest, "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return frozenset()
    words = proc.stdout.split("\n\n")[0].split()
    for before, word in zip(["usage:", *words], words):
        found = re.fullmatch(r"\[?\{([\w,-]+)\}\]?", word)
        # `[--where {host,docker}]` is an option's choices, not subcommands
        if found and not (before.lstrip("[").startswith("-") and not before.endswith("]")):
            return frozenset(found.group(1).split(","))
    return frozenset()


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
            if key not in seen and not forbidden(key):
                seen.append(key)
    return seen


HEREDOC = re.compile(
    r"(?<![\w<])<<(?!<)(-?)[ \t]*"
    r"(?:'([A-Za-z_][\w-]*)'|\"([A-Za-z_][\w-]*)\"|\\?([A-Za-z_][\w-]*))"
)


def _strip_heredocs(command: str) -> str:
    """`command` without its heredoc bodies. A body is data a command
    reads, never a command: `cat > notes.md <<EOF` over a line that says
    `python -m chitragupta.draft render` runs nothing, and an apostrophe
    in a body ("It's done.") must not unbalance the quotes of the lines
    after it."""
    kept, pending = [], []
    for line in command.split("\n"):
        if pending:
            delimiter, tabs = pending[0]
            if (line.lstrip("\t") if tabs else line) == delimiter:
                pending.pop(0)
            continue
        kept.append(line)
        pending.extend(
            (m.group(2) or m.group(3) or m.group(4), m.group(1) == "-")
            for m in HEREDOC.finditer(line)
        )
    return "\n".join(kept)


def _shell_words(text: str) -> list:
    # A newline ends a command like `;` does, so it is punctuation here,
    # not whitespace: line two of a multi-line Bash call is a command too.
    lexer = shlex.shlex(text, posix=True, punctuation_chars="();<>|&\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    # No comment handling: shlex's would swallow the newline after a
    # `# note`, and with it the next line's command. A `#` word is then
    # the command word of its line, which runs nothing we count.
    lexer.commenters = ""
    return list(lexer)


def _tokens(command: str) -> list:
    """Shell words with quotes honoured, and `;`, `&&`, `|`, `(`, `)` and
    newlines as words of their own, so `$(python -m ...)` and `a; b` both
    expose the interpreter. Where the quotes still do not balance (a
    command cut off mid-string), each line is read on its own, so one bad
    line costs only itself; a line that still fails falls back to
    whitespace, which can split a quoted mention apart but never join one
    into an interpreter call."""
    command = _strip_heredocs(command)
    try:
        return _shell_words(command)
    except ValueError:
        tokens = []
        for line in command.split("\n"):
            try:
                tokens.extend(_shell_words(line))
            except ValueError:
                tokens.extend(line.split())
            tokens.append("\n")
        return tokens


# Words that may stand before a command and leave the next word in
# command position: the keywords that open a body, and wrappers that run
# their argument (their own options, and `timeout`'s duration, skipped).
KEYWORDS = {"do", "then", "else", "elif", "if", "while", "until", "{", "}", "!"}
WRAPPERS = {"time", "exec", "nohup", "env", "sudo", "xargs", "command", "nice", "timeout"}
OPERATOR_CHARS = set(";&|()\n")
HELP = {"-h", "--help"}


def _is_operator(token: str) -> bool:
    """`;`, `&&\\n`, `);` and every other run of shell punctuation, which
    the lexer hands back as one word when they touch."""
    return bool(token) and set(token) <= OPERATOR_CHARS


def _command_words(tokens: list):
    """(index, word) of each word in command position: the first word of a
    simple command, past keywords, `VAR=value` assignments and wrappers.
    `echo python -m ...` and `echo time python -m ...` name an interpreter
    as an argument, not a command."""
    at_start, wrapped = True, False
    for i, token in enumerate(tokens):
        bare = token.lstrip("$`")
        if _is_operator(token):
            at_start, wrapped = True, False
        elif not at_start:
            continue
        elif bare in KEYWORDS or re.fullmatch(r"\w+=.*", token):
            continue
        elif bare in WRAPPERS:
            wrapped = True
        elif wrapped and (token.startswith("-") or re.fullmatch(r"[\d.]+[smhd]?", token)):
            continue
        else:
            at_start, wrapped = False, False
            yield i, bare


def _arguments(tokens: list) -> list:
    """`tokens` up to the end of their simple command."""
    for i, token in enumerate(tokens):
        if _is_operator(token):
            return tokens[:i]
    return tokens


def _python_module(after: list):
    """(module, its arguments) when `after` -- a Python interpreter's
    arguments -- runs `-m chitragupta.<module>` or the `chitragupta`
    dispatcher, else None. `-W` and `-X` take a value of their own."""
    while after and after[0].startswith("-") and after[0] not in ("-m", "-c"):
        after = after[2:] if after[0] in ("-W", "-X") else after[1:]
    if len(after) < 2 or after[0] != "-m":
        return None
    if after[1] == "chitragupta":
        if len(after) > 2 and after[2] in subcommands(("__main__",)):
            return after[2], after[3:]
        return None
    if after[1].startswith("chitragupta."):
        return after[1].split(".", 1)[1], after[2:]
    return None


def _substitutions(command: str) -> list:
    """The scripts of substitutions the shell runs but the lexer folds
    into one word: `$(...)` inside double quotes (`OUT="$(python -m
    ...)"`), and backticks anywhere outside single quotes. An unquoted
    `$(...)` is already split into words of its own; anything in single
    quotes is text and runs nothing."""
    found, quote, i = [], None, 0
    while i < len(command):
        char = command[i]
        if quote != '"' and char == "'":
            quote = None if quote == "'" else "'"
        elif quote != "'" and char == '"':
            quote = None if quote == '"' else '"'
        elif quote == '"' and command.startswith("$(", i) and not command.startswith("$((", i):
            depth, j = 1, i + 2
            while j < len(command) and depth:
                depth += {"(": 1, ")": -1}.get(command[j], 0)
                j += 1
            found.append(command[i + 2 : j - 1])
            i = j
            continue
        elif quote != "'" and char == "`":
            end = command.find("`", i + 1)
            if end > i:
                found.append(command[i + 1 : end])
                i = end + 1
                continue
        i += 1
    return found


def commands_run_in(command: str) -> list:
    """Every command key one tool call's shell command executes, in order.

    `sh -c '<script>'` (Codex runs everything as `zsh -lc '...'`) is
    scored on the script inside the quotes. A `--help` or `-h` call shows
    usage and runs nothing, so it is not a run of the command."""
    tokens = _tokens(command)
    found = [key for inner in _substitutions(command) for key in commands_run_in(inner)]
    for i, word in _command_words(tokens):
        name = Path(word).name
        after = _arguments(tokens[i + 1 :])
        module = None
        if name in SHELLS:
            for j, option in enumerate(after):
                if not option.startswith("-"):
                    break
                if re.fullmatch(r"-\w*c\w*", option) and j + 1 < len(after):
                    found.extend(commands_run_in(after[j + 1]))
                    break
        elif name in CONSOLE and after and after[0] in subcommands(("__main__",)):
            module = after[0], after[1:]
        elif re.fullmatch(r"python[\d.]*", name):
            module = _python_module(after)
        if module is not None and not HELP & set(module[1]):
            found.append(command_key(*module))
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
SEVERITY = [PASS, INCONCLUSIVE, FAIL]
GATE = "(gate passed)"


def forbidden(key: str) -> bool:
    """`corpus sync`, and `enrich` with any subcommand of its own."""
    return any(key == f or key.startswith(f + " ") for f in FORBIDDEN)


def _counts(rows: list) -> dict:
    """Per command, in how many of `rows` it ran; plus the gate and every
    forbidden command, under keys of their own."""
    counts = {GATE: sum(row.get("gate") == 0 for row in rows)}
    for row in rows:
        # Every command the run executed, not only those its own arm's
        # skill named: a command one arm moved out of the files the
        # scorer reads must not read as "stopped running".
        for key in row.get("ran_all", row.get("ran", [])):
            counts[key] = counts.get(key, 0) + 1
        for key in row.get("forbidden_ran", []):
            counts[f"(forbidden) {key}"] = counts.get(f"(forbidden) {key}", 0) + 1
    return counts


def _verdict(b: int, n_b: int, a: int, n_a: int, worse_when_lower: bool) -> int:
    """One row's verdict. `move` is how far the after arm went the wrong
    way, on the before arm's scale, so unequal arms compare rates."""
    scaled = a * n_b / n_a
    move = b - scaled if worse_when_lower else scaled - b
    everything_lost = b == n_b and a == 0 if worse_when_lower else b == 0 and a == n_a
    if everything_lost:
        return FAIL
    if n_b >= 6 and n_a >= 6:
        return FAIL if move >= 2 * n_b / 3 - 1e-9 else PASS
    return INCONCLUSIVE if move > 1e-9 else PASS


def measured(rows: list) -> list:
    """The runs that measured this skill on this project at all: not one
    whose prerequisite never passed its gate (a broken fixture), and not
    one whose transcript names the launch checkout (it loaded the wrong
    skills)."""
    return [
        row
        for row in rows
        if row.get("prerequisite_gate", 0) == 0 and not row.get("outside_project", False)
    ]


def usable(rows: list) -> list:
    """The measured runs whose commands and gate are judged: also not one
    that timed out or raised, whose tail never ran. Those are judged on
    their own row instead (`judge`), since a shrink can cause them."""
    return [row for row in measured(rows) if row.get("exit") not in ("timeout", "error")]


CLOCK = "(timed out or raised)"


def _clock_verdict(b: int, n_b: int, a: int, n_a: int) -> int:
    """Timeouts and errors, stricter than a command: none in 132 baseline
    runs, so a rise of two runs fails at any size and one is inconclusive."""
    rise = a * n_b / max(n_a, 1) - b
    if rise >= 2 - 1e-9:
        return FAIL
    return INCONCLUSIVE if rise > 1e-9 else PASS


def judge(before: list, after: list) -> "tuple[int, list]":
    """The verdict for one (harness, skill), and its table rows.

    3 runs an arm screen and do not convict (docs/HARNESS.md, "Measuring a
    skill change", has the rule and its arithmetic): at 3 against 3 only a
    row that went all the way the wrong way fails, and any other move is
    inconclusive, settled by 3 more runs an arm, where a move of 4 in 6
    fails and less passes. Timeouts and errors are a row of their own;
    arms that used different prompts, or with fewer than 3 usable runs,
    are inconclusive.
    """
    m_b, m_a = measured(before), measured(after)
    b_rows, a_rows = usable(m_b), usable(m_a)
    n_b, n_a = len(b_rows), len(a_rows)
    table = []
    if len(before) + len(after) > len(m_b) + len(m_a):
        broken = (len(before) - len(m_b), len(after) - len(m_a))
        table.append(("(left out: fixture, outside project)", *map(str, broken), ""))
    clock_b = sum(r.get("exit") in ("timeout", "error") for r in m_b)
    clock_a = sum(r.get("exit") in ("timeout", "error") for r in m_a)
    verdict = _clock_verdict(clock_b, len(m_b), clock_a, len(m_a)) if m_b and m_a else PASS
    mark = {PASS: "", INCONCLUSIVE: "drop?", FAIL: "FAIL"}
    table.append((CLOCK, f"{clock_b}/{len(m_b)}", f"{clock_a}/{len(m_a)}", mark[verdict]))
    prompts = (
        {row.get("prompt", "full") for row in b_rows},
        {row.get("prompt", "full") for row in a_rows},
    )
    if prompts[0] != prompts[1]:
        mixed = (
            "(arms used different prompts)",
            "/".join(sorted(prompts[0])),
            "/".join(sorted(prompts[1])),
            "drop?",
        )
        return max(verdict, INCONCLUSIVE, key=SEVERITY.index), [*table, mixed]
    if n_b < 3 or n_a < 3:
        few = ("(fewer than 3 usable runs)", str(n_b), str(n_a), "drop?")
        return max(verdict, INCONCLUSIVE, key=SEVERITY.index), [*table, few]
    b_counts, a_counts = _counts(b_rows), _counts(a_rows)
    keys = list(dict.fromkeys([k for row in b_rows + a_rows for k in row.get("expected", [])]))
    extra = sorted(k for k in set(b_counts) | set(a_counts) if k.startswith("(forbidden)"))
    for key in [GATE, *keys, *extra]:
        b, a = b_counts.get(key, 0), a_counts.get(key, 0)
        bad = _verdict(b, n_b, a, n_a, worse_when_lower=not key.startswith("(forbidden)"))
        verdict = max(verdict, bad, key=SEVERITY.index)
        table.append((key, f"{b}/{n_b}", f"{a}/{n_a}", mark[bad]))
    return verdict, table


# The harnesses whose verdict sets the exit code. Only Claude Code runs a
# skill's steps steadily enough at 3 runs an arm to gate on; Codex and
# OpenCode are judged and printed, but advisory, until #1210 steadies
# them (docs/HARNESS.md, the 2026-11-13 baseline).
GATED = ("claude",)


def compare(before_path: Path, after_path: Path, quiet: bool = False, gate=GATED) -> int:
    """`--compare`: one table per (harness, skill), then the worst verdict
    of the `gate` harnesses as the exit code -- 0 pass, 1 fail, 3
    inconclusive (rerun 3 more on both arms and compare the merged
    files). Every other harness is judged and marked advisory. A (harness,
    skill) only the before arm ran is listed and skipped, so a full
    baseline compares against a PR that ran one skill; one only the after
    arm ran, or judging no gated pair at all, is inconclusive."""

    def load(path):
        return json.loads(Path(path).read_text(encoding="utf-8"))

    groups: dict = {}
    for arm, rows in (("before", load(before_path)), ("after", load(after_path))):
        for row in rows:
            key = (row["harness"], row["skill"])
            groups.setdefault(key, {"before": [], "after": []})[arm].append(row)
    worst, skipped, judged = PASS, [], 0
    for (harness, skill), arms in sorted(groups.items()):
        if not arms["after"]:
            skipped.append(f"{harness} / {skill}")
            continue
        if not arms["before"]:
            if harness in gate:
                worst = max(worst, INCONCLUSIVE, key=SEVERITY.index)
            if not quiet:
                print(f"\n{harness} / {skill}: inconclusive -- no before runs to compare with")
            continue
        verdict, table = judge(arms["before"], arms["after"])
        if harness in gate:
            worst = max(worst, verdict, key=SEVERITY.index)
            judged += 1
        if not quiet:
            name = {PASS: "pass", FAIL: "FAIL", INCONCLUSIVE: "inconclusive"}[verdict]
            note = "" if harness in gate else " (advisory)"
            print(f"\n{harness} / {skill}: {name}{note}")
            width = max(len(row[0]) for row in table)
            for key, b, a, mark in table:
                print(f"  {key:<{width}}  {b:>5} -> {a:<5} {mark}")
    if not judged:
        # A wrong --skill or --harness on one arm, or a truncated file,
        # judges nothing; that must never read as a pass.
        worst = max(worst, INCONCLUSIVE, key=SEVERITY.index)
    if not quiet:
        if skipped:
            print(f"\nin the before arm only, not judged: {', '.join(skipped)}")
        if not judged:
            print(f"\nno {'/'.join(gate)} (harness, skill) was judged")
        verdict_name = {PASS: "pass", FAIL: "fail", INCONCLUSIVE: "inconclusive"}[worst]
        print(f"\nverdict: {verdict_name} (gated on: {', '.join(gate)})")
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
        "forbidden_ran": [key for key in ran_all if forbidden(key)],
        "ran_unnamed": [key for key in ran_all if key not in expected and not forbidden(key)],
    }
