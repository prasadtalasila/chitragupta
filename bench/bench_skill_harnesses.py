"""Does each harness load every skill, and read the files it points at? (#997)

Since #997 only `SKILL.md` is kept per harness: every reference a skill
uses lives once under `.claude/`, and the Codex and OpenCode copies name
it by its path from the project root. The unit tests prove the files
exist and the paths resolve. They cannot prove that a harness loads the
right `SKILL.md`, lets its model read a `.claude/...` path from outside
that skill's own folder, or that a model actually follows the pointer.
This measures that, against a project scaffolded from this checkout.

Tier 1, loading: for each skill and each harness, ask the model to load
the skill, read every `.claude/skills...` file its `SKILL.md` names, and
print each file's first line. A read is counted only when the printed
line matches the file, so a model that guesses fails.

Tier 2, following: one real drafting task per harness (a survey, then a
copy-edit of it), to see which references a model reads unprompted, and
at which step. That is a long run on a local model, so it is a separate
`--tier 2` and its transcript is kept for reading rather than scored.

Models: Claude Code runs `claude -p --model sonnet`; Codex and OpenCode
run on an OpenAI-compatible server at BASE_URL (a local llama-server in
the recorded runs). The server has one slot, so harnesses run one at a
time. Like everything in bench/, this is outside the test suite and its
coverage; docs/HARNESS.md records what it measured.

    python bench/bench_skill_harnesses.py --tier 1 --out /tmp/skills-t1
    python bench/bench_skill_harnesses.py --tier 1 --harness codex --skill survey-writer
    python bench/bench_skill_harnesses.py --tier 2 --out /tmp/skills-t2
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tests.test_skill_harness_copies import SKILLS, SUFFIX  # noqa: E402
from tests.test_skill_references import NAMED_PATH  # noqa: E402

EXAMPLES = REPO_ROOT / "docs" / "examples"
BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:18080/v1")
LOCAL_MODEL = os.environ.get("MODEL", "qwen3.6-35b-a3b")
HARNESSES = ("claude", "codex", "opencode")
SKILL_DIRS = {
    "claude": ".claude/skills",
    "codex": ".agents/skills",
    "opencode": ".opencode/skills",
}
READ_LINE = re.compile(r"READ\s+`?(\.claude/skills[^\s`]*)`?\s*::\s*(.*)")

TIER1_PROMPT = """\
This is a check of how skills load. It is not a drafting task: do not do
what the skill describes, and write no files.

1. Load the skill named `{name}`, the way you load any skill.
2. Its instructions name files by paths that start with `.claude/skills`.
   Read every one of those files. Skip anything else.
3. For each file you read, print exactly one line:
   READ <path> :: <the first line of that file, verbatim>
   If a file cannot be read, print: FAIL <path> :: <why>
4. Then print DONE and stop.
"""

TIER2_SURVEY = (EXAMPLES / "codex" / "prompt.txt").read_text(encoding="utf-8")
TIER2_COPYEDIT = """\
Copy-edit the draft at content/drafts/dt-survey.md: convert it to British
English (en-GB). Change no claim and no citation.
"""


def harness_env() -> dict:
    """The project's own interpreter first on PATH, and `git` off it for
    OpenCode, whose runtime never reaps a `git` child in this container
    and then waits on it forever."""
    env = dict(os.environ)
    python_dir = str(Path(sys.executable).parent)
    parts = [python_dir, *[p for p in env.get("PATH", "").split(os.pathsep) if p]]
    env["PATH"] = os.pathsep.join(parts)
    env["BASE_URL"] = BASE_URL
    env["OPENCODE_CONFIG"] = str(EXAMPLES / "opencode" / "opencode-provider.json")
    return env


def without_git(env: dict) -> dict:
    keep = [p for p in env["PATH"].split(os.pathsep) if not (Path(p) / "git").exists()]
    return {**env, "PATH": os.pathsep.join(keep)}


def scaffold(harness: str, dest: Path, sync: bool) -> Path:
    """A fresh project from this checkout's tree, not an installed one."""
    project = dest / harness / "project"
    if project.exists():
        shutil.rmtree(project)
    project.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [sys.executable, "-m", "chitragupta.init", "--agent", harness, str(project)],
        cwd=REPO_ROOT,
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


def command(harness: str, prompt: str) -> list:
    if harness == "claude":
        return [
            shutil.which("claude"),
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
            shutil.which("codex"),
            "exec",
            "--json",
            "--skip-git-repo-check",
            "--dangerously-bypass-approvals-and-sandbox",
            "--dangerously-bypass-hook-trust",
            "-c",
            "model_provider=local",
            "-c",
            f'model_providers.local={{name="local",base_url="{BASE_URL}",wire_api="responses"}}',
            "-m",
            LOCAL_MODEL,
            prompt,
        ]
    return [shutil.which("opencode"), "run", "--format", "json", prompt]


def run(harness: str, project: Path, prompt: str, log: Path, timeout: int) -> dict:
    # PWD too, not only cwd: OpenCode takes its project directory from the
    # inherited PWD, so without this it loads the skills of whichever
    # directory launched the bench (measured: it read this checkout's).
    env = {**harness_env(), "PWD": str(project)}
    if harness == "opencode":
        env = without_git(env)
    started = time.monotonic()
    with log.open("w", encoding="utf-8") as out:
        try:
            proc = subprocess.run(
                command(harness, prompt),
                cwd=project,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                check=False,
            )
            code = proc.returncode
        except subprocess.TimeoutExpired:
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
    skill_md = project / SKILL_DIRS[harness] / f"{name}{SUFFIX[harness]}" / "SKILL.md"
    text = skill_md.read_text(encoding="utf-8")
    return {m.split("#")[0] for m in NAMED_PATH.findall(text)}


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


def score_tier1(project: Path, harness: str, name: str, log: Path) -> dict:
    """Which named files the model read, judged by whether the first line
    it printed is really that file's first line, from which copy of the
    skill it loaded."""
    expected = expected_paths(project, harness, name)
    text = transcript_text(log)
    own, foreign = loaded_own_copy(harness, name, log, text)
    # A harness that resolved the project from the wrong directory reads
    # this checkout's identical files and would otherwise pass.
    leaked = str(REPO_ROOT) in text
    printed = {}
    for path, first in READ_LINE.findall(text):
        printed[path.rstrip(".,")] = first.strip()
    read, wrong = [], []
    for path in sorted(expected):
        if path not in printed:
            continue
        actual = (project / path).read_text(encoding="utf-8").splitlines()[0].strip()
        (read if printed[path].strip("`") == actual else wrong).append(path)
    return {
        "expected": sorted(expected),
        "read": read,
        "wrong_first_line": wrong,
        "missing": sorted(expected - set(printed)),
        "extra": sorted(set(printed) - expected),
        "outside_project": leaked,
        "loaded_own_copy": own,
        "loaded_claude_copy": foreign,
        "pass": set(read) == expected and not leaked and own and not foreign,
    }


def tier1(args) -> list:
    results = []
    for harness in args.harness:
        project = scaffold(harness, args.out, sync=False)
        for name in args.skill:
            loaded = f"{name}{SUFFIX[harness]}"
            log = args.out / harness / f"t1-{name}.jsonl"
            outcome = run(harness, project, TIER1_PROMPT.format(name=loaded), log, args.timeout)
            outcome.update(score_tier1(project, harness, name, log))
            outcome.update(harness=harness, skill=name)
            results.append(outcome)
            print(json.dumps(outcome), flush=True)
    return results


TOOL_INPUT_KEYS = {"file_path", "filePath", "command", "path"}


def tool_inputs(log: Path) -> str:
    """The file paths and commands of every tool call in a transcript --
    what a harness actually opened or ran, not the skill text it was
    shown, which names every reference whether or not one is read."""
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
    return "\n".join(found)


def references_read(log: Path) -> list:
    """Every `.claude/skills...references/...` file a tool call opened, in
    order of first opening."""
    seen = []
    pattern = r"\.claude/skills(?:-common|/[\w-]+)/references/[\w.-]+\.md"
    for match in re.findall(pattern, tool_inputs(log)):
        if match not in seen:
            seen.append(match)
    return seen


def tier2(args) -> list:
    results = []
    for harness in args.harness:
        project = scaffold(harness, args.out, sync=True)
        for label, prompt in (("survey", TIER2_SURVEY), ("copy-edit", TIER2_COPYEDIT)):
            log = args.out / harness / f"t2-{label}.jsonl"
            outcome = run(harness, project, prompt, log, args.timeout)
            outcome.update(harness=harness, task=label, references=references_read(log))
            gate = subprocess.run(
                [sys.executable, "-m", "chitragupta.draft", "gate", "content/drafts/dt-survey.md"],
                cwd=project,
                env=harness_env(),
                capture_output=True,
                text=True,
                check=False,
            )
            outcome["gate"] = gate.returncode
            results.append(outcome)
            print(json.dumps(outcome), flush=True)
    return results


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
    still pass. Tier 2 counts only files a tool call opened.
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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tier", type=int, choices=(1, 2), required=True)
    parser.add_argument("--harness", action="append", choices=HARNESSES)
    parser.add_argument("--skill", action="append", choices=SKILLS)
    parser.add_argument("--out", type=Path, default=Path("/tmp/skill-harness-bench"))
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args(argv)
    self_check()
    args.harness = args.harness or list(HARNESSES)
    args.skill = args.skill or list(SKILLS)
    args.out.mkdir(parents=True, exist_ok=True)
    results = tier1(args) if args.tier == 1 else tier2(args)
    (args.out / f"tier{args.tier}.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    if args.tier == 1:
        passed = sum(r["pass"] for r in results)
        print(f"tier 1: {passed}/{len(results)} passed", flush=True)
        return 0 if passed == len(results) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
