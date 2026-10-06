# 🤖 LLMs and coding agents

Status: **current for 6.128.** Written 2026-10-02.

**Written for** anyone choosing which coding agent, and which model, to
draft with. chitragupta itself calls no language model: nothing under
`chitragupta/` sends a prompt anywhere. A coding agent (Claude Code,
Codex or OpenCode) reads a skill, drives the model, and runs the
pipeline's commands. This page says how to set a project up for each
agent, and what happened when each one drafted a survey.

The one rule is the same everywhere: a citekey may be used only if it is
in your own `.bib` export and the ledger picked it up from a real PDF
([SOUL.md](../SOUL.md)). Agents differ in how early they catch a broken
key.

## 🧭 Table of contents

- [The three checks](#-the-three-checks)
- [Setting up a project for each agent](#-setting-up-a-project-for-each-agent)
- [What was observed](#-what-was-observed)
- [Choosing an agent and a model](#-choosing-an-agent-and-a-model)
- [Where to read more](#-where-to-read-more)

## 🛡 The three checks

Every agent gets the same three checks, all of them calls to one gate in
`chitragupta/citation_gate.py` ([HARNESS.md](HARNESS.md) has the design):

1. **Self-check.** Each skill tells the model to run `chitragupta draft
   gate` on its draft and fix what it reports. The model can skip it.
2. **Mandatory check.** On Claude Code, Codex and OpenCode, a hook or
   plugin runs the gate after every write the agent makes to a draft
   through its own file tools, and hands a refusal back to the model as
   the tool's result. The model cannot skip it on those tools. A write
   through the shell bypasses it on every agent, and so does an agent
   that never fires it (see Codex behind llama.cpp, and Continue, below).
3. **Last check.** `chitragupta draft render` runs the gate before it
   writes any format, so a draft with an unknown key never becomes a
   document. It does not depend on the agent at all.

## 🧰 Setting up a project for each agent

Install the package first. The usual way is from PyPI:

```bash
pip install chitragupta-cli
```

PyPI carries each minor release. The release zip and a git checkout are
the other two ways in; [PACKAGING.md](PACKAGING.md) compares them.

Then scaffold a project with `chitragupta init`. Its `--agent` option
chooses which agent's files to write, and can be repeated:

| Agent | Command | What it adds |
| --- | --- | --- |
| Claude Code | `chitragupta init my-project` | `.claude/`: the skills, the hook scripts and `settings.json`, which wires the hooks to `Write` and `Edit`. This is the default |
| Codex | `chitragupta init --agent codex my-project` | `.codex/hooks.json`, which runs the same hook scripts on `apply_patch`, and Codex's copy of the skills in `.agents/skills/` |
| OpenCode | `chitragupta init --agent opencode my-project` | `.opencode/`: a plugin that runs the gate after `write`, `edit` and `apply_patch`, OpenCode's copy of the skills, and `opencode.json` |
| Several | `chitragupta init --agent claude --agent codex --agent opencode my-project` | all of the above in one project |
| Continue | none yet | see below |

Every project also gets `config.toml`, `papers/`, `content/`, `assets/`,
`AGENTS.md`, `SOUL.md` and the documentation. `.claude/` is written for
every agent, because it holds the hook scripts Codex and OpenCode run
too. After scaffolding, put your `.bib` export and PDFs in `papers/`, run
`chitragupta corpus sync`, and run `chitragupta doctor`. Doctor reports
a hook launcher that cannot start, and an OpenCode project whose skill
deny list is incomplete.

### Claude Code

Start `claude` in the project and ask for a skill by name, for example
"use survey-writer to draft a survey on ...". The hooks in
`.claude/settings.json` fire on every `Write` and `Edit` with nothing
further to set up. [AGENTS.md](../AGENTS.md) is the drafting contract;
Claude Code reaches it through `CLAUDE.md`.

### Codex

Start `codex` in the project. The skills are the same ten, read from
`.agents/skills/`, and Codex reads `AGENTS.md` itself.

You have to trust the project's hooks, or the mandatory check does not
run. Codex skips project hooks until you trust them, and it records the
trust against each hook's current hash. On the first start it shows
"Hooks need review": choose "Trust all and continue". `/hooks` lists
them later. A hook that changes, for example after you upgrade
chitragupta, needs trusting again. An untrusted hook fails silently, and
the only sign is the warning `chitragupta draft gate` prints when no
hook has checked a draft since it last changed.

Two things matter when Codex runs a local model:

- Codex's sandbox needs unprivileged user namespaces. On a host or
  container without them, every sandboxed command fails with `bwrap: No
  permissions to create new namespace`, and the pipeline's commands
  cannot run. The recorded run used
  `--dangerously-bypass-approvals-and-sandbox` in a scratch directory,
  with `--dangerously-bypass-hook-trust`, so it never showed the trust
  prompt.
- Behind llama.cpp's server, the mandatory check never fires. Codex
  sends `apply_patch` as a Responses tool of type `custom`, which
  llama.cpp skips. The model then writes files through the shell, which
  no hook sees. Self-check and render still hold. Other local servers
  have not been measured.

[`examples/codex/`](examples/codex/README.md) has a full run, with the
script that drives it.

### OpenCode

Start `opencode` in the project. OpenCode's skills carry an `-opencode`
suffix (`survey-writer-opencode`, `draft-reviser-opencode` and so on),
because OpenCode also reads `.claude/skills/` and `.agents/skills/` and
would otherwise pick among same-named copies at random.
`.opencode/opencode.json` hides the unsuffixed names. Keep that file
when you add your own OpenCode settings.

The plugin needs no trust step. For a local model, add an
`@ai-sdk/openai-compatible` provider; the example passes one through
`OPENCODE_CONFIG` so the project's own `opencode.json` stays as `init`
wrote it. In some containers OpenCode never reaps a `git` child and
stalls before its first model call; [HARNESS.md](HARNESS.md) has the
workaround.

[`examples/opencode/`](examples/opencode/README.md) has a full run, with
the script that drives it.

### Continue

`chitragupta init` has no Continue option yet. Continue's CLI reads
`.claude/skills/` and `AGENTS.md`, so a project made with the default
`chitragupta init` gives it the skills. It has no mandatory check,
though: Continue CLI 1.5.47 loads the hooks in `.claude/settings.json`
and never runs them on a tool call. Only the self-check and render
apply. The gated write tools that would close that gap are planned in
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
makes it. "Enforced" means the model cannot get past the check. The
Claude Code and Codex-with-OpenAI rows come from earlier measurements;
the three local-model rows come from the runs this page summarises.

The last check holds on every agent. Render runs the gate whatever wrote
the draft, so in no setup can an unknown key reach a rendered document.
In both recorded local-model surveys, the final draft cited only keys in
the ledger.

The agents differ in when a bad key is caught. With the mandatory check,
the model hears about the key at the write that put it there and fixes
it before moving on. That happened on OpenCode: the model wrote a
placeholder `[@citekey]`, the plugin refused the write and named the
line, and the model fixed that line without swapping in a real key. On
Codex behind llama.cpp and on Continue, which have no mandatory check,
the model hears about a bad key only if it runs the gate itself, or at
render once the draft is finished.

The warning that a hook did not fire is easy to miss. On Codex each of
the model's two gate runs printed it, and the model read past it both
times. It also fires after `chitragupta draft references` rewrites a
draft the hook already checked, so it can appear on a draft that was
gated correctly.

How closely a model follows a skill varies from run to run. Two Codex
runs of the same prompt took different paths: one ran `dossier init`
and logged its searches, while the other skipped both and wrote the
dossier files itself. Both OpenCode runs played down the verbatim scan's
findings in their summaries. None of these lapses touched a citekey, and
a person reviewing the dossier would see all of them.

A local model needs a large context window. The largest prompts were
about 30,000 tokens on Codex and 44,000 on OpenCode, in a 131,072-token
window. Most of each prompt is the agent's own system prompt, `AGENTS.md`
and the skill, so a 32k window overflows within the first few
retrievals.

Each local-model row records a single run on one model over five sample
papers, so read it as one observation.

## 🧭 Choosing an agent and a model

For the strongest guarantee, use an agent whose mandatory check fires
with your model: Claude Code, Codex with an OpenAI model and trusted
hooks, or OpenCode. For a local model, OpenCode is the agent with a
recorded run in which the mandatory check fired; give the model at least
a 64k window.

If you use Codex behind llama.cpp, or Continue, run `chitragupta draft
gate` yourself before trusting a draft, and take its "no automatic gate
has checked" warning seriously. Render will still refuse an unknown key.

Whatever the agent, read the dossier. It records what the model searched
for and what it kept, which is where a model that skipped steps shows
it.

## 📚 Where to read more

- [LOCAL-MODELS.md](LOCAL-MODELS.md): the local-model runs in detail,
  and what Continue does with hooks, tools, skills and `AGENTS.md`.
- [`examples/codex/`](examples/codex/README.md) and
  [`examples/opencode/`](examples/opencode/README.md): each run committed
  whole, with the script to repeat it.
- [HARNESS.md](HARNESS.md): why the checks are built the way they are,
  and the designs turned down.
- [HOOKS.md](HOOKS.md): the hook scripts every agent runs.
- [PACKAGING.md](PACKAGING.md): the ways to install, and the command
  surface.
- [AGENTS.md](../AGENTS.md): the drafting contract every agent reads.
