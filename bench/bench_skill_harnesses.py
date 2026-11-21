"""Does each harness load every skill, and read the files it points at? (#997)

Since #997 only `SKILL.md` is kept per harness: every reference a skill
uses lives once under `.claude/`, and the Codex and OpenCode copies name
it by its path from the project root. The unit tests prove the files
exist and the paths resolve. They cannot prove that a harness loads the
right `SKILL.md`, lets its model read a `.claude/...` path from outside
that skill's own folder, or that a model actually follows the pointer.
This measures that, against a project scaffolded from this checkout.

Tier 1, loading: for each skill and each harness, ask the model to load
the skill, read every `.claude/skills...` file its `SKILL.md` names and
every `docs/` page it or those files name, and print each file's first
line. A read is counted only when the printed line matches the file, so
a model that guesses fails.

Tier 2, following: one real task per user skill and harness
(skill_bench_tasks.py), scored by which `chitragupta` commands the skill
and its references name and which a tool call actually ran
(skill_commands.py), and by the gate on the task's draft. `--runs` and
`--jobs` repeat and parallelise it; `--compare` judges two arms
(docs/HARNESS.md, "Measuring a skill change").

Models: Claude Code runs `claude -p --model sonnet`; Codex and OpenCode
run on OpenAI-compatible servers given by `--base-url` (one local
llama-server per GPU in the recorded runs, one slot each, so each local
job holds a server of its own). Like everything in bench/, this is
outside the test suite and its coverage; docs/HARNESS.md records what it
measured.

**Run it only on a disposable machine.** To measure a harness unattended
it turns that harness's safety off: Claude Code runs with
`--permission-mode bypassPermissions`, and Codex with
`--dangerously-bypass-approvals-and-sandbox` and
`--dangerously-bypass-hook-trust`. A model then runs shell commands with
no sandbox and no approval prompt, in the scaffolded project and with
your user's access to everything else. Without `--out`, each run gets a
fresh private directory from `tempfile.mkdtemp`, never a fixed path
another user could plant files in.

    python bench/bench_skill_harnesses.py --tier 1
    python bench/bench_skill_harnesses.py --tier 1 --harness codex --skill survey-writer
    python bench/bench_skill_harnesses.py --tier 2 --out ~/bench/skills-t2
    python bench/bench_skill_harnesses.py --tier 2 --skill-only --harness codex
"""

import argparse
import json
import queue
from concurrent.futures import ThreadPoolExecutor
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tests.test_skill_harness_copies import SUFFIX, USER_SKILLS  # noqa: E402
from tests.test_skill_references import NAMED_PATH  # noqa: E402

from skill_bench_tasks import OUTLINE_TASKS, TAIL_WORDS, TIER2_TASKS  # noqa: E402  (bench/ is sys.path[0])
from skill_commands import (  # noqa: E402
    GATED,
    commands_run,
    commands_run_in,
    compare,
    expected_commands,
    handed_off,
    handoffs,
    help_choices,
    score_commands,
    skill_files,
)

EXAMPLES = REPO_ROOT / "docs" / "examples"
BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:18080/v1")
LOCAL_MODEL = os.environ.get("MODEL", "qwen3.6-35b-a3b")
# The context every llama-server is started with (serve_models.sh's -c) and
# docs/examples/opencode/opencode-provider.json declares.
LOCAL_CONTEXT = 131072
HARNESSES = ("claude", "codex", "opencode")
# Filled by main() before any scaffolding, so a missing CLI is named up
# front rather than failing inside Popen after a corpus sync.
BINARIES: dict = {}
# This checkout and `--source`: a run whose transcript names either
# resolved the project from the wrong directory (filled by main()).
LEAK_ROOTS: set = {str(REPO_ROOT)}
SKILL_DIRS = {
    "claude": ".claude/skills",
    "codex": ".agents/skills",
    "opencode": ".opencode/skills",
}
# A skill or reference file a `SKILL.md` names, in any harness's folder:
# the Codex and OpenCode copies point at their own harness's copy of
# another skill (agenda-reviser follows draft-reviser's loop), and only
# the references live under `.claude/` alone.
SKILL_FILE = re.compile(r"\.(?:claude|agents|opencode)/skills(?:-common)?/[\w./-]+?\.md")
# A `docs/` page a skill or one of its references names, at any depth,
# backticked, bare, or as a relative link (`../../../docs/X.md`, which
# every such link in the skills resolves to the project's own `docs/`).
# Not `mkdocs/x.md` or `sample-project/docs/x.md`: another folder's.
DOCS_PATH = re.compile(r"(?<![\w.-])(?<![\w-]/)docs/[\w./-]*?\.md(?!\w)")
READ_LINE = re.compile(r"READ\s+`?(?:\.\./)*(\.claude/skills[^\s`]*|docs/[^\s`]*)`?\s*::\s*(.*)")

TIER1_PROMPT = """\
This is a check of how skills load. It is not a drafting task: do not do
what the skill describes, and write no files.

1. Load the skill named `{name}`, the way you load any skill.
2. Its instructions name files by paths that start with `.claude/skills`
   or `docs/` (some as a relative link such as `../../../docs/X.md`).
   Read every one of those files, then every `docs/` file that the
   `.claude/skills` files you read name. Skip anything else.
3. For each file you read, print exactly one line, with the path from
   the project root (`docs/X.md`, never `../../../docs/X.md`):
   READ <path> :: <the first line of that file, verbatim>
   If a file cannot be read, print: FAIL <path> :: <why>
4. Then print DONE and stop.
"""


# Credentials a model must never be handed: every harness runs with its
# approvals off, and the A40 operator sets GH_TOKEN for scripts/merge_pr.py.
SECRET = re.compile(r"(?i)^(GH|GITHUB)\w*_TOKEN$|^GH_TOKEN$|^GITHUB_PAT\w*$")


def harness_env(base_url: str = BASE_URL) -> dict:
    """The project's own interpreter first on PATH, and no `PYTHONPATH`:
    one naming a checkout makes a model's `python -m chitragupta` read
    that checkout, and the run is left out as outside its project
    (measured: 21 of 36 local runs in one experiment). `run()` takes `git`
    off PATH for OpenCode and points it at `opencode_config()`."""
    env = {k: v for k, v in os.environ.items() if not SECRET.search(k) and k != "PYTHONPATH"}
    python_dir = str(Path(sys.executable).parent)
    parts = [python_dir, *[p for p in env.get("PATH", "").split(os.pathsep) if p]]
    env["PATH"] = os.pathsep.join(parts)
    env["BASE_URL"] = base_url
    env["OPENCODE_CONFIG"] = str(EXAMPLES / "opencode" / "opencode-provider.json")
    return env


def opencode_config(folder: Path) -> Path:
    """The bench's OpenCode config, written to `folder/opencode.json`: the
    provider example users copy, plus leave to read and write outside the
    project. `opencode run` answers an `external_directory` request with
    `auto-rejecting` and the run ends there (measured: a figure compiled
    in /tmp, the installed package's source). Claude Code and Codex run
    with their approvals off, so this only brings OpenCode level with
    them; the example itself keeps OpenCode's default."""
    config = json.loads(
        (EXAMPLES / "opencode" / "opencode-provider.json").read_text(encoding="utf-8")
    )
    config["permission"] = {"external_directory": "allow"}
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "opencode.json"
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return path


def without_git(env: dict, shim_root: Path) -> dict:
    """`env` with no `git` on PATH and everything else still there.

    Dropping a directory that holds `git` would drop `/usr/bin` on a
    merged-/usr host, taking `python`, `bash` and coreutils with it. A
    stub `git` does not work either: a non-executable one is skipped by
    the PATH search, and an executable one is still a child OpenCode never
    reaps. So each such directory is replaced by a shim directory that
    links every entry in it except `git`.
    """
    parts = []
    for index, entry in enumerate(env["PATH"].split(os.pathsep)):
        folder = Path(entry)
        if not (folder / "git").exists():
            parts.append(entry)
            continue
        shim = shim_root / str(index)
        if shim.exists():
            shutil.rmtree(shim)
        shim.mkdir(parents=True)
        for item in folder.iterdir():
            if item.name != "git":
                (shim / item.name).symlink_to(item)
        parts.append(str(shim))
    return {**env, "PATH": os.pathsep.join(parts)}


def scaffold(harness: str, project: Path, sync: bool, source: Path = REPO_ROOT) -> Path:
    """A fresh project from `source`'s tree, not an installed one.

    `init` takes its source tree from its own `__file__`, and `-m` imports
    from the working directory first, so running it with `cwd=source`
    scaffolds that checkout's skills. Only the scaffold comes from
    `source`: the sync, the gate and every command a model runs use the
    installed `chitragupta`, the same for both arms of a comparison.
    """
    if project.exists():
        shutil.rmtree(project)
    project.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [sys.executable, "-m", "chitragupta.init", "--agent", harness, str(project)],
        cwd=source,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    shutil.copytree(EXAMPLES / "codex" / "papers", project / "papers", dirs_exist_ok=True)
    shutil.copy(EXAMPLES / "codex" / "config.toml", project / "config.toml")
    if sync:
        subprocess.run(
            [sys.executable, "-m", "chitragupta.corpus", "sync"],
            cwd=project,
            check=True,
            env=harness_env(),
        )
    return project


def command(harness: str, prompt: str, base_url: str = BASE_URL) -> list:
    if harness == "claude":
        return [
            BINARIES["claude"],
            "-p",
            "--model",
            "sonnet",
            "--output-format",
            "stream-json",
            "--verbose",
            "--permission-mode",
            "bypassPermissions",
            prompt,
        ]
    if harness == "codex":
        return [
            BINARIES["codex"],
            "exec",
            "--json",
            "--skip-git-repo-check",
            "--dangerously-bypass-approvals-and-sandbox",
            "--dangerously-bypass-hook-trust",
            "-c",
            "model_provider=local",
            "-c",
            # json.dumps writes a valid TOML basic string, quotes escaped.
            f'model_providers.local={{name="local",base_url={json.dumps(base_url)},'
            'wire_api="responses"}',
            # Codex has no metadata for a local model, so it does not know
            # the server's window and never compacts: two runs ended on a
            # 400 at 131,625 tokens (#1210). 75% leaves room for one large
            # tool output after the last compaction.
            "-c",
            f"model_context_window={LOCAL_CONTEXT}",
            "-c",
            f"model_auto_compact_token_limit={LOCAL_CONTEXT * 3 // 4}",
            "-m",
            LOCAL_MODEL,
            prompt,
        ]
    return [BINARIES["opencode"], "run", "--format", "json", prompt]


def run(
    harness: str, project: Path, prompt: str, log: Path, timeout: int, base_url: str = BASE_URL
) -> dict:
    # PWD too, not only cwd: OpenCode takes its project directory from the
    # inherited PWD, so without this it loads the skills of whichever
    # directory launched the bench (measured: it read this checkout's).
    env = {**harness_env(base_url), "PWD": str(project)}
    if harness == "opencode":
        env = without_git(env, project.parent / "path-shim")
        env["OPENCODE_CONFIG"] = str(opencode_config(project.parent / "opencode-config"))
    started = time.monotonic()
    # Its own session, so a timeout kills the harness and everything it
    # started. `subprocess.run(timeout=)` kills only the direct child: a
    # timed-out Codex run kept its model request alive and held the local
    # server's one slot, and every run after it queued until it timed out
    # too (measured).
    with log.open("w", encoding="utf-8") as out:
        proc = subprocess.Popen(
            command(harness, prompt, base_url),
            cwd=project,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
            code = "timeout"
    return {"exit": code, "seconds": round(time.monotonic() - started)}


def transcript_text(log: Path) -> str:
    """Every string in a JSONL transcript, joined, so READ lines are found
    whichever event a harness puts its answer in. A line that is not JSON
    is kept as it is."""
    found = []

    def walk(node):
        if isinstance(node, str):
            found.append(node)
        elif isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            walk(json.loads(line))
        except ValueError:
            found.append(line)
    return "\n".join(found)


def expected_paths(project: Path, harness: str, name: str) -> set:
    """The `.claude/skills...` files the harness's `SKILL.md` names, and
    the `docs/` pages it or any of those files names: a rule a skill cites
    in a `docs/` page is read only if a model follows that pointer too."""
    skill_md = project / SKILL_DIRS[harness] / f"{name}{SUFFIX[harness]}" / "SKILL.md"
    text = skill_md.read_text(encoding="utf-8")
    named = {m.split("#")[0] for m in NAMED_PATH.findall(text)}
    texts = [text, *((project / p).read_text("utf-8") for p in named if (project / p).is_file())]
    return named | {m for t in texts for m in DOCS_PATH.findall(t)}


def loaded_own_copy(harness: str, name: str, log: Path, text: str) -> "tuple[bool, bool]":
    """(loaded its own copy, loaded the Claude copy instead).

    Every agent's project holds `.claude/skills/`, and all three copies of
    a `SKILL.md` name the same reference paths, so READ lines alone cannot
    tell an OpenCode run that loaded `survey-writer-opencode` from one that
    read `.claude/skills/survey-writer/SKILL.md`. The load itself can:
    Claude Code's `Skill` call names the skill, OpenCode's `skill` tool
    reports its base directory, and Codex opens the file by path.
    """
    if harness == "claude":
        return f'"skill":"{name}"' in log.read_text(encoding="utf-8", errors="replace"), False
    own = f"{SKILL_DIRS[harness]}/{name}{SUFFIX[harness]}"
    return own in text, f".claude/skills/{name}/SKILL.md" in text


def leaked(text: str) -> bool:
    """Whether `text` names this checkout or `--source` as a path of its
    own -- `/srv/cg` or `/srv/cg/x`, never the sibling `/srv/cg-runs`."""
    return any(re.search(re.escape(root) + r"(?![\w.-])", text) for root in LEAK_ROOTS)


def _pictographic(char: str) -> bool:
    """An emoji or other symbol, or a character that only shapes one:
    a variation selector, a zero-width joiner, a skin-tone modifier, a
    keycap, a tag -- and U+FFFD, what an emoji becomes when a model's
    output mangles its bytes."""
    point = ord(char)
    return (
        unicodedata.category(char) == "So"
        or point in (0x200D, 0x20E3, 0xFFFD)
        or 0xFE00 <= point <= 0xFE0F
        or 0x1F3FB <= point <= 0x1F3FF
        or 0xE0000 <= point <= 0xE01EF
    )


def first_line_key(line: str) -> str:
    """What two first lines are compared by.

    Wrapping backticks are the model's, so both sides lose them: stripping
    only the printed side failed every first line that itself ends in a
    backtick (`draft-diff.md`'s heading). Pictographs go too, with the
    space around them: many `docs/` headings open on an emoji, and a model
    that prints the heading with the emoji garbled to U+FFFD, or dropped,
    has still read the file (the agenda-reviser baseline, 2026-11-14).
    Every other character, words included, still has to match.
    """
    unwrapped = line.strip().strip("`")
    marked = "".join("\0" if _pictographic(char) else char for char in unwrapped)
    return re.sub(r"\s*\0[\s\0]*", " ", marked).strip()


def score_tier1(project: Path, harness: str, name: str, log: Path) -> dict:
    """Which named files the model read, judged by whether the first line
    it printed is really that file's first line, from which copy of the
    skill it loaded."""
    expected = expected_paths(project, harness, name)
    text = transcript_text(log)
    own, foreign = loaded_own_copy(harness, name, log, text)
    # A harness that resolved the project from the wrong directory reads
    # this checkout's identical files and would otherwise pass.
    outside = leaked(text)
    # A model may print a path absolute, inside its own project; the
    # file is the same one, so it is made relative before matching.
    for root in {str(project.resolve()), str(project)}:
        text = text.replace(root + "/", "")
    printed = {}
    for path, first in READ_LINE.findall(text):
        printed[path.rstrip(".,")] = first.strip()
    read, wrong, firsts = [], [], {}
    for path in sorted(p for p in expected if (project / p).is_file()):
        lines = (project / path).read_text(encoding="utf-8").splitlines()
        actual = first_line_key(next(iter(lines), ""))
        firsts.setdefault(actual, []).append(path)
        if path not in printed:
            continue
        (read if first_line_key(printed[path]) == actual else wrong).append(path)
    # Two named files that open on the same line cannot tell a read of
    # one from a read of the other, so the skill fails until one changes.
    # It is the same key as the read itself: two headings that differ only
    # by emoji are one line once emoji are ignored.
    shared = sorted(p for paths in firsts.values() if len(paths) > 1 for p in paths)
    return {
        "expected": sorted(expected),
        "read": read,
        "wrong_first_line": wrong,
        "missing": sorted(expected - set(printed)),
        "extra": sorted(set(printed) - expected),
        "outside_project": outside,
        "loaded_own_copy": own,
        "loaded_claude_copy": foreign,
        "shared_first_line": shared,
        "pass": set(read) == expected and not outside and own and not foreign and not shared,
    }


def tier1(args) -> list:
    results = []
    for harness in args.harness:
        project = scaffold(harness, args.out / harness / "project", False, args.source)
        for name in args.skill:
            loaded = f"{name}{SUFFIX[harness]}"
            log = args.out / harness / f"t1-{name}.jsonl"
            prompt = TIER1_PROMPT.format(name=loaded)
            outcome = run(harness, project, prompt, log, args.timeout, args.base_url[0])
            outcome.update(score_tier1(project, harness, name, log))
            outcome.update(harness=harness, skill=name)
            results.append(outcome)
            print(json.dumps(outcome), flush=True)
    return results


TOOL_INPUT_KEYS = {"file_path", "filePath", "command", "path"}


def score_run(source: Path, harness: str, skill: str, log: Path) -> dict:
    """Task 2's fields for one run, against the commands the harness's own
    copy of the skill, in the scaffolded checkout, names -- and those of
    each skill it hands a step to -- plus how the run loaded each of
    those skills (`skill_load`)."""
    folder, name = SKILL_DIRS[harness], f"{skill}{SUFFIX[harness]}"
    inputs = tool_input_list(log)
    files = skill_files(source, folder, name, SKILL_FILE)
    scored = score_commands(expected_commands(*files), commands_run(inputs))
    targets = handed_off(source, folder, name)
    scored["handoffs_loaded"] = {t: skill_load(log, inputs, folder, t) for t in targets}
    return scored


def tool_input_list(log: Path) -> list:
    """The file paths and commands of every tool call in a transcript, one
    entry per call -- what a harness actually opened or ran, not the skill
    text it was shown, which names every reference whether or not one is
    read. One entry per call, so a command is parsed on its own and one
    bad quote spoils only its own call."""
    found = []

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in TOOL_INPUT_KEYS and isinstance(value, str):
                    found.append(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            walk(json.loads(line))
        except ValueError:
            continue
    return found


def tool_inputs(log: Path) -> str:
    """`tool_input_list`, joined."""
    return "\n".join(tool_input_list(log))


def references_read(log: Path) -> list:
    """Every `.claude/skills...references/...` file a tool call opened, in
    order of first opening."""
    seen = []
    pattern = r"\.claude/skills(?:-common|/[\w-]+)/references/[\w.-]+\.md"
    for match in re.findall(pattern, tool_inputs(log)):
        if match not in seen:
            seen.append(match)
    return seen


def skill_load(log: Path, inputs: list, folder: str, name: str) -> "str | None":
    """How a run loaded skill `name`: "skill" through the harness's skill
    tool, "read" by opening its `SKILL.md` in `folder` with a file tool
    or a shell command, None when the transcript shows neither.

    Claude Code's `Skill` call carries `{"skill": name}` and OpenCode's
    `skill` tool `{"name": name}`; Codex has no skill tool, so a read is
    its only load. A read is not rare elsewhere either: in the 36 Claude
    Code genre-writer transcripts of the 2026-11-13/14 baselines, 22
    loaded `figure-drawer` by reading its `SKILL.md` and 14 through
    `Skill`. A read of another harness's copy is not this harness's
    skill, and is not counted.
    """
    called = False

    def walk(node):
        nonlocal called
        if isinstance(node, dict):
            state = node.get("state")
            given = node.get("input") or (state.get("input") if isinstance(state, dict) else None)
            tool = node.get("name") or node.get("tool")
            if tool in ("Skill", "skill") and isinstance(given, dict):
                called = called or name in (given.get("skill"), given.get("name"))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            walk(json.loads(line))
        except ValueError:
            continue
    if called:
        return "skill"
    path = re.compile(re.escape(f"{folder}/{name}/SKILL.md") + r"(?![\w.-])")
    return "read" if any(path.search(one) for one in inputs) else None


def gate(project: Path, draft: str) -> int:
    """`draft gate`'s exit code on the task's own draft, or 2 when the run
    never wrote it (a gate on a missing file is not a pass)."""
    if not (project / draft).exists():
        return 2
    return subprocess.run(
        [sys.executable, "-m", "chitragupta.draft", "gate", draft],
        cwd=project,
        env=harness_env(),
        capture_output=True,
        text=True,
        check=False,
    ).returncode


def tier2_job(args, harness: str, skill: str, k: int, servers: "queue.Queue") -> dict:
    """One (harness, skill, run): a fresh project, the task's prerequisite
    if it has one, then the task, scored on the task's transcript only.

    A local-model job holds one server for its whole length, prerequisite
    included, so two jobs never share a llama-server slot."""
    task = TIER2_TASKS[skill]
    root = args.out / harness / skill / f"run-{k}"
    project = scaffold(harness, root / "project", True, args.source)
    if task.setup is not None:
        task.setup(project)
    url = servers.get() if harness != "claude" else BASE_URL
    prerequisite = {}
    try:
        if task.after is not None:
            before = root / f"prerequisite-{task.after}.jsonl"
            prompt = task_prompt(args, task.after, prerequisite=True)
            run(harness, project, prompt, before, args.timeout, url)
            # The task's input: a prerequisite that never passed its gate
            # hands the task a broken draft, which is read with the score.
            prerequisite = {"prerequisite_gate": gate(project, TIER2_TASKS[task.after].draft)}
        if task.seed is not None:
            task.seed(project)
        log = root / "transcript.jsonl"
        outcome = run(harness, project, task_prompt(args, skill), log, args.timeout, url)
    finally:
        if harness != "claude":
            servers.put(url)
    outcome.update(harness=harness, skill=skill, run=k, references=references_read(log))
    outcome["prompt"] = "skill-only" if args.skill_only else "full"
    if args.outline and skill in OUTLINE_TASKS:
        outcome["prompt"] += "+outline"
    # A run that resolved its project from this checkout or `--source`
    # measured the wrong skills; `--compare` leaves it out.
    outcome["outside_project"] = leaked(transcript_text(log))
    outcome.update(prerequisite)
    outcome.update(score_run(args.source, harness, skill, log))
    outcome["gate"] = gate(project, task.draft)
    print(json.dumps(outcome), flush=True)
    return outcome


def task_prompt(args, skill: str, prerequisite: bool = False) -> str:
    """The task's skill-only prompt under `--skill-only` (no closing steps
    named, so only the skill can make a model run them), else its full
    one. A prerequisite always gets the full prompt: a reviser is measured
    on what it does to a complete survey, not on a survey's own skips."""
    tasks = OUTLINE_TASKS if args.outline and not prerequisite else {}
    task = tasks.get(skill, TIER2_TASKS[skill])
    return task.prompt(skill_only=args.skill_only and not prerequisite)


def tier2(args) -> list:
    servers: "queue.Queue" = queue.Queue()
    for url in args.base_url:
        servers.put(url)
    jobs = [
        (harness, skill, k)
        for k in range(1, args.runs + 1)
        for skill in args.skill
        for harness in args.harness
        if skill in TIER2_TASKS
    ]
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(safe_job, args, *job, servers) for job in jobs]
        return [future.result() for future in futures]


def safe_job(args, harness: str, skill: str, k: int, servers, job=None) -> dict:
    """`tier2_job`, or an error row when it raises: one failing fixture
    must not throw away a multi-hour run's other rows. `--compare` leaves
    an error row out, as it does a timeout."""
    try:
        return (job or tier2_job)(args, harness, skill, k, servers)
    except Exception as error:  # noqa: BLE001 -- recorded, never swallowed
        row = {"harness": harness, "skill": skill, "run": k, "exit": "error", "gate": 2}
        row["error"] = f"{type(error).__name__}: {error}"
        if job is None:  # a real job; the self-check's own fake stays quiet
            print(json.dumps(row), flush=True)
        return row


def check_args(args) -> "str | None":
    """Why these flags cannot run, or None."""
    if not (Path(args.source) / "chitragupta" / "init.py").is_file():
        return f"--source {args.source} holds no chitragupta/init.py: not a checkout"
    if args.jobs < 1 or getattr(args, "runs", 1) < 1:
        return "--jobs and --runs must be at least 1"
    return None


def jobs_warning(args) -> "str | None":
    """Local jobs beyond the number of servers wait for a free one."""
    local = [h for h in args.harness if h != "claude"]
    if local and args.jobs > len(args.base_url):
        return (
            f"--jobs {args.jobs} with {len(args.base_url)} --base-url: local-model jobs "
            "beyond that wait for a free server"
        )
    return None


def self_check() -> None:
    """Prove the scoring before trusting a pass rate built on it.

    `bench/` sits outside the test suite and its coverage (bench/README.md),
    so this runs on every invocation instead. Tier 1 counts a read only
    when the printed first line is the file's own, so the guards are
    the ways that comparison could pass a read that never happened: a
    wrong first line must not count, a path never printed must be
    reported missing rather than passed, a run that touched this checkout
    instead of its own project, or loaded another copy of the skill, must
    fail even though the files there are identical -- and a clean run must
    still pass. A `docs/` page is held to the same rule, and two named
    files sharing a first line fail. Tier 2 counts only files a tool call
    opened.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        skill = project / SKILL_DIRS["claude"] / "x" / "SKILL.md"
        ref = project / ".claude" / "skills-common" / "references"
        skill.parent.mkdir(parents=True)
        ref.mkdir(parents=True)
        skill.write_text(
            "Read `.claude/skills-common/references/a.md` and "
            "`.claude/skills-common/references/b.md`.\n",
            encoding="utf-8",
        )
        (ref / "a.md").write_text("# A heading\n", encoding="utf-8")
        (ref / "b.md").write_text("# B heading\n", encoding="utf-8")
        log = project / "log.jsonl"
        log.write_text(
            json.dumps({"result": "READ .claude/skills-common/references/a.md :: # A heading"})
            + "\nREAD .claude/skills-common/references/b.md :: # Not the heading\n",
            encoding="utf-8",
        )
        scored = score_tier1(project, "claude", "x", log)
        assert scored["read"] == [".claude/skills-common/references/a.md"], scored
        assert scored["wrong_first_line"] == [".claude/skills-common/references/b.md"], scored
        assert not scored["pass"], "a wrong first line must fail the skill"
        log.write_text(
            "READ .claude/skills-common/references/a.md :: # A heading\n", encoding="utf-8"
        )
        scored = score_tier1(project, "claude", "x", log)
        assert scored["missing"] == [".claude/skills-common/references/b.md"], scored
        assert not scored["pass"], "an unread file must fail the skill"
        log.write_text(
            f"READ .claude/skills-common/references/a.md :: # A heading\n{REPO_ROOT}/x\n"
            "READ .claude/skills-common/references/b.md :: # B heading\n",
            encoding="utf-8",
        )
        scored = score_tier1(project, "claude", "x", log)
        assert scored["outside_project"] and not scored["pass"], scored
        good = (
            json.dumps({"name": "Skill", "input": {"skill": "x"}}, separators=(",", ":"))
            + "\nREAD .claude/skills-common/references/a.md :: # A heading"
            + "\nREAD .claude/skills-common/references/b.md :: # B heading\n"
        )
        log.write_text(good, encoding="utf-8")
        assert score_tier1(project, "claude", "x", log)["pass"], "a clean run must pass"
        log.write_text(good.replace('"skill":"x"', '"skill":"y"'), encoding="utf-8")
        assert not score_tier1(project, "claude", "x", log)["pass"], "another skill's load"
        log.write_text(
            json.dumps({"input": {"file_path": ".claude/skills-common/references/a.md"}})
            + "\nThe skill names `.claude/skills-common/references/b.md`.\n",
            encoding="utf-8",
        )
        assert references_read(log) == [".claude/skills-common/references/a.md"]
        for name, task in [*TIER2_TASKS.items(), *OUTLINE_TASKS.items()]:
            only = task.prompt(skill_only=True).lower()
            named = [word for word in TAIL_WORDS if word in only]
            assert not named, f"{name}'s skill-only prompt names a closing step: {named}"
            assert task.tail.strip() and task.tail in task.prompt(), f"{name}'s full prompt"
        log.write_text(
            json.dumps(
                {"input": {"command": "python -m chitragupta.draft render x.md --format md"}}
            )
            + "\nThe skill names `python -m chitragupta.draft references x.md`.\n",
            encoding="utf-8",
        )
        ran = commands_run(tool_input_list(log))
        assert ran == ["draft render"], "a command a tool call ran counts; one only named does not"
        _check_tier1_reads(project, log)
        _check_tier1_docs(project, log)
        _check_command_scoring(project)
        _check_handoffs(project)
        _check_compare(project)
        _check_shell_shapes()
        _check_help_layouts()
        (ref / "b.md").write_text("", encoding="utf-8")
        log.write_text(good, encoding="utf-8")
        scored = score_tier1(project, "claude", "x", log)
        assert scored["wrong_first_line"] == [".claude/skills-common/references/b.md"], scored
        tools = project / "bin"
        tools.mkdir()
        for name in ("git", "python"):
            (tools / name).write_text("", encoding="utf-8")
        env = without_git({"PATH": str(tools)}, project / "shim")
        shim = Path(env["PATH"])
        assert sorted(p.name for p in shim.iterdir()) == ["python"], "only git is hidden"
        _check_harness_env(project)
        _check_flag_guards(project)


def _check_tier1_reads(project: Path, log: Path) -> None:
    """Two ways a real read was scored as a failure (measured 2026-11-13,
    9 of 14 Tier 1 failures): a first line that itself ends in a backtick,
    and a path printed absolute rather than from the project root."""
    skill = project / SKILL_DIRS["claude"] / "y" / "SKILL.md"
    ref = project / ".claude" / "skills" / "y" / "references"
    skill.parent.mkdir(parents=True)
    ref.mkdir(parents=True)
    skill.write_text(
        "Read `.claude/skills/y/references/c.md` and `.claude/skills/y/references/d.md`.\n",
        encoding="utf-8",
    )
    (ref / "c.md").write_text("# Showing what changed: `draft diff`\n", encoding="utf-8")
    (ref / "d.md").write_text("# D heading\n", encoding="utf-8")
    load = json.dumps({"name": "Skill", "input": {"skill": "y"}}, separators=(",", ":"))
    log.write_text(
        f"{load}\nREAD .claude/skills/y/references/c.md :: # Showing what changed: `draft diff`\n"
        f"READ {project}/.claude/skills/y/references/d.md :: `# D heading`\n",
        encoding="utf-8",
    )
    scored = score_tier1(project, "claude", "y", log)
    assert scored["read"] == sorted(scored["expected"]) and scored["pass"], scored
    log.write_text(
        f"{load}\nREAD .claude/skills/y/references/c.md :: # Showing what changed: `draft`\n"
        "READ .claude/skills/y/references/d.md :: # D heading\n",
        encoding="utf-8",
    )
    scored = score_tier1(project, "claude", "y", log)
    assert scored["wrong_first_line"] == [".claude/skills/y/references/c.md"], scored


def _check_tier1_docs(project: Path, log: Path) -> None:
    """A `docs/` page named by `SKILL.md` (backticked, bare, or as a
    relative link) or by a reference it names is expected and scored like
    a reference; another folder's `docs/` is not; and two named files
    that open on one line fail, since neither read can then be told."""
    skill = project / SKILL_DIRS["claude"] / "w" / "SKILL.md"
    ref = project / ".claude" / "skills" / "w" / "references" / "r.md"
    docs = project / "docs" / "sub"
    ref.parent.mkdir(parents=True)
    docs.mkdir(parents=True)
    skill.write_text(
        "Follow `docs/A.md` §3, see [the rules](../../../docs/B.md#-rules) and docs/A.md,\n"
        "never `mkdocs/C.md` or `sample-project/docs/C.md`; read "
        "`.claude/skills/w/references/r.md`.\n",
        encoding="utf-8",
    )
    ref.write_text("# R heading\nThen `docs/sub/D.md`.\n", encoding="utf-8")
    for path, first in (("A.md", "# A doc"), ("B.md", "# B doc"), ("sub/D.md", "# D doc")):
        (project / "docs" / path).write_text(f"{first}\nbody\n", encoding="utf-8")
    want = ["docs/A.md", "docs/B.md", "docs/sub/D.md", ".claude/skills/w/references/r.md"]
    load = json.dumps({"name": "Skill", "input": {"skill": "w"}}, separators=(",", ":"))
    good = (
        f"{load}\nREAD .claude/skills/w/references/r.md :: # R heading\n"
        "READ docs/A.md :: # A doc\nREAD ../../../docs/B.md :: # B doc\n"
        "READ docs/sub/D.md :: # D doc\n"
    )
    log.write_text(good, encoding="utf-8")
    scored = score_tier1(project, "claude", "w", log)
    assert scored["expected"] == sorted(want) and scored["pass"], scored
    log.write_text(good.replace(":: # D doc", ":: # D"), encoding="utf-8")
    scored = score_tier1(project, "claude", "w", log)
    assert scored["wrong_first_line"] == ["docs/sub/D.md"] and not scored["pass"], scored
    log.write_text(good.replace("READ docs/A.md :: # A doc\n", ""), encoding="utf-8")
    scored = score_tier1(project, "claude", "w", log)
    assert scored["missing"] == ["docs/A.md"] and not scored["pass"], scored
    (project / "docs" / "B.md").write_text("# A doc\n", encoding="utf-8")
    log.write_text(good.replace(":: # B doc", ":: # A doc"), encoding="utf-8")
    scored = score_tier1(project, "claude", "w", log)
    assert scored["shared_first_line"] == ["docs/A.md", "docs/B.md"], scored
    assert not scored["pass"], "two files that open on one line prove neither read"
    (project / "docs" / "B.md").write_text("# B doc\n", encoding="utf-8")
    _check_tier1_emoji(project, log, good)


def _check_tier1_emoji(project: Path, log: Path, good: str) -> None:
    """A heading's emoji is a symbol, not the read: the agenda-reviser
    baseline (2026-11-14) printed `docs/AUTO-IMPROVEMENT-RATIONALE.md`'s
    heading whole but for a replacement character where its emoji was,
    and was scored a wrong first line. Pictographs are ignored on both
    sides; every word still has to match, and two headings that differ
    only by emoji are one shared first line."""
    docs = project / "docs"
    (docs / "A.md").write_text("# \U0001f4a1 A doc\nbody\n", encoding="utf-8")
    (docs / "sub" / "D.md").write_text(
        "# \U0001f9d1\u200d\U0001f4bb\ufe0f D doc\n", encoding="utf-8"
    )
    garbled = good.replace(":: # A doc", ":: # \ufffd A doc").replace(
        ":: # D doc", ":: # \ufffd\ufffd D doc"
    )
    log.write_text(garbled, encoding="utf-8")
    scored = score_tier1(project, "claude", "w", log)
    assert scored["pass"] and not scored["wrong_first_line"], f"a garbled emoji: {scored}"
    log.write_text(good, encoding="utf-8")
    scored = score_tier1(project, "claude", "w", log)
    assert scored["pass"] and not scored["wrong_first_line"], f"a missing emoji: {scored}"
    log.write_text(garbled.replace("\ufffd A doc", "\ufffd A page"), encoding="utf-8")
    scored = score_tier1(project, "claude", "w", log)
    assert scored["wrong_first_line"] == ["docs/A.md"] and not scored["pass"], scored
    (docs / "B.md").write_text("# \U0001f4d0 A doc\n", encoding="utf-8")
    log.write_text(good.replace(":: # B doc", ":: # A doc"), encoding="utf-8")
    scored = score_tier1(project, "claude", "w", log)
    assert scored["shared_first_line"] == ["docs/A.md", "docs/B.md"], scored
    assert not scored["pass"], "two headings that differ only by emoji prove neither read"


def _check_command_scoring(project: Path) -> None:
    """Task 2's five cases: fenced and inline both expected; `-P` is the
    same command; named but not run is missed; `corpus sync` is never
    expected, and is reported when it ran."""
    skill_md = project / "cmd-skill.md"
    skill_md.write_text(
        "Run `python -m chitragupta.draft gate <draft>`, never "
        "`python -m chitragupta.corpus sync`.\n\n```bash\n"
        "python -P -m chitragupta.draft dossier stamp content/drafts/x.md\n"
        "python -m chitragupta.draft render twin-basics --format pdf\n```\n",
        encoding="utf-8",
    )
    expected = expected_commands(skill_md)
    assert expected == ["draft gate", "draft dossier stamp", "draft render"], expected
    pointer = project / "cmd-ref.md"
    pointer.write_text("Then `python -m chitragupta.draft evidence <draft>`.\n", encoding="utf-8")
    both = expected_commands(skill_md, pointer)
    assert both == expected + ["draft evidence"], "a reference's command is expected too"
    # Each harness's copy points at that harness's copy of another skill
    # (agenda-reviser reads `.opencode/skills/draft-reviser-opencode/...`).
    own = project / SKILL_DIRS["opencode"] / "a-opencode" / "SKILL.md"
    other = project / SKILL_DIRS["opencode"] / "b-opencode" / "SKILL.md"
    own.parent.mkdir(parents=True)
    other.parent.mkdir(parents=True)
    own.write_text("Follow `.opencode/skills/b-opencode/SKILL.md`.\n", encoding="utf-8")
    other.write_text("Run `python -m chitragupta.draft diff <draft>`.\n", encoding="utf-8")
    log = project / "empty.jsonl"
    log.write_text("", encoding="utf-8")
    assert score_run(project, "opencode", "a", log)["expected"] == ["draft diff"], "own harness"
    ran = commands_run(
        [
            "/bin/zsh -lc 'python -m chitragupta.draft dossier stamp x.md; echo done'",
            'grep "python -m chitragupta.draft gate" x.md',
            "echo python -m chitragupta.draft render x.md",
            "python -m chitragupta.corpus sync",
            "cd p && python3 -P -m chitragupta.draft gate x.md",
        ]
    )
    scored = score_commands(expected, ran)
    assert scored["ran"] == ["draft dossier stamp", "draft gate"], scored
    assert scored["missed"] == ["draft render"], "a mention is not a run: " + str(scored)
    assert scored["forbidden_ran"] == ["corpus sync"], scored


# (skill text, the skills it hands a step to and gets back from). The
# first two are the real wordings, wrapped as the skills wrap them; the
# rest name a sibling without handing it a step, and must not pull its
# commands into the caller's expected set.
HANDOFF_SHAPES = [
    (
        "Hand the drawing itself to `figure-drawer`, and come back to this\n   step",
        ["figure-drawer"],
    ),
    ("**To redraw it, hand it to `figure-drawer`**\n  and come back to step 6", ["figure-drawer"]),
    ("| Hand off to `corpus-reviser` -- not this skill |", []),
    ("To change a survey, use `draft-reviser` instead.", []),
    ("a shorter figure, drawn through `figure-drawer`. Never edit", []),
    ("Hand it to `x`. Then come back to this step.", []),
    ("If `figure-drawer` was not loaded, come back and run it yourself.", []),
]


def _check_handoffs(project: Path) -> None:
    """A step handed to a sibling skill keeps its commands there: they are
    the caller's expected commands, the sibling's references' too, on the
    harness's own copies only; a sibling merely mentioned adds nothing; a
    handoff cycle ends; and the run records how it loaded the sibling."""
    for text, want in HANDOFF_SHAPES:
        assert handoffs(text) == want, f"{text!r}: {handoffs(text)}, want {want}"
    folder = project / SKILL_DIRS["opencode"]
    for name, text in {
        "c-opencode": "Run `python -m chitragupta.draft gate x`. Hand the loop to\n"
        "`l-opencode`, and come back to this step. Hand it to `l`, and come back.\n"
        "To revise, use `r-opencode` instead.\n",
        "l-opencode": "Run `python -m chitragupta.review agenda x`, then read\n"
        "`.claude/skills/l/references/loop.md`. Hand a check to `c-opencode`, and come back.\n",
        "r-opencode": "Run `python -m chitragupta.draft diff x`.\n",
    }.items():
        (folder / name).mkdir(parents=True)
        (folder / name / "SKILL.md").write_text(text, encoding="utf-8")
    (project / ".claude/skills/l/references").mkdir(parents=True)
    loop = project / ".claude/skills/l/references/loop.md"
    loop.write_text("Then `python -m chitragupta.draft style x`.\n", encoding="utf-8")
    assert handed_off(project, SKILL_DIRS["opencode"], "c-opencode") == ["l-opencode"]
    files = skill_files(project, SKILL_DIRS["opencode"], "c-opencode", SKILL_FILE)
    assert files[-1] == loop, "the handed-off skill's reference is read too"
    log = project / "handoff.jsonl"
    log.write_text("", encoding="utf-8")
    scored = score_run(project, "opencode", "c", log)
    want = ["draft gate", "review agenda", "draft style"]
    assert scored["expected"] == want, f"no `r` command, no cycle: {scored['expected']}"
    assert scored["handoffs_loaded"] == {"l-opencode": None}, scored
    loads = [
        ({"tool": "skill", "state": {"input": {"name": "l-opencode"}}}, "skill"),
        ({"name": "Skill", "input": {"skill": "l-opencode"}}, "skill"),
        ({"input": {"command": "cat .opencode/skills/l-opencode/SKILL.md"}}, "read"),
        ({"input": {"filePath": f"{project}/.opencode/skills/l-opencode/SKILL.md"}}, "read"),
        ({"input": {"filePath": ".claude/skills/l/SKILL.md"}}, None),
        ({"tool": "skill", "state": {"input": {"name": "r-opencode"}}}, None),
        ({"input": {"command": "cat .opencode/skills/l-opencode/SKILL.md.bak"}}, None),
    ]
    for event, how in loads:
        log.write_text(json.dumps(event) + "\n", encoding="utf-8")
        got = score_run(project, "opencode", "c", log)["handoffs_loaded"]["l-opencode"]
        assert got == how, f"{event}: {got}, want {how}"


# (one tool call's command, the command keys it ran). Each row is a shape
# a real transcript produced or a reviewer found the scorer misreading.
SHELL_SHAPES = [
    ("cat >> r.md <<'EOF'\nIt's done.\nEOF\npython -m chitragupta.draft gate x", ["draft gate"]),
    ("cat > n.md <<EOF\npython -m chitragupta.draft render x\nEOF", []),
    ("cat >> r.md <<'EOF'\nrun `python -m chitragupta.enrich` first\nEOF", []),
    ("cat <<-EOF > n.md\n\tpython -m chitragupta.draft render x\n\tEOF\necho ok", []),
    ("echo it's\npython -m chitragupta.draft style x", ["draft style"]),
    ("python -m chitragupta.draft gate --help", []),
    ("python -m chitragupta.corpus sync -h", []),
    ("cd p\n\npython -m chitragupta.draft gate x", ["draft gate"]),
    ("cd p &&\npython -m chitragupta.draft gate x", ["draft gate"]),
    ("(cd p); python -m chitragupta.draft gate x", ["draft gate"]),
    ("python -m chitragupta draft dossier stamp x", ["draft dossier stamp"]),
    ("python -W ignore -X utf8 -m chitragupta.draft gate x", ["draft gate"]),
    ("bash -e -c 'python -m chitragupta.draft gate x'", ["draft gate"]),
    ("echo time python -m chitragupta.draft render x", []),
    ("echo python -m chitragupta.draft gate", []),
    (
        "python -m chitragupta.draft gate x  # check\npython -m chitragupta.draft render x",
        ["draft gate", "draft render"],
    ),
    ("cd p # go\npython -m chitragupta.draft gate x", ["draft gate"]),
    ('OUT="$(python -m chitragupta.draft gate x 2>&1)"', ["draft gate"]),
    ("OUT=`python -m chitragupta.draft gate x`", ["draft gate"]),
    ("echo $((1<<4))\npython -m chitragupta.draft gate x", ["draft gate"]),
    ("echo $((x<<y))\npython -m chitragupta.draft gate x", ["draft gate"]),
    ("cat <<\\EOF > n.md\npython -m chitragupta.draft render x\nEOF", []),
    ("cat <<'END-OF' > n.md\npython -m chitragupta.draft render x\nEND-OF", []),
    ("# python -m chitragupta.draft render x", []),
    ("grep '$(python -m chitragupta.draft gate x)' f", []),
]


def _check_shell_shapes() -> None:
    for command, want in SHELL_SHAPES:
        got = commands_run_in(command)
        assert got == want, f"{command!r}: ran {got}, want {want}"


CLICK_HELP = """Usage: python -m chitragupta.draft [OPTIONS] COMMAND [ARGS]...

  The drafting layer.

Options:
  -h, --help  Show this message and exit.

Commands:
  gate        Verify every citekey in a draft against the ledger
  dossier     The working state behind a draft: create it...
  diff        What changed
  a-command-name-long-enough-to-wrap
                    Its description, on a line of its own

  Run 'python -m chitragupta.draft COMMAND --help' for a command's flags.
"""


def _check_help_layouts() -> None:
    """The subcommands a `--help` lists, in the click-style layout every
    command prints now and in the argparse usage line an older install
    prints; a leaf command lists none, and an option's choices are not
    subcommands."""
    want = {"gate", "dossier", "diff", "a-command-name-long-enough-to-wrap"}
    assert help_choices(CLICK_HELP) == want, help_choices(CLICK_HELP)
    old = "usage: draft.py [-h] {gate,dossier,diff} ...\n\nThe drafting layer.\n"
    assert help_choices(old) == {"gate", "dossier", "diff"}, help_choices(old)
    leaf = "Usage: python -m chitragupta.draft gate [OPTIONS] FILE...\n\n  Fail if...\n"
    assert help_choices(leaf) == frozenset(), "a leaf has no subcommands"
    option = "usage: x [-h] [--where {host,docker}]\n"
    assert help_choices(option) == frozenset(), "an option's choices"


def _check_compare(project: Path) -> None:
    """3 against 3 screens: equal passes, all to none fails, any other move
    is inconclusive. 6 against 6 settles: a move of 4 fails, less passes.
    The gate and a forbidden command follow the same rule as a command;
    a run that measured its fixture or the clock is left out."""

    def arm(
        name,
        ran_in,
        runs=3,
        gated=3,
        forbidden=0,
        broken=0,
        timeouts=0,
        skills=("x",),
        harness="claude",
        outside=0,
        prompt="skill-only",
    ):
        rows = [
            {
                "harness": harness,
                "skill": skill,
                "run": k,
                "exit": "timeout" if k > runs - timeouts else 0,
                "expected": ["draft gate"],
                "ran": ["draft gate"] if k <= ran_in else [],
                "forbidden_ran": ["corpus sync"] if k <= forbidden else [],
                "gate": 0 if k <= gated else 1,
                "prerequisite_gate": 2 if k > runs - broken else 0,
                "outside_project": k <= outside,
                "prompt": prompt,
            }
            for skill in skills
            for k in range(1, runs + 1)
        ]
        path = project / f"{name}.json"
        path.write_text(json.dumps(rows), encoding="utf-8")
        return path

    assert compare(arm("b", 3), arm("a", 3), quiet=True) == 0, "equal arms pass"
    assert compare(arm("b", 3), arm("a", 2), quiet=True) == 3, "a one-run drop is inconclusive"
    assert compare(arm("b", 3), arm("a", 0), quiet=True) == 1, "3 to 0 fails"
    assert compare(arm("b", 3), arm("a", 1), quiet=True) == 3, "3 to 1 only screens"
    assert compare(arm("b", 2), arm("a", 0), quiet=True) == 3, "2 to 0 is not every run"
    assert compare(arm("b", 6, 6), arm("a", 3, 6), quiet=True) == 0, "6v6: a three-run drop passes"
    assert compare(arm("b", 6, 6), arm("a", 2, 6), quiet=True) == 1, "6v6: a four-run drop fails"
    assert compare(arm("b", 3, gated=1), arm("a", 3, gated=0), quiet=True) == 3, "gate 1 to 0"
    assert compare(arm("b", 3, gated=3), arm("a", 3, gated=0), quiet=True) == 1, "gate 3 to 0"
    assert compare(arm("b", 3), arm("a", 3, forbidden=1), quiet=True) == 3, "one new forbidden"
    assert compare(arm("b", 3), arm("a", 3, forbidden=3), quiet=True) == 1, "forbidden every run"
    assert compare(arm("b", 3, forbidden=1), arm("a", 3, forbidden=1), quiet=True) == 0
    assert compare(arm("b", 6, 6), arm("a", 6, 6, forbidden=4), quiet=True) == 1, "6v6: +4"
    assert compare(arm("b", 3), arm("a", 2, broken=1), quiet=True) == 3, "a broken fixture"
    assert compare(arm("b", 3), arm("a", 2, timeouts=1), quiet=True) == 3, "a timeout"
    assert compare(arm("b", 3), arm("a", 1, timeouts=2), quiet=True) == 1, "two new timeouts"
    steady = arm("b", 3, timeouts=1), arm("a", 3, timeouts=1)
    assert compare(*steady, quiet=True) == 3, "a timed-out run is not judged on its commands"
    assert compare(arm("b", 6, 6), arm("a", 3, 6, timeouts=3), quiet=True) == 1, "6v6: 3 timeouts"
    assert compare(arm("b", 3), arm("a", 3, outside=1), quiet=True) == 3, "a run outside"
    assert compare(arm("b", 3), arm("a", 3, prompt="full"), quiet=True) == 3, "mixed prompts"
    empty = project / "empty.json"
    empty.write_text("[]", encoding="utf-8")
    assert compare(arm("b", 3), empty, quiet=True) == 3, "nothing judged is not a pass"
    assert compare(arm("b", 3), arm("a", 3, harness="codex"), quiet=True) == 3, "no gated pair"
    after_more = arm("a", 3, skills=("x", "z"))
    assert compare(arm("b", 3), after_more, quiet=True) == 3, "a gated skill only after"
    assert compare(arm("b", 3), arm("a", 0, broken=3), quiet=True) == 3, "no usable runs"
    both = arm("b", 3, skills=("x", "y"))
    assert compare(both, arm("a", 3), quiet=True) == 0, "a skill in one arm only is skipped"
    moved = arm("a", 3)
    rows = json.loads(moved.read_text(encoding="utf-8"))
    for row in rows:
        row.update(expected=[], ran=[], ran_all=["draft gate"])
    moved.write_text(json.dumps(rows), encoding="utf-8")
    assert compare(arm("b", 3), moved, quiet=True) == 0, "a command the after arm stopped naming"
    # Only the gated harnesses set the exit code (Claude Code by default,
    # docs/HARNESS.md): a local harness's fail is reported, and advisory.
    local_b, local_a = arm("lb", 3, harness="codex"), arm("la", 0, harness="codex")
    for path, claude in ((local_b, arm("cb", 3)), (local_a, arm("ca", 3))):
        rows = json.loads(path.read_text(encoding="utf-8"))
        rows += json.loads(claude.read_text(encoding="utf-8"))
        path.write_text(json.dumps(rows), encoding="utf-8")
    assert compare(local_b, local_a, quiet=True) == 0, "codex is advisory by default"
    assert compare(local_b, local_a, quiet=True, gate=("claude", "codex")) == 1, "unless gated"


def _check_harness_env(tmp: Path) -> None:
    """A `PYTHONPATH` naming a checkout makes a model's `python -m
    chitragupta` read that checkout, and the run is then left out as
    outside its project; OpenCode's own config must let a run read and
    write outside its project, or `opencode run` auto-rejects the request
    and the run ends there. Both measured (#1210)."""
    saved = os.environ.get("PYTHONPATH")
    os.environ["PYTHONPATH"] = str(REPO_ROOT)
    try:
        assert "PYTHONPATH" not in harness_env(), "PYTHONPATH reaches the harness"
    finally:
        if saved is None:
            del os.environ["PYTHONPATH"]
        else:
            os.environ["PYTHONPATH"] = saved
    path = opencode_config(tmp / "oc")
    config = json.loads(path.read_text(encoding="utf-8"))
    example = json.loads(
        (EXAMPLES / "opencode" / "opencode-provider.json").read_text(encoding="utf-8")
    )
    assert config["permission"] == {"external_directory": "allow"}, config
    assert {k: v for k, v in config.items() if k != "permission"} == example, "the example"
    assert "permission" not in example, "the user-facing example stays as it was"
    assert example["provider"]["local"]["models"][LOCAL_MODEL]["limit"]["context"] == LOCAL_CONTEXT
    saved_binaries = dict(BINARIES)
    BINARIES["codex"] = "codex"
    try:
        codex = command("codex", "x")
    finally:
        BINARIES.clear()
        BINARIES.update(saved_binaries)
    assert f"model_context_window={LOCAL_CONTEXT}" in codex, codex
    assert f"model_auto_compact_token_limit={LOCAL_CONTEXT * 3 // 4}" in codex, codex


def _raise(*_args) -> dict:
    raise RuntimeError("boom")


def _check_flag_guards(tmp: Path) -> None:
    """`--source` must be a checkout, and more local jobs than servers
    must be said out loud rather than discovered as a slow run."""
    plain = argparse.Namespace(source=tmp, jobs=1, base_url=[BASE_URL], harness=["codex"])
    assert check_args(plain) is not None, "--source without chitragupta/init.py"
    good = argparse.Namespace(source=REPO_ROOT, jobs=1, base_url=[BASE_URL], harness=["codex"])
    assert check_args(good) is None, "this checkout is a valid --source"
    for bad in ({"jobs": 0}, {"runs": 0}):
        flags = argparse.Namespace(source=REPO_ROOT, jobs=1, runs=1, base_url=[], harness=[])
        assert check_args(argparse.Namespace(**{**vars(flags), **bad})) is not None, bad
    leak = tmp / "leak.jsonl"
    leak.write_text(f"cd {REPO_ROOT}-runs/x\n", encoding="utf-8")
    assert not leaked(leak.read_text(encoding="utf-8")), "a sibling folder is not this checkout"
    assert leaked(f"cd {REPO_ROOT}\n") and leaked(f"cat {REPO_ROOT}/x"), "this checkout is"
    saved = {k: os.environ.get(k) for k in ("GH_TOKEN", "GITHUB_TOKEN")}
    os.environ.update(GH_TOKEN="x", GITHUB_TOKEN="y")
    try:
        env = harness_env()
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    assert "GH_TOKEN" not in env and "GITHUB_TOKEN" not in env and env["PATH"], "no token"
    row = safe_job(argparse.Namespace(), "codex", "x", 1, None, job=_raise)
    assert row["exit"] == "error" and "boom" in row["error"], "a failed job is a row, not a crash"
    busy = argparse.Namespace(source=REPO_ROOT, jobs=3, base_url=[BASE_URL], harness=["codex"])
    assert check_args(busy) is None and jobs_warning(busy), "3 jobs on 1 server warns"
    assert not jobs_warning(good), "1 job on 1 server is quiet"
    assert set(TIER2_TASKS) == set(USER_SKILLS) - {"figure-drawer"} or set(TIER2_TASKS) == set(
        USER_SKILLS
    ), "every user skill has a Tier 2 task"
    for name, task in TIER2_TASKS.items():
        assert task.after is None or task.after in TIER2_TASKS, f"{name} runs after a task"


def parse(argv) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tier", type=int, choices=(1, 2))
    parser.add_argument("--harness", action="append", choices=HARNESSES)
    parser.add_argument("--skill", action="append", choices=USER_SKILLS)
    parser.add_argument("--out", type=Path, help="default: a fresh private temporary directory")
    parser.add_argument("--timeout", type=int, default=900, help="seconds per run (default 900)")
    parser.add_argument(
        "--skill-only",
        action="store_true",
        help="tier 2: leave every task's closing steps out of its prompt, so only the "
        "skill asks for them (the arm a shrink is gated on)",
    )
    parser.add_argument(
        "--outline",
        action="store_true",
        help="tier 2: survey-writer's task opens its dossier with an outline, which makes "
        "the critique step's `draft dossier status` required and not optional",
    )
    parser.add_argument(
        "--source", type=Path, default=REPO_ROOT, help="the checkout whose skills are scaffolded"
    )
    parser.add_argument(
        "--base-url",
        action="append",
        help=f"an OpenAI-compatible server, repeatable, one local job each (default {BASE_URL})",
    )
    parser.add_argument("--jobs", type=int, default=1, help="(harness, skill, run) jobs at once")
    parser.add_argument("--runs", type=int, default=1, help="tier 2: runs of each task")
    parser.add_argument(
        "--compare",
        nargs=2,
        type=Path,
        metavar=("BEFORE", "AFTER"),
        help="compare two tier2.json files; exit 0 pass, 1 fail, 3 inconclusive",
    )
    parser.add_argument(
        "--gate",
        action="append",
        choices=HARNESSES,
        help="--compare: a harness whose verdict sets the exit code, repeatable "
        "(default claude; the others are advisory, docs/HARNESS.md)",
    )
    args = parser.parse_args(argv)
    if args.compare is None and args.tier is None:
        parser.error("one of --tier or --compare is required")
    args.source = args.source.resolve()
    args.base_url = args.base_url or [BASE_URL]
    args.harness = args.harness or list(HARNESSES)
    args.skill = args.skill or list(USER_SKILLS)
    return args


def main(argv=None) -> int:
    args = parse(argv)
    self_check()
    if args.compare is not None:
        return compare(*args.compare, gate=tuple(args.gate or GATED))
    problem = check_args(args)
    if problem:
        print(problem, file=sys.stderr)
        return 2
    warning = jobs_warning(args)
    if warning:
        print(f"warning: {warning}", file=sys.stderr)
    LEAK_ROOTS.update({str(REPO_ROOT), str(args.source)})
    BINARIES.update({h: shutil.which(h) for h in args.harness})
    missing = [h for h, path in BINARIES.items() if path is None]
    if missing:
        print(f"not on PATH: {', '.join(missing)}; install it or drop --harness", file=sys.stderr)
        return 2
    if args.out is None:
        args.out = Path(tempfile.mkdtemp(prefix="skill-harness-bench-"))
    args.out.mkdir(parents=True, exist_ok=True)
    print(f"writing to {args.out}", flush=True)
    results = tier1(args) if args.tier == 1 else tier2(args)
    (args.out / f"tier{args.tier}.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    if args.tier == 1:
        passed = sum(r["pass"] for r in results)
        print(f"tier 1: {passed}/{len(results)} passed", flush=True)
        return 0 if passed == len(results) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
