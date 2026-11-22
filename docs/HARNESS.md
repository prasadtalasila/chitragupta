# 🔌 Harnesses: one citekey gate on Claude Code, Codex and OpenCode

Status: **implemented.**

Continue support is open, in
[issue 901](https://github.com/prasadtalasila/chitragupta/issues/901).
The task-by-task plan for the rest is
[plans/812-harness-neutral-core.md](https://github.com/prasadtalasila/chitragupta/blob/main/plans/812-harness-neutral-core.md).

This page records why the pipeline runs on more than one agent harness,
how the gate is enforced on each, and which designs were turned down.
Several of the rejected designs look like the obvious fix, and each one
fails the same test: **can the model skip it?**

**Written for** anyone adding a harness, changing a launcher, or
wondering why the OpenCode plugin holds no gate logic. It assumes
[HOOKS.md](HOOKS.md), whose three-layer rule (checks, adapters,
launcher) this extends, and [ARCHITECTURE.md](ARCHITECTURE.md)'s
"Grounding is enforced, not requested".

## 🎯 Why more than one harness

The Python package has always been harness-neutral: nothing under
`chitragupta/` calls a language model, and retrieval's embedding models
run locally. Everything above it assumed Claude Code. That shuts out
two kinds of user:

- a researcher without a Claude Code subscription, who drafts in Codex
  or OpenCode;
- a researcher who keeps the corpus on their own hardware and runs a
  local model through one of those harnesses.

A small local model is the one most likely to fabricate a citekey, so
another harness is supported only if the one binding rule is exactly as
strong there.

## ❗ The problem

Without per-harness work, three facts make the gate Claude Code-only:

1. `.claude/hooks/citation_gate_hook.py` fires on Claude Code's
   `Write|Edit` matcher and reads `tool_input.file_path`.
2. Codex edits through `apply_patch`, whose payload carries the patch
   text in `tool_input.command` and no `file_path`. A hook that reads
   only `file_path` finds no path there and fails open: a gate that
   looks like it passed.
3. Pandoc alone does not refuse a fabricated key. Before render ran the
   gate, `--format md` refused a key missing from the ledger only as a
   side effect of building the numbered reference list, while docx, pdf
   and tex printed pandoc's citeproc warning and wrote the document
   anyway (measured).

OpenCode reads none of `.claude/settings.json`, so without its plugin it
has no check at all.

## 🧱 The design: three checks over one gate

Every check calls `chitragupta/citation_gate.py`. No gate logic is
copied into a skill, a hook launcher or a plugin.

1. **Self-check (asked).** Before presenting, each skill runs
   `python -m chitragupta.draft gate` on its own draft and fixes what it
   reports. Each harness gets its own copy of the skill, naming its own
   tools (see "Skills: one copy per harness" below).
2. **Mandatory check (enforced).** A thin per-harness launcher runs the
   existing hook scripts on every write to a draft. The model cannot
   skip it, and it is told to fix the key before it moves on. That holds
   only while it writes through the harness's own file tools, which
   Codex behind llama.cpp does not offer it
   ([LOCAL-MODELS.md](LOCAL-MODELS.md)).
3. **Last check.** `draft render` runs the gate before producing any
   format, so no draft with an unknown key becomes a document on any
   harness.

The mandatory check is the one that needed per-harness work, and it was
kept as small as possible:

- **The hooks live in `.claude/hooks/`**, and Codex and OpenCode launch
  the same scripts. A neutral folder would churn about 28 test files for
  no change in behaviour.
- **The hooks read one extra payload shape**: `apply_patch` patch text.
  Codex and OpenCode use the same envelope (OpenAI's V4A grammar), so
  one parser, `.claude/hooks/patch_paths.py`, serves both. Every draft
  a patch adds, updates or moves is gated. A patch that mentions
  `content/drafts/` but whose headers cannot be read is **blocked**:
  the one deliberate exception to "malformed stdin fails open", because
  failing open there is the silently inert gate HOOKS.md exists to
  prevent.
- **The OpenCode plugin is a transport.** It turns OpenCode's tool
  arguments into the payload the hooks already read, pipes it to
  `citation_gate_hook.py` and then `style_check_hook.py`, and hands the
  verdict and any style notes back. Which writes are drafts, the size
  bound, the timeout and the fail-closed rules are the Python hook's,
  shared by all three harnesses.
- **A liveness warning covers the hook that never fires.** `draft gate`
  run by hand warns about a draft no hook has checked since it last
  changed. It never changes the gate's exit code.

## 🗂 What each harness enforces

| Harness | Self-check | Mandatory check | Last check |
| --- | --- | --- | --- |
| Claude Code | the skill runs `draft gate` | `PostToolUse` hook on Write and Edit, after the write | `draft render` |
| Codex | the skill runs `draft gate` | `PostToolUse` hook on `apply_patch`, after the write, once the project's hooks are trusted and only if the model server passes `apply_patch` through (llama.cpp does not) | `draft render` |
| OpenCode | the skill runs `draft gate` | plugin on `tool.execute.after`, after the write | `draft render` |

None of them stops a write through the shell, such as
`echo ... >> content/drafts/x.md`, because no harness's file-tool hook
sees it. `draft render` refuses the draft, and the skill's own
`draft gate` run warns that no hook checked it. A person copying text
straight out of the raw draft file is outside every check.

## 📂 Skills: one copy per harness

Each skill's `SKILL.md` exists once per harness, and each copy names
that harness's own tools. A model then reads a complete instruction at
the step where it acts ("use `Edit`, never `Write`" on Claude Code,
"patch with `apply_patch`" on Codex, "`edit`, never `write`" on
OpenCode) instead of a harness-neutral phrase it has to translate.

```text
<project root>
├── AGENTS.md                      # all harnesses read it
├── .claude/
│   ├── settings.json              # Claude Code's hook launchers
│   ├── hooks/                     # the hook scripts all three harnesses run
│   ├── agents/                    # Claude Code subagents
│   ├── skills/<name>/
│   │   ├── SKILL.md               # Claude Code wording
│   │   ├── references/            # this skill's detail, read on demand
│   │   └── assets/                # template files a skill copies from
│   └── skills-common/references/  # detail several skills share
├── .agents/
│   └── skills/<name>/SKILL.md     # Codex wording
├── .codex/
│   └── hooks.json                 # Codex's hook launchers → .claude/hooks/
└── .opencode/
    ├── opencode.json              # denies the unsuffixed skill names
    ├── plugins/chitragupta-gate.js
    ├── chitragupta/gate.js
    └── skills/<name>-opencode/SKILL.md  # OpenCode wording
```

| Harness | Skills it sees | Why only those |
| --- | --- | --- |
| Claude Code | `.claude/skills/*` | the only skills folder it reads |
| Codex | `.agents/skills/*` | the only project skills folder it reads (measured) |
| OpenCode | `.opencode/skills/*-opencode` | it also scans `.claude/skills/` and `.agents/skills/`, but `.opencode/opencode.json` denies those names (measured, 3 of 3 runs) |

OpenCode's copies carry a suffix because OpenCode keys skills by name
and loads every folder it scans concurrently, so among same-named copies
the last to load wins, which in practice is random. The suffixed names
cannot collide, and the `skill` permission in `.opencode/opencode.json`,
which filters the list the model is shown, denies every unsuffixed name.
That holds per project, with no environment variable. The OpenCode
copies refer to one another by the suffixed names; `AGENTS.md` says so
in one line.

For `init --agent`, `claude` (the default) writes `.claude/` and the
shared core; `codex` adds `.codex/` and `.agents/`; `opencode` adds
`.opencode/`. `.claude/` is written for every harness because it holds
the hook scripts Codex and OpenCode launch too; Codex never reads its
skills and OpenCode denies them.

The copies are edited by hand. `tests/test_skill_harness_copies.py`
normalises each copy through `tests/fixtures/skill_harness_phrases.toml`,
which lists every phrase meant to differ, and requires the three results
to be identical, naming the first line that moved. It also checks that
no copy names another harness's tools and that the deny list names
exactly the unsuffixed skills; `chitragupta doctor` reports an OpenCode
project whose deny list is missing or incomplete. To change a skill,
change every copy, with a phrase-map entry for any wording meant to
differ. The step scans
(`tests/test_skill_*_step.py`) read only `.claude/skills/`; once the
copies agree, a required step present in one is present in all three.

### Developer-only skills

A skill for working on this repository rather than with the pipeline,
so far `demo-recorder` (which records the feature demo) and
`skill-bench` (which measures a skill change on all three harnesses),
carries one extra frontmatter field:

```yaml
metadata:
  audience: developer
```

It keeps its three copies and its deny rule, so every checkout's
harness offers it, but no distribution carries it: `chitragupta init`
and `scripts/release.py` skip any skill folder
`chitragupta/developer_skills.py` finds marked, scripts included.
`pyproject.toml` names every other skill folder one by one, because
Poetry's `exclude` cannot take a path back out of an `include`d folder,
so a new user-facing skill needs three `include` lines, and
`tests/test_developer_skills.py` fails until it has them. The step scans
and the user-facing skill counts skip developer-only skills. The deny
rule still ships: a rule for a name a project lacks has no effect.

### Only `SKILL.md` is per harness

Everything else a skill uses exists once, under `.claude/`:
`.claude/skills/<name>/references/` for one skill's detail,
`.claude/skills/<name>/assets/` for a template it copies from, and
`.claude/skills-common/references/` for a passage several skills share.
All three copies of `SKILL.md` name those files by their path from the
project root. That works because every harness preloads only a skill's
name and description, loads the `SKILL.md` body when the skill is used,
and leaves every other file for the model to open by path with its
ordinary file tools (the Claude Code skills docs, Codex's
`ext/skills/src/catalog_prompt.rs`, OpenCode's
`packages/opencode/src/tool/skill.ts`). Codex resolves a relative path
against the skill's folder first, which is why the paths are written
from the project root and say so. `.claude/` is scaffolded for every
`--agent`, so the files are always there.

deep-research's agent definitions in `.claude/agents/` work the same
way: Codex does each agent's work itself and OpenCode dispatches a
`general` subagent, both following the agent's file by path.

The price is one rule: **a shared file names no skill and no harness
tool.** OpenCode must be sent to `<name>-opencode`, so a sentence that
routes to another skill stays in `SKILL.md`, where the phrase map and
the suffix rule apply. `tests/test_skill_references.py` checks that
every path a `SKILL.md` names exists, every reference is named by some
`SKILL.md`, no shared file names a skill or a tool, and the Codex and
OpenCode folders hold `SKILL.md` and nothing else.

**Measured** with `bench/bench_skill_harnesses.py` on freshly scaffolded
projects (Claude Code on `sonnet`; Codex 0.159.3 and OpenCode 1.18.34 on
Qwen3.6-35B-A3B through llama-server). Tier 1 asks each harness to load
a skill and print the first line of every `.claude/` file it names; a
read counts only when that line matches. It now also asks for every
`docs/` page named and ignores emoji, which the table predates:

| Harness | Loaded its own copy | `.claude/` reads that failed | Every named file read |
| --- | ---: | ---: | ---: |
| Claude Code | 10 of 10 | 0 | 10 of 10 |
| Codex | 10 of 10 | 0 | 7 of 10 |
| OpenCode | 10 of 10 | 0 | 7 of 10 |

Every shortfall was the local model listing fewer paths than the skill
names, or a run passing its time cap, never a path that failed to
resolve or a read that was refused.

**A pointer alone is not enough for a step that must run.** With the
critique step reduced to "read `critique.md` and follow it", a Claude
Code run went straight to the gate. A pointer that also says the step
**is not done until the loop the reference describes has run** holds:
with the step inline, as such a pointer, and as a handoff to a separate
skill, 12 of 12 Claude Code runs in every arm reached the loop, logged a
critique entry in `revisions.md` and passed the gate. The local-model
runs logged no critique entry in any arm, so they could not tell the
arms apart. On that evidence the owner decided that the loop's commands
may move to `.claude/skills-common/references/critique.md`, one genre
writer at a time, each benched. `tests/test_skill_pregate_feedback_step.py`
lists which steps are pointers and fails if an inline step loses its
commands, or a pointer step loses that sentence, keeps a command, or its
reference loses one. Otherwise, move rationale and detail into a
reference and keep the commands a step requires in `SKILL.md`.

**The render step is the other measured exception.** survey-writer's
`draft references`, `draft render` and `draft evidence` steps were cut
to a pointer at
`.claude/skills-common/references/render-and-references.md`, and the
task prompt no longer asked for a render. Every pointer-only run on all
three harnesses opened the reference and ran the steps, and every final
draft passed the gate; the one partial skip was a Codex run with the
commands inline. That licenses moving this step, which the four genre
writers and deep-research now do, and nothing more.

The bench works around two harness facts, both recorded in the script:
OpenCode takes its project directory from the inherited `PWD`, and a
timed-out Codex run holds the local server's one slot until its process
group is killed.

## 🚫 Designs turned down, and why

**An MCP server with gated `draft_write` / `draft_edit` tools, as the
enforcement.** A pre-write gate enforces only if the model has no other
way to write, and on every harness it has one: its built-in edit tool,
or the shell. On Codex, Claude Code and OpenCode the hook or plugin
already covers the built-in tools, so the server would be a second write
path to maintain and secure for no added guarantee. It belongs to #901,
where Continue has no hooks and the server, with Continue's built-in
write tools excluded, *is* the enforcement. Its planned security
choices: it writes only `content/drafts/`, reads only `content/`, opens
the ledger read-only with no sync tool, speaks stdio only, and is
launched through the installed `chitragupta mcp` command so a planted
`chitragupta/` cannot be imported in its place.

**The gate in a script each skill runs, instead of a hook.** The model
decides whether to run a skill's script. That is the "asked, not
enforced" posture ARCHITECTURE.md rules out, and the model likeliest to
skip the step is also the likeliest to fabricate. It is kept as the
self-check, never as the only check. No `scripts/` folder either: the
self-check is already one CLI call, and a script in each of eleven
skills would be eleven copies of it.

**A pre-write check inside the OpenCode plugin.** To gate the text an
`edit` *would* produce, the plugin would have to reproduce OpenCode's
fuzzy `oldString` matching: a second implementation of someone else's
edit semantics, inside the one component that must not drift. The
plugin checks the file on disk after the write, as Claude Code's and
Codex's hooks do.

**Rely on render alone.** It catches a fabricated key only at the end,
and loses the model fixing a bad key *in the draft, before moving on*.

**A file watcher that quarantines bad drafts.** It acts after the
write, races a person editing the same file, is invisible to the
model, and needs platform-specific file-change APIs or polling.

**A "closest match" suggestion in a refusal.** Offering the nearest
ledger key invites the model to swap in a real key for a paper it never
read. That passes the gate, so it is worse than a fabricated key. Every
refusal names the bad key and its line, and nothing else.

**A git pre-commit hook.** `content/drafts/` is gitignored, so a draft
is never committed.

**Hand-kept copies of each skill with no check between them.** Eleven
skills of 1,800-6,300 words, copied three ways, would drift, and a copy
that drifts on the gate step is a fabrication path. The copies exist
only because the phrase-map test fails on any drift outside the entries
meant to differ.

**One harness-neutral wording, with a tool glossary in `AGENTS.md`.**
Tried and replaced. "Edit the passage in place" gives up Claude Code's
exact tool names and gives Codex and OpenCode nothing specific, and the
glossary asks the model to connect a phrase to a table in another file
that Claude Code does not even load.

**Generating the copies from one templated source.** It gives the same
protection as the phrase-map test, at the cost of a build step and a
source nobody reads. The copies are plain files, each editable where it
is read.

**Relying on OpenCode's folder order, or `OPENCODE_DISABLE_EXTERNAL_SKILLS`.**
There is no folder order: OpenCode picks among same-named copies at
random. The environment variable restricts it to `.opencode/skills/`,
but a project cannot set it, and a user who forgets it gets a random
mix. The suffix and the deny list are per project.

## 📚 Harness facts learned

Each fact the code depends on is re-checked on a real session before it
is relied on.

- **Codex hooks** load from `<repo>/.codex/hooks.json` and fire on
  `PostToolUse` for `apply_patch`, with `tool_name: "apply_patch"` and
  the patch in `tool_input.command`. The `{"decision": "block"}` output
  shape matches Claude Code's.
  ([Codex hooks](https://developers.openai.com/codex/hooks))
- **Codex skips project hooks until they are trusted**, each against
  its current hash, so a changed hook is skipped until trusted again.
  An untrusted gate looks like one that passed, which is why the
  liveness warning exists.
- **Codex reads skills from `.agents/skills/`**
  ([Codex skills](https://developers.openai.com/codex/skills)), and
  `AGENTS.md` natively.
- **OpenCode reads skills from `.opencode/skills/`, and also from
  `.claude/skills/` and `.agents/skills/` for compatibility**
  ([OpenCode skills](https://opencode.ai/docs/it/skills/)).
- **OpenCode plugins** hook `tool.execute.before` and
  `tool.execute.after`. Its `edit` tool takes `filePath`, `oldString`,
  `newString` and `replaceAll`; its `apply_patch` tool takes
  `patchText`, whose paths are relative to the project root.
  ([OpenCode plugins](https://opencode.ai/docs/en/plugins/),
  [OpenCode tools](https://opencode.ai/docs/tools/))
- **Continue** reads Agent Skills and supports MCP. Its CLI loads
  Claude Code-style hooks but never runs them on a tool call (measured
  on `cn` 1.5.47, [LOCAL-MODELS.md](LOCAL-MODELS.md)), and can mark a
  built-in tool `exclude`.
  ([Continue tool permissions](https://docs.continue.dev/cli/tool-permissions))
- **The Agent Skills specification** limits `description` to 1,024
  characters and allows only `name`, `description`, `license`,
  `compatibility`, `metadata` and `allowed-tools` in the frontmatter.
  Every skill carries a `tags:` key outside that list, which all three
  harnesses load anyway (measured).
  ([agentskills.io](https://agentskills.io))

## ⚖ Decisions a maintainer made

- **Render refusing in every format is a MINOR change.**
  DEVELOPER-AGENTS.md calls a change MAJOR when it requires an existing
  user to change how they invoke the pipeline, and a docx render with an
  unknown key fails rather than succeeding with a warning. The call is
  that writing a document with an unknown key was never intended
  behaviour, so refusing it closes a gap rather than breaking an
  invocation. There is no flag to let such a render through.
- **Continue is out of scope here**; it is #901, together with the MCP
  server.
- **OpenCode is built alongside Codex**, not after it, since it needs
  no MCP server and reuses the same hook scripts.

## 🔬 Measured, and what is still not

Measured with Codex 0.159.0 and OpenCode 1.18.33 in a project scaffolded
by `chitragupta init`, with a scripted stand-in model, so each harness
ran its own real tools, hooks and plugins and the stand-in logged what
came back to the model.

**Codex:**

- The gate hook fires on `apply_patch`, and the model receives the
  gate's refusal in place of the tool's output, naming the bad key and
  its line. The session-start preflight arrives as a developer message.
  One patch adding two drafts is gated as one call. The payloads are in
  `tests/fixtures/harness_payloads/`.
- **Project hooks do not run until trusted.** In an untrusted project a
  fabricated key landed with "Success"; the hand-run gate then printed
  the liveness warning.
- **A hook runs in the session's working directory**, and Codex sets no
  project-directory variable, so a relative launcher fails to start from
  any subfolder. Each launcher line walks up to `.codex/hooks.json` and
  runs the hook under `python -P`; blocking from `content/` is measured.
- A `description` over 1,024 characters loads but is cut at 1,024 in
  what the model sees, so its end (often the "use X instead" routing)
  is lost. A `tags:` key loads.

**OpenCode:**

- **The plugin blocks all three file tools**: `write`, `edit` and
  `apply_patch` (offered to GPT models instead), each refused with the
  gate's report as the tool's result. `tool.execute.after` receives the
  same `args` as the before-hook, so the plugin needs only that.
- **Skill discovery** loads one copy per name, chosen arbitrarily when
  a name is in several folders; the deny list gives it exactly its own
  copy (3 of 3 runs). A long description is kept whole.
- **An environment trap:** in one container OpenCode's runtime never
  reaped a `git` child process, and the turn never went out. With `git`
  off `PATH` everything ran. A harness that stalls before its first model
  call in a sandbox is worth checking for a zombie child first.

**Still not measured:** whether a Codex advisory note (the style hook's)
reaches the model; and Codex's gate hook on a local model, since
llama.cpp dropped `apply_patch` and the model wrote through the shell
([LOCAL-MODELS.md](LOCAL-MODELS.md),
[#904](https://github.com/prasadtalasila/chitragupta/issues/904)).

### Measuring a skill change: commands run, and the pass rule

A shrink can leave a step's command in a skill and still make a model
stop running it, and no unit test sees that. `skill-bench` measures it.
Each Tier 2 run of `bench/bench_skill_harnesses.py` records, for its
(harness, skill):

- `expected`: every `chitragupta` command the harness's copy of
  `SKILL.md` and the references it names hold, as `module sub [sub]`
  with subcommands taken from `--help`. A skill this one hands a step to
  and takes it back from (a sentence that hands something to a skill
  and says "and come back", as with `figure-drawer`) adds its commands
  too; a skill only named adds nothing.
- `handoffs_loaded`: how the run loaded each such skill: `"skill"`
  through the skill tool, `"read"` by opening its `SKILL.md`, or `null`.
- `ran` and `missed`: which of those a tool call executed, counted only
  where a shell would run it. A `grep`, an `echo`, a heredoc line and a
  `--help` call are not runs.
- `forbidden_ran`: `corpus sync` or `enrich`, which only the user runs.
- `gate`: `draft gate` on the task's own draft, 2 when it was never
  written; and `prerequisite_gate`, the same for a reviser's starting
  survey.

**The gated arm is `--skill-only`.** Without it the prompt names the
closing steps, and a prompt that names a step makes a model run it
whatever the skill says. `--compare BEFORE AFTER` judges each (harness,
skill) on every command either arm expected, leaving out a run whose
prerequisite failed its gate or that loaded the wrong checkout, and
counting timeouts and errors on a row of their own:

| Usable runs per arm | Fail (exit 1) | Inconclusive (exit 3) | Pass (exit 0) |
| --- | --- | --- | --- |
| fewer than 3 | -- | always | -- |
| 3 against 3 | the row went all the way the wrong way: a command or the gate in every before run and no after run, or a forbidden command in no before run and every after run | any other move the wrong way | no move the wrong way |
| 6 against 6 | an all-the-way move, or a move of 4 runs or more | -- | anything else |

On the timeout-or-error row a rise of 2 runs fails and a rise of 1 is
inconclusive. Arms with different prompts, an (harness, skill) only the
after arm ran, or a comparison that judged nothing gated are
inconclusive. On exit 3, run 3 more on both arms into a fresh `--out`,
join each arm's runs into one JSON list, and compare again.

**Only Claude Code gates.** The exit code is the worst verdict of the
`--gate` harnesses, `claude` by default; Codex and OpenCode are printed
as advisory: with the run-ending failures fixed (below), an unchanged
skill still fails a comparison over all three harnesses 6% to 10% of
the time for the median skill and up to 20% for the worst, against 0%
to 7% on Claude Code alone.
Three runs screen and do not convict: the rule fails a row at 3 runs
only on all-to-none, so an unchanged skill rarely fails, while a step
dropped outright still does. Results are comparable within one host and
model build only.

**The baselines** are in `bench/results/2026-11-13-skill-bench-baseline/`
(full prompt) and `bench/results/2026-11-14-skill-bench-skill-only/`
(the before arm a shrink is measured against):

| Harness | Usable runs | Gate passed | Named commands run | Median run |
| --- | ---: | ---: | ---: | ---: |
| Claude Code (`sonnet`) | 33 of 33 | 33 | 74% | 336 s |
| Codex 0.159.3 (Qwen3.6) | 32 of 33 | 30 | 49% | 443 s |
| OpenCode 1.18.34 (Qwen3.6) | 31 of 33 | 24 | 48% | 280 s |

Claude Code's A/A comparison failed nothing. Codex skips the dossier
bookkeeping but its drafts still pass the gate; OpenCode's
non-interactive mode ends a run on a read outside the project, so whole
tails of steps go unrun. The skill-only arm on Claude Code also passed
the gate in all 33 runs, with 74% of named commands run.

**The local harnesses, rebaselined (2026-11-21).** Three causes outside
the skills ended local runs early, and each is fixed in the bench's own
setup, with no skill changed:

- Codex sent the PNG that `figure look` writes to a `llama-server` with
  no vision projector, got `500 image input is not supported`, and
  exited. `serve_models.sh` now serves the model's own
  `mmproj-F16.gguf`, which `install_tools.sh` pins by size and hash.
- `opencode run` answered an `external_directory` request (a figure
  compiled in `/tmp`, the installed package's source) with
  `auto-rejecting`, and the run ended. The bench gives OpenCode its own
  config, the provider example plus `"permission": {"external_directory":
  "allow"}`, written beside each run; the example users copy keeps
  OpenCode's default.
- Codex has no metadata for a local model, so it never compacted and two
  runs ended on a 400 at 131,625 tokens. The bench passes
  `model_context_window` and an auto-compact limit at 75% of it.

The bench also drops `PYTHONPATH` from every harness's environment, and
reads subcommands from the click-style `--help` every command now
prints; before that it found none. The skill-only arm of every user
skill, 3 runs a harness, is in
`bench/results/2026-11-21-local-harness-rebaseline/`. Its commands ran
on the package as of `9862c8cb`; 50 of its 66 runs were scaffolded from
the skills as of `0fd52e29a` and 16 OpenCode runs from those of
`9862c8cb`, which differ only in the wording of the style step:

| Harness | Usable runs | Gate passed | Named commands run | Median run |
| --- | ---: | ---: | ---: | ---: |
| Codex 0.159.3 (Qwen3.6) | 32 of 33 | 32 | 54% | 456 s |
| OpenCode 1.18.34 (Qwen3.6) | 31 of 33 | 31 | 58% | 546 s |

No run hit an image error, an auto-reject or the context limit. The
three unusable runs timed out at 1,500 seconds: Codex's agenda-reviser
once and OpenCode's deep-research twice. One cause remains that no
setting reaches: now and then the model writes a tool call whose
arguments are not JSON, `llama-server` answers 500, and Codex resends
the same history five times and exits (2 runs in an earlier arm the
same day, none in the recorded one). After the shrinks Codex runs
`draft dossier init` in every genre writer's run, but in no
review-digest run: at its step 0 it writes `scope.md` and the other
dossier files by hand.

`bench/simulate_false_fail.py` says how often an unchanged skill would
fail `--compare` at 3 runs an arm, drawing both arms from one skill's
measured runs. Claude Code's rows are each skill's newest skill-only
rows from the shrink series. "Whole runs" draws runs as they were
measured; "each command" draws every command on its own, the model the
earlier 42% estimate was read from, so only that column compares with
it (it gives 1% to 25% on the 2026-11-13 rows):

| Harness | Whole runs | Each command |
| --- | ---: | ---: |
| Claude Code | 0% to 3% | 0% to 7% |
| Codex | 0% to 9% | 0% to 9% |
| OpenCode | 0% to 9% | 0% to 13% |
| All three, at least one fails | 0% to 15% (median 6%) | 0% to 20% (median 10%) |

What is left is command-level, not run-level: optional commands that
run in some runs and not others, and timeouts on the two longest
skills. So the local harnesses stay advisory, and their tables are now
worth reading: a command missing from every after run is a real signal
on them too.
[MODEL-COMPLIANCE.md](https://github.com/prasadtalasila/chitragupta/blob/main/docs/MODEL-COMPLIANCE.md)
lists which steps the local model runs every time, never, or now and
then, and the reasons its transcripts give.
