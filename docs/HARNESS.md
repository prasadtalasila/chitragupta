# 🔌 Harnesses: one citekey gate on Claude Code, Codex and OpenCode

Status: **implemented.**

Continue support is open, in
[issue 901](https://github.com/prasadtalasila/chitragupta/issues/901).
The task-by-task plan for the rest is
[plans/812-harness-neutral-core.md](https://github.com/prasadtalasila/chitragupta/blob/main/plans/812-harness-neutral-core.md).

This document records why the pipeline runs on more than one agent
harness, what the design session of 2026-09-26 to
2026-09-29 decided, and which designs it turned down and why. Several
of the rejected designs look like the obvious fix, and each one fails
the same test: **can the model skip it?**

**Written for** anyone adding a harness, changing a launcher, or
wondering why the OpenCode plugin holds no gate logic. It assumes
[HOOKS.md](HOOKS.md), whose three-layer rule (checks, adapters,
launcher) this extends, and [ARCHITECTURE.md](ARCHITECTURE.md)'s
"Grounding is enforced, not requested".

## 🧭 Table of contents

- [Why more than one harness](#-why-more-than-one-harness)
- [The problem](#-the-problem)
- [The design: three checks over one gate](#-the-design-three-checks-over-one-gate)
- [What each harness enforces](#-what-each-harness-enforces)
- [Skills: one copy per harness](#-skills-one-copy-per-harness)
- [Designs turned down, and why](#-designs-turned-down-and-why)
- [Harness facts learned](#-harness-facts-learned)
- [Decisions a maintainer made](#-decisions-a-maintainer-made)
- [Measured, and what is still not](#-measured-and-what-is-still-not)

## 🎯 Why more than one harness

The Python package has always been harness-neutral: nothing under
`chitragupta/` calls a language model, and retrieval's embedding models
run locally. Everything above it assumed Claude Code. That shuts out
two kinds of user:

- a researcher without a Claude Code subscription, who drafts in Codex
  or OpenCode;
- a researcher who keeps the corpus on their own hardware and runs a
  local model through one of those harnesses.

The second is the harder case, because a small local model is the one
most likely to fabricate a citekey. Supporting another harness is
therefore only worth doing if the one binding rule is exactly as strong
there. A harness where a fabricated key can slip through unnoticed is
not supported.

## ❗ The problem

Without per-harness work, three facts make the gate Claude Code-only:

1. A Claude Code hook alone is not enough.
   `.claude/hooks/citation_gate_hook.py` fires on Claude Code's
   `Write|Edit` matcher and reads `tool_input.file_path`.
2. Codex edits through `apply_patch`, whose payload carries the patch
   text in `tool_input.command` and no `file_path`. A hook that reads
   only `file_path` finds no path there and fails open: a gate that
   looks like it passed.
3. Pandoc alone does not refuse a fabricated key. Measured on
   2026-09-26, before render ran the gate: `--format md` refused a key
   missing from the ledger only as a side effect of building the
   numbered reference list, while `--format docx` printed pandoc's
   citeproc warning and wrote the document anyway, and pdf and tex take
   the same path.

OpenCode reads none of `.claude/settings.json`, so without its plugin it
has no check at all.

## 🧱 The design: three checks over one gate

Every check calls `chitragupta/citation_gate.py`. No gate logic is
copied into a skill, a hook launcher or a plugin.

1. **Self-check (asked).** Before presenting, each skill runs
   `python -m chitragupta.draft gate` on its own draft and fixes what it
   reports. Each harness gets its own copy of the skill, naming its own tools
   (see "Skills:
   one copy per harness" below).
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

- **The hooks live in `.claude/hooks/`.** Codex's `.codex/hooks.json`
  and OpenCode's plugin both launch those same scripts. Moving them to
  a neutral folder would churn about 28 test files and the coverage
  source for no change in behaviour.
- **The hooks read one extra payload shape**: `apply_patch` patch text.
  Codex and OpenCode use the same envelope (OpenAI's V4A grammar), so
  one parser, `.claude/hooks/patch_paths.py`, serves both. Every draft
  a patch adds, updates or moves is gated. A patch that mentions
  `content/drafts/` but whose headers cannot be read is **blocked**:
  the one deliberate exception to "malformed stdin fails open", because
  failing open there is exactly the silently inert gate HOOKS.md exists
  to prevent.
- **The OpenCode plugin is a transport.** It turns OpenCode's tool
  arguments into the payload the hooks already read, pipes it to
  `citation_gate_hook.py` and then `style_check_hook.py`, and hands the
  verdict and any style notes back. Which writes are
  drafts, the size bound, the timeout and the fail-closed rules are the
  Python hook's, shared by all three harnesses.
- **A liveness warning covers the hook that never fires.** The gate
  hook records each draft it checked, and `draft gate` run by hand
  warns about a draft no hook has seen since it last changed. The
  warning only reports; it never changes the gate's exit code.

## 🗂 What each harness enforces

| Harness | Self-check | Mandatory check | Last check |
| --- | --- | --- | --- |
| Claude Code | the skill runs `draft gate` | `PostToolUse` hook on Write and Edit, after the write | `draft render` |
| Codex | the skill runs `draft gate` | `PostToolUse` hook on `apply_patch`, after the write, once the project's hooks are trusted and only if the model server passes `apply_patch` through (llama.cpp does not) | `draft render` |
| OpenCode | the skill runs `draft gate` | plugin on `tool.execute.after`, after the write | `draft render` |

None of them stops a write through the shell, such as
`echo ... >> content/drafts/x.md`. No harness's file-tool hook sees it,
on Claude Code today as on the other two. `draft render` refuses the
draft, and the skill's own `draft gate` run warns that no hook checked
it. A person copying text straight out of the raw draft file is outside
every check, and nothing can see that.

## 📂 Skills: one copy per harness

Each skill's `SKILL.md` exists once per harness, and each copy names
that harness's own tools. A model then reads a complete instruction at
the step where it acts ("use `Edit`, never `Write`" on Claude Code, "patch with
`apply_patch`" on Codex, "`edit`, never `write`" on OpenCode) instead of
a harness-neutral phrase it has to translate.

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
cannot collide with the other copies, and the `skill` permission in
`.opencode/opencode.json`, which filters the list the model is shown,
denies every unsuffixed name. That holds per project, with no
environment variable. The OpenCode copies refer to one another by the
suffixed names; `AGENTS.md` says so in one line.

For `init --agent`, `claude` (the default) writes `.claude/` and the
shared core; `codex` adds `.codex/` and `.agents/`; `opencode`
adds `.opencode/`. `.claude/` is written for every harness because it
holds the hook scripts Codex and OpenCode launch too; Codex never reads
its skills and OpenCode denies them.

The copies are edited by hand, and `tests/test_skill_harness_copies.py`
keeps them from drifting.
`tests/fixtures/skill_harness_phrases.toml` lists every place the
copies are meant to differ, as one entry per phrase with a value per
harness. The test replaces each copy's phrases with the entry's key,
drops OpenCode's suffix, and requires the three results to be
identical. A sentence changed in one copy and not the others fails,
naming the skill, the copy and the first line that moved. The same test
also checks:

- every entry is used in every copy;
- no copy names another harness's tools;
- the OpenCode copies refer to suffixed skill names;
- the deny list names exactly the unsuffixed skills.

`chitragupta doctor` reports an OpenCode project whose deny list is
missing or incomplete. The phrase map is never shown to a model; it
exists only for the test.

To change a skill, change every copy, and add or edit a phrase-map
entry for any wording that is meant to differ. The step scans
(`tests/test_skill_*_step.py`) read only `.claude/skills/`; once the
copies agree, a required step present in one is present in all three.

### Developer-only skills

A skill for working on this repository rather than with the pipeline,
so far `demo-recorder` (which records the feature demo) and
`skill-bench` (which measures a skill change on all three harnesses), carries
one extra frontmatter field:

```yaml
metadata:
  audience: developer
```

It keeps its three copies and its deny rule like any other skill, so
every checkout's harness offers it. No distribution carries it (#1188):
`chitragupta init` and `scripts/release.py` skip any skill folder
`chitragupta/developer_skills.py` finds marked, and `pyproject.toml`
names every other skill folder one by one, because Poetry's `exclude`
cannot take a path back out of an `include`d folder. A new user-facing
skill therefore needs three `include` lines, and
`tests/test_developer_skills.py` fails, naming the files, until it has
them. The step scans and the user-facing skill counts skip developer-only
skills. A developer-only skill keeps its scripts in its own folder, so
the marker takes them out with it. The deny rule does ship, in
`.opencode/opencode.json`: a rule for a name a project lacks has no
effect.

### Only `SKILL.md` is per harness

Everything else a skill uses exists once, under `.claude/`:
`.claude/skills/<name>/references/` for one skill's detail,
`.claude/skills/<name>/assets/` for a template it copies from (so far
only book-assembler's `book-skeleton.tex`), and
`.claude/skills-common/references/` for a passage several skills share.
All three copies of `SKILL.md` name those files by their path from the
project root, so the files sit outside the Codex and OpenCode skill
folders. That works because:

- **every harness loads them on demand.** Each one preloads only a
  skill's name and description, loads the `SKILL.md` body when the skill
  is used, and leaves every other file for the model to open by path.
  None inlines a `references/` folder. Sources: the Claude Code skills
  docs; Codex's skill catalog prompt (`openai/codex`,
  `ext/skills/src/catalog_prompt.rs`), which tells the model to read
  only the references it needs; OpenCode's `skill` tool
  (`sst/opencode`, `packages/opencode/src/tool/skill.ts`), which lists
  a skill's other files by path without their contents.
- **nothing confines a model to its skill's own folder.** It reads with
  its ordinary file tools. Codex resolves a relative path against the
  skill's folder first, which is why the paths are written from the
  project root and say so.
- **`.claude/` is scaffolded for every `--agent`**, so the files are
  there whichever harness a project uses.

The price is one rule: **a shared file names no skill and no harness
tool.** OpenCode must be sent to `<name>-opencode`, and a reference that
named the unsuffixed skill would send it to one its config denies, so a
sentence that routes to another skill stays in `SKILL.md`, where the
phrase map and the suffix rule apply. `tests/test_skill_references.py`
holds both halves: every path a `SKILL.md` names exists, every reference
is named by some `SKILL.md`, no shared file names a skill or a tool, and
the Codex and OpenCode folders hold `SKILL.md` and nothing else.

**Measured on 2026-10-06/07** with `bench/bench_skill_harnesses.py`,
against freshly scaffolded projects. Claude Code ran
`claude -p --model sonnet`; Codex 0.159.3 and OpenCode 1.18.34 ran
Qwen3.6-35B-A3B on a local llama-server. Tier 1 asks each harness to load
a skill and print the first line of every `.claude/` file it names; a
read counts only when that line matches the file. Each Tier 1 run was
capped at 900 seconds (`--timeout 900`, the script's default), except
the first Codex batch (1800) and OpenCode's four genre writers (1200);
each Tier 2 task was capped at 3300.

| Harness | Loaded its own copy | `.claude/` reads that failed | Every named file read |
| --- | ---: | ---: | ---: |
| Claude Code | 10 of 10 | 0 | 10 of 10 |
| Codex | 10 of 10 | 0 | 7 of 10 |
| OpenCode | 10 of 10 | 0 | 7 of 10 |

Every shortfall was the local model listing fewer paths than the skill
names (or, on OpenCode, two runs passing the 15-minute cap), never a
path that failed to resolve or a read that was refused. Codex opened
`.agents/skills/<name>/SKILL.md` and then each `.claude/` path from the
project root; OpenCode reported its `-opencode` copy's base directory and
read the same way.

**A pointer alone is not enough for a step that must run.** Tier 2 runs a
real survey. With the critique step reduced to "read `critique.md` and
follow it", a Claude Code run skipped the step outright: no baseline, no
recheck, no `revisions.md` entry. With the loop's commands inline and the
step saying it is not done until they have run, two re-runs both worked
the loop, so each genre's step keeps them inline.
`tests/test_skill_pregate_feedback_step.py` fails if the step's own text
loses them. Move rationale and detail into a reference; keep the
commands a step requires in `SKILL.md`.

**The render step is the one measured exception**, measured on
2026-10-30 to 11-02. survey-writer's steps 12 and 13 (`draft references`, `draft
render`, `draft evidence`) were cut to a pointer at
`.claude/skills-common/references/render-and-references.md`, with no
command left in `SKILL.md`, and the Tier 2 survey was run with its
"then render" clause removed, so only the skill could make a model run
them. Claude Code ran `claude -p --model sonnet`; Codex 0.159.3 and
OpenCode 1.18.34 ran the same Qwen3.6-35B-A3B `UD-Q4_K_M` on
llama-server b11321 (CPU, one slot, 131,072-token context). Each run was
capped at 3600 seconds on Claude Code and 14,400 on the local harnesses.

| Harness | Runs per arm | Commands inline | Pointer only |
| --- | ---: | --- | --- |
| Claude Code | 3 | all three steps, 3 of 3 | reference opened and all three steps run, 3 of 3 |
| Codex | 1 | `draft references` skipped; md rendered, no tex or pdf | reference opened; references, tex, pdf, md and the sidecar |
| OpenCode | 1 | all three steps | reference opened; all three steps |

Every final draft passed the gate. No pointer-only step was skipped;
the one partial skip was a run with the commands inline. That is one
step on small samples, so it licenses moving this step, which is what
the four genre writers and deep-research now do, and nothing more. The
critique loop keeps its commands inline until it is measured the same
way. `bench/bench_skill_harnesses.py --tier 2 --skill-only` re-runs the
pointer arm, since it scaffolds the tree it runs from; run with this
script against a tree from before the size budget, it gives the inline
arm.

Two harness facts the bench had to work around, both recorded in the
script: OpenCode takes its project directory from the inherited `PWD`,
not the process's working directory, so a run launched from elsewhere
loads that directory's skills; and a timed-out Codex run left its model
request holding the local server's one slot until its process group was
killed.

## 🚫 Designs turned down, and why

**An MCP server with gated `draft_write` / `draft_edit` tools, as the
enforcement.** The tools would run
the gate before writing, so a bad key would never reach disk through
them. But a pre-write gate enforces only if the model has no other way
to write, and on every harness it has one: its built-in edit tool, or
failing that the shell. On Codex, Claude Code and OpenCode the hook or
plugin already covers the built-in tools, so the server would be a
second write path to maintain and secure for no added guarantee. It
belongs to #901, where Continue has no hooks at all and the server,
with Continue's built-in write tools excluded, *is* the enforcement.
Its planned security choices are recorded there: it writes only
`content/drafts/`, reads only `content/`, opens the ledger read-only
with no sync tool, speaks stdio only, and is launched through the
installed `chitragupta mcp` command so a planted `chitragupta/` cannot
be imported in its place.

**The gate in a script each skill runs, instead of a hook.** The
Agent Skills layout lets a skill carry `scripts/`, and every harness
here reads that layout. But the model decides whether to run a skill's
script. That is the "asked, not enforced" posture ARCHITECTURE.md rules
out, and the model likeliest to skip the step is also the likeliest to
fabricate. It is kept as the self-check, never as the only check. No
`scripts/` folder either: the self-check is already one CLI call, and a
script in each of eleven skills would be eleven copies of it.

**A pre-write check inside the OpenCode plugin.** `tool.execute.before`
could refuse a bad write before it lands. But to gate the text an
`edit` *would* produce, the plugin would have to reproduce OpenCode's
own `oldString` matching, which is fuzzy. That is a second
implementation of someone else's edit semantics that can drift, inside
the one component that must not. The plugin checks the file on disk
after the write, as Claude Code's and Codex's hooks do.

**Rely on render alone.** Render is harness-independent and adds no
attack surface, so it is tempting to call it enough. But it catches a
fabricated key only at the end. The guarantee Claude Code users already
had is that the model fixes a bad key *in the draft, before moving on*,
and render alone would lose that on Codex and OpenCode.

**A file watcher that quarantines bad drafts.** It acts after the
write, races a person editing the same file, is invisible to the
model, and needs platform-specific file-change APIs or polling.

**A "closest match" suggestion in a refusal.** Offering the nearest
ledger key invites the model to swap in a real key for a paper it
never read. That passes the gate, so it is worse than a fabricated key.
Every refusal names the bad key and its line, and nothing else.

**A git pre-commit hook.** `content/drafts/` is gitignored, so a draft
is never committed.

**Hand-kept copies of each skill with no check between them.** Eleven skills of
1,800-6,300 words each, copied three ways, would drift, and a
copy that drifts on the gate step is a fabrication path. The copies exist, but
only because the phrase-map test fails on any drift outside the entries meant
to differ.

**One harness-neutral wording, with a tool glossary in `AGENTS.md`.**
Tried and replaced. "Edit the passage in place" gives up Claude
Code's exact tool names and gives Codex and OpenCode nothing specific,
and a glossary in `AGENTS.md` asks the model to connect a phrase to a
table in another file that Claude Code does not even load (it loads
`CLAUDE.md`, which only points there).

**Generating the copies from one templated source.** It gives the same
protection as the phrase-map test, at the cost of a build step and a
source nobody reads. The copies are plain files instead, each editable
where it is read.

**Relying on OpenCode's folder order, or `OPENCODE_DISABLE_EXTERNAL_SKILLS`.**
There is no folder order: OpenCode picks among same-named copies at
random. The environment variable restricts it to `.opencode/skills/`,
but a project cannot set it, and a user who forgets it gets a random
mix. The suffix and the deny list are per project.

## 📚 Harness facts learned

Gathered from documentation and write-ups on 2026-09-26 to 2026-09-29.
Each one the code depends on is re-checked on a real session before it
is relied on (the plan's Task 0).

- **Codex hooks** load from `<repo>/.codex/hooks.json` and fire on
  `PostToolUse` for `apply_patch`, with `tool_name: "apply_patch"` and
  the patch in `tool_input.command`. The `{"decision": "block"}` output
  shape matches Claude Code's.
  ([Codex hooks](https://developers.openai.com/codex/hooks))
- **Codex skips project hooks until they are trusted.** The project's
  `.codex/` layer must be trusted, and each command hook is trusted
  against its current hash, so a changed hook is skipped until trusted
  again. An untrusted gate is indistinguishable from one that passed,
  which is why the liveness warning exists.
- **Codex reads skills from `.agents/skills/`.**
  ([Codex skills](https://developers.openai.com/codex/skills))
- **OpenCode reads skills from `.opencode/skills/`, and also from
  `.claude/skills/` and `.agents/skills/` for compatibility**
  ([OpenCode skills](https://opencode.ai/docs/it/skills/)). How it
  handles one name in several folders is measured below.
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
  Four skills' descriptions were over the limit. Every skill carries a
  `tags:` key outside that list, which all three harnesses load anyway
  (measured).
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

Measured on 2026-09-29, with Codex 0.159.0 and OpenCode 1.18.33
installed in a scratch copy of a project scaffolded by
`chitragupta init`. No real model was used: a small local stand-in
answered each harness's model requests with scripted tool calls, so each
harness ran its own real tools, hooks and plugins, and the stand-in
logged exactly what the harness handed back to the model after each tool
call.

**Codex**, driven end to end:

- The gate hook fires on `apply_patch`, and the model receives the
  gate's refusal in place of the tool's output, naming the bad key and
  its line. The session-start preflight arrives as a developer message.
- The payload carries `tool_name: "apply_patch"`, the patch text as a
  plain string in `tool_input.command`, and the session's `cwd`. Patch
  paths are relative to that `cwd`.
  A single patch that adds two drafts is gated as one call and the
  refusal names the bad one. Both payloads are recorded in
  `tests/fixtures/harness_payloads/`.
- **Project hooks do not run until trusted.** In an untrusted project a
  draft with a fabricated key landed with "Success" and no warning. The
  hand-run gate then printed the liveness warning, and after a trusted
  run it printed none.
- **A hook runs in the session's working directory**, which is wherever
  Codex was started, and Codex sets no project-directory variable. A
  relative launcher such as `python .claude/hooks/<x>.py` therefore fails to
  start from
  any subfolder, and the draft lands ungated. Each launcher line walks up
  to the folder holding `.codex/hooks.json` and runs the hook from there,
  under `python -P`; blocking from `content/` is measured.
- **Codex reads project skills only from `.agents/skills/`**, never
  `.claude/skills/`, which is where its own copy lives. It reads
  `AGENTS.md` natively.
- A skill with a `tags:` key loads. A `description` over 1,024
  characters loads but is cut at 1,024 in what the model sees, so the
  end of an over-long description (often its "use X instead" routing)
  would be lost.

**OpenCode**, driven end to end the same way:

- **The plugin blocks all three file tools.** A `write` and an `edit`
  that put a fabricated key in a draft, and an `apply_patch` (the tool
  OpenCode offers a GPT model in place of `write` and `edit`) adding two
  drafts, were each refused: the model is handed the gate's report as
  the tool's result, naming the bad draft and key. A clean `write`
  passes silently, and the hook's run leaves the liveness record, so a
  hand-run gate afterwards is quiet.
- `tool.execute.before` sees `{filePath, content}` for `write`,
  `{filePath, oldString, newString}` for `edit` and `{patchText}` for
  `apply_patch`, and `tool.execute.after` receives the same `args` on
  its input, so the plugin needs only the after-hook.
- **Skill discovery.** It reads `.opencode/skills/`, `.claude/skills/`
  and `.agents/skills/` (and the user's global `~/.claude/skills/`),
  and loads one copy per skill name, chosen arbitrarily when a name is
  in more than one folder: four runs picked different mixes, and
  `.opencode/skills/` does not take precedence. Its source shows why:
  skills land in one map keyed by name, loaded concurrently. The list
  the model is shown is filtered by the `skill` permission, per name, so
  OpenCode-only names plus a project-level deny list for the others give
  it exactly its own copy (measured in 3 of 3 runs). The environment
  variable `OPENCODE_DISABLE_EXTERNAL_SKILLS=1` restricts it to
  `.opencode/skills/` too, but a project cannot set it.
- A skill with `tags:` loads, and a long description is kept whole.
- **The per-harness layout, end to end** (2026-09-30, a project
  scaffolded from the built wheel with `--agent claude --agent codex
  --agent opencode`, when the project had nine skills): Codex listed
  them all from `.agents/skills/`; OpenCode, in two runs, listed only
  the `-opencode` skills, handed
  the model the OpenCode wording when it loaded `survey-writer-opencode`,
  and refused `survey-writer` under the deny list.
- **One environment trap, not OpenCode's or this repository's.** In the
  container these were measured in, OpenCode's runtime never reaped a
  `git` child process (it sat `<defunct>`), and the agent loop waited on
  it forever: the title request went out and the turn itself never did.
  With `git` off `PATH` everything ran. A harness that stalls before its
  first real model call in a sandbox is worth checking for a zombie
  child before anything else.

**Still not measured:**

- whether a Codex `PostToolUse` advisory note (the style hook's) reaches
  the model (the probe draft had no prose finding to report);
- Codex's gate hook on a local model. In the recorded run, llama.cpp
  dropped Codex's `apply_patch` tool, so the model wrote through the
  shell and the hook never fired; OpenCode's plugin did fire and
  refused a write. Both runs are in [LOCAL-MODELS.md](LOCAL-MODELS.md),
  tracked in [#904](https://github.com/prasadtalasila/chitragupta/issues/904).

### Measuring a skill change: commands run, and the pass rule

A shrink can leave a step's command in a skill and still make a model
stop running it, and no unit test sees that. `skill-bench` measures it
(plans/1091-skill-shrink.md, PR 0). Each Tier 2 run of
`bench/bench_skill_harnesses.py` records, for its (harness, skill):

- `expected`: every `chitragupta` command the harness's own copy of
  `SKILL.md` names, and every command in the references it names, since
  a step cut to a pointer keeps its commands in the reference. A command
  is `module sub [sub]` (`draft dossier init`), with the subcommands
  taken from the module's own `--help`, so a slug after `draft render`
  is an argument and never a third word.
- `ran` and `missed`: which of those a tool call executed. A command
  counts only where a shell would run it: as the first word of a simple
  command, inside the `zsh -lc '...'` that Codex wraps every call in, or
  behind `cd x &&`, `VAR=1`, `timeout 600` or a keyword such as `then`.
  A `grep` for the command, an `echo` naming it, a line inside a heredoc
  body and a `--help` call are not runs.
- `forbidden_ran`: `corpus sync` or `enrich`, which the skills name only
  as what the user runs.
- `gate`: `draft gate` on the task's own draft, 2 when it was never
  written; and `prerequisite_gate`, the same for the survey a reviser
  task starts from.

`--compare BEFORE AFTER` reads two such files and judges each (harness,
skill) that both arms ran, on every command either arm expected, counted
from everything each run executed. It leaves out a run that timed out,
raised, or started from a prerequisite that never passed its gate: that
run measured the clock or the fixture, not the skill. Every row -- each
command, the gate, each forbidden command -- is judged by one rule:

| Usable runs per arm | Fail (exit 1) | Inconclusive (exit 3) | Pass (exit 0) |
| --- | --- | --- | --- |
| fewer than 3 | -- | always | -- |
| 3 against 3 | the row went all the way the wrong way: a command or the gate in every before run and no after run, or a forbidden command in no before run and every after run | any other move the wrong way | no move the wrong way |
| 6 against 6 | an all-the-way move, or a move of 4 runs or more | -- | anything else |

On exit 3, run 3 more on both arms and compare the merged files.

**Why 3 runs screen and do not convict.** A skill names 15 to 19
commands counting its references (5 for figure-drawer), so a comparison
judges about 54 rows across the three harnesses. Take a row a model
runs on 80% of runs, unchanged between the arms. A two-run drop then
happens for 1 row in 18, so a rule that failed a two-run drop at 3 runs
would fail an unchanged skill 96% of the time. The rule above fails a
row at 3 runs only on all-to-none (0.4% a row) and at 6 runs on a drop
of 4 (0.5% a row). Simulated end to end with `judge()` itself, if every
row ran at 80% an unchanged skill would still fail 34% of the time, at
90% 7%, and at 95% under 1%. Real rows are mostly near 0 or 1: a
command a skill always runs, or one only a branch reaches. The baseline
below measures what that makes the false-fail rate. It still finds a
real regression: a step dropped outright fails at 3 runs, and a command
that fell from 90% to 30% fails at 6 runs more than half the time.
Results are comparable within one host and model build only.

**Measured on 2026-11-13** on six NVIDIA A40s (driver 595.58, CUDA
13.2): llama.cpp `b11321` built with `-DGGML_CUDA=ON` and
`CMAKE_CUDA_ARCHITECTURES=86`, one `llama-server` per GPU with
`-c 131072 -np 1 -ngl 99 --jinja`, serving the same Qwen3.6-35B-A3B
`UD-Q4_K_M` file as #1068. A Tier 2 survey took 3 to 4 minutes on
Codex and OpenCode, against 2 to 3.5 hours on the CPU host. On that
day's single survey run per harness, Codex wrote the dossier by hand
instead of running `draft dossier init`, and OpenCode skipped
`draft evidence`; Claude Code ran 14 of the 19 commands the skill and
its references name, and the five it did not are branch-only
(`draft dossier outline`) or named as optional.
