# 🤖 LLMs and coding agents

Status: **how-to.**

**Written for** anyone choosing which coding agent, and which model, to
draft with. chitragupta itself calls no language model: the agent reads a
skill, drives the model, and runs the pipeline's commands. The citekey
rule ([SOUL.md](../SOUL.md)) is the same on every agent; agents differ in
how early they catch a broken key.

## 🛡 The three checks

Every agent gets the same three checks, all of them calls to one gate in
`chitragupta/citation_gate.py` ([HARNESS.md](HARNESS.md) has the design):

1. **Self-check.** Each skill tells the model to run `chitragupta draft
   gate` on its draft and fix what it reports. The model can skip it.
2. **Mandatory check.** On Claude Code, Codex and OpenCode, a hook or
   plugin runs the gate after every write the agent makes to a draft
   through its own file tools, and hands a refusal back to the model as
   the tool's result. A write through the shell bypasses it on every
   agent, and so does an agent that never fires it (see Codex behind
   llama.cpp, and Continue, below).
3. **Last check.** `chitragupta draft render` runs the gate before it
   writes any format, so a draft with an unknown key never becomes a
   document, whatever the agent.

## 🧰 Setting up a project for each agent

Install the package, usually from PyPI (`pip install chitragupta-cli`);
[PACKAGING.md](PACKAGING.md) compares it with the release zip and a git
checkout. Then scaffold a project with `chitragupta init`. Its `--agent`
option chooses which agent's files to write, and can be repeated:

| Agent | Command | What it adds |
| --- | --- | --- |
| Claude Code | `chitragupta init my-project` | `.claude/`: the skills with their reference files, the hook scripts and `settings.json`, which wires the hooks to `Write` and `Edit`. This is the default |
| Codex | `chitragupta init --agent codex my-project` | `.codex/hooks.json`, which runs the same hook scripts on `apply_patch`, and Codex's copy of each skill's `SKILL.md` in `.agents/skills/` |
| OpenCode | `chitragupta init --agent opencode my-project` | `.opencode/`: a plugin that runs the gate after `write`, `edit` and `apply_patch`, OpenCode's copy of each skill's `SKILL.md`, and `opencode.json` |
| Several | `chitragupta init --agent claude --agent codex --agent opencode my-project` | all of the above in one project |
| Continue | none yet | see below |

`.claude/` is written for every agent and must be kept: it holds the hook
scripts and the only copy of each skill's reference files, which the
Codex and OpenCode `SKILL.md` copies read by path. After scaffolding,
put your `.bib` export and PDFs in `papers/`, run `chitragupta corpus
sync`, and run `chitragupta doctor`. Doctor reports a hook launcher that
cannot start, and an OpenCode project whose skill deny list is
incomplete.

### Claude Code

Start `claude` in the project and ask for a skill by name, for example
"use survey-writer to draft a survey on ...". The hooks fire on every
`Write` and `Edit` with nothing further to set up.
[AGENTS.md](https://github.com/prasadtalasila/chitragupta/blob/main/AGENTS.md)
is the drafting contract; Claude Code reaches it through `CLAUDE.md`.

### Codex

Start `codex` in the project. The skills are the same eleven, read from
`.agents/skills/`, and Codex reads `AGENTS.md` itself.

You have to trust the project's hooks, or the mandatory check does not
run. On the first start Codex shows "Hooks need review": choose "Trust
all and continue". `/hooks` lists them later. Trust is recorded against
each hook's hash, so a hook that changes, for example after you upgrade
chitragupta, needs trusting again. An untrusted hook fails silently; the
only sign is the warning `chitragupta draft gate` prints when no hook has
checked a draft since it last changed.

Codex's sandbox needs unprivileged user namespaces; without them every
sandboxed command fails with `bwrap: No permissions to create new
namespace`. Behind llama.cpp's server the mandatory check never fires:
Codex sends `apply_patch` as a Responses tool of type `custom`, which
llama.cpp skips, so the model writes through the shell, which no hook
sees. Other local servers have not been measured.
[LOCAL-MODELS.md](LOCAL-MODELS.md) has the details and
[`examples/codex/`](examples/codex/README.md) a full run.

### OpenCode

Start `opencode` in the project. OpenCode's skills carry an `-opencode`
suffix (`survey-writer-opencode` and so on), because OpenCode also reads
`.claude/skills/` and `.agents/skills/` and would otherwise pick among
same-named copies at random. `.opencode/opencode.json` hides the
unsuffixed names, so keep that file when you add your own settings.

The plugin needs no trust step. For a local model, add an
`@ai-sdk/openai-compatible` provider, as
[`examples/opencode/`](examples/opencode/README.md) does. In some
containers OpenCode stalls before its first model call;
[HARNESS.md](HARNESS.md) has the workaround.

### Continue

`chitragupta init` has no Continue option yet. Continue's CLI reads
`.claude/skills/` and `AGENTS.md`, so a default project gives it the
skills. It has no mandatory check: Continue CLI 1.5.47 loads the hooks in
`.claude/settings.json` and never runs them on a tool call, so only the
self-check and render apply. The gated write tools that would close that
gap are planned in
[issue 901](https://github.com/prasadtalasila/chitragupta/issues/901).

## 📊 What was observed

| Agent and model | Self-check | Mandatory check | Last check | Evidence |
| --- | --- | --- | --- | --- |
| Claude Code, Anthropic models | asked | **enforced** on `Write` and `Edit` | enforced | the reference setup: [HOOKS.md](HOOKS.md) |
| Codex, OpenAI models | asked | **enforced** on `apply_patch`, once the hooks are trusted | enforced | a scripted stand-in model: [HARNESS.md](HARNESS.md) |
| Codex, Qwen3.6-35B-A3B on llama.cpp | ran and passed, warned that no hook had checked the draft | **never fired** | enforced | one survey: [LOCAL-MODELS.md](LOCAL-MODELS.md), [`examples/codex/`](examples/codex/README.md) |
| OpenCode, Qwen3.6-35B-A3B on llama.cpp | ran and passed | **enforced**, and refused one write | enforced | one survey: [LOCAL-MODELS.md](LOCAL-MODELS.md), [`examples/opencode/`](examples/opencode/README.md) |
| Continue CLI 1.5.47, Qwen3.6-35B-A3B on llama.cpp | asked | **never fires** | enforced | one write probe: [LOCAL-MODELS.md](LOCAL-MODELS.md) |

"Asked" means the skill tells the model to run the check and nothing
makes it. "Enforced" means the model cannot get past the check. Each
local-model row is a single run on one model over five sample papers.

The last check holds on every agent, and in both recorded local-model
surveys the final draft cited only keys in the ledger. The agents differ
in when a bad key is caught. With the mandatory check, the model hears
about it at the write that put it there: on OpenCode the model wrote a
placeholder `[@citekey]`, the plugin refused the write and named the
line, and the model fixed that line without swapping in a real key.
Without it, the model hears only if it runs the gate itself, or at
render.

The warning that a hook did not fire is easy to miss. On Codex the model
read past it both times it ran the gate. It also fires after `chitragupta
draft references` rewrites a draft the hook already checked, so it can
appear on a draft that was gated correctly.

How closely a model follows a skill varies from run to run: one Codex
run wrote the dossier files itself instead of running `dossier init`, and
both OpenCode runs played down the verbatim scan's findings. None of
these lapses touched a citekey, and the dossier shows all of them.

A local model needs a large context window: the largest prompts were
about 30,000 tokens on Codex and 44,000 on OpenCode, in a 131,072-token
window, so a 32k window overflows within the first few retrievals.

## 🧭 Choosing an agent and a model

For the strongest guarantee, use an agent whose mandatory check fires
with your model: Claude Code, Codex with an OpenAI model and trusted
hooks, or OpenCode. For a local model, OpenCode is the agent with a
recorded run in which the mandatory check fired; give the model at least
a 64k window.

With Codex behind llama.cpp, or Continue, run `chitragupta draft gate`
yourself before trusting a draft, and take its "no automatic gate has
checked" warning seriously.

Whatever the agent, read the dossier. It records what the model searched
for and what it kept, which is where a model that skipped steps shows
it.

## 📚 Where to read more

- [LOCAL-MODELS.md](LOCAL-MODELS.md): the local-model runs in detail,
  and what Continue does with hooks, tools, skills and `AGENTS.md`.
- [HARNESS.md](HARNESS.md): why the checks are built the way they are,
  and the designs turned down.
- [HOOKS.md](HOOKS.md): the hook scripts every agent runs.
