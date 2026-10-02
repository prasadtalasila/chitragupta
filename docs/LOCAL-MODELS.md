# 🖥 Local models: recorded runs on Codex, OpenCode and Continue

Status: **one run recorded, two blocked.** Written 2026-10-02 for
[issue 904](https://github.com/prasadtalasila/chitragupta/issues/904),
with the Continue facts
[issue 901](https://github.com/prasadtalasila/chitragupta/issues/901)
asked to confirm before building.

[HARNESS.md](HARNESS.md) measured the plumbing with a scripted stand-in
model. This file records what a real local model did with it. Each
record states the setup, where each of the three checks fired, and
whether the skill fitted in context. It makes no general quality claim:
one run on one model over the five-paper sample corpus says what
happened, not what usually happens.

## 🧭 Table of contents

- [The setup every run shared](#-the-setup-every-run-shared)
- [OpenCode: one survey, end to end](#-opencode-one-survey-end-to-end)
- [Codex: blocked by the sandbox in this container](#-codex-blocked-by-the-sandbox-in-this-container)
- [Continue: what a real session showed](#-continue-what-a-real-session-showed)
- [Still to record](#-still-to-record)

## 🧪 The setup every run shared

| Item | Value |
| --- | --- |
| Date | 2026-10-02 |
| Model | Qwen3.6-35B-A3B, Unsloth `UD-Q4_K_M` GGUF |
| Server | llama.cpp `llama-server` b11321, CPU, one slot |
| Context | 131,072 tokens |
| Speed | about 88 tokens/s prompt, 14 tokens/s output |
| chitragupta | 6.128.5, installed from the checkout into a clean venv |

Each project was scaffolded with `chitragupta init --agent <harness>`,
given `docs/examples/sample-project/`'s `papers/` and `config.toml`,
and synced with a real `python -m chitragupta.corpus sync`: five PDFs
parsed. A logging proxy between the harness and the server recorded
every request, so the tool lists and context sizes below are measured,
not inferred.

## ✅ OpenCode: one survey, end to end

**OpenCode 1.18.34.** The provider was `@ai-sdk/openai-compatible`
pointing at the server, passed through `OPENCODE_CONFIG` so the
project's own `.opencode/opencode.json` stayed as scaffolded. `git` was
kept off `PATH`, for the zombie-child stall HARNESS.md records.

The prompt asked for `survey-writer-opencode` and answered its scoping
questions up front, since `opencode run` cannot stop to ask: the slug,
the reader, what it covers and excludes, no collection, `en-GB`, and
about 1,000 words.

| Measure | Value |
| --- | --- |
| Wall time | 38 minutes |
| Model requests | 30 |
| Tool calls | 45: 27 `bash`, 8 `edit`, 6 `read`, 3 `write`, 1 `skill` |
| Prompt before the skill loads | 17,816 tokens |
| Prompt once the skill is loaded | 29,790 tokens |
| Largest prompt | 49,161 tokens |
| Draft | 1,459 words, 9 citations of all 5 sample papers |

**What the model did.** It followed the skill in order. It checked the
ledger and its collections, ran `dossier init` and `outline --check`,
searched four sub-themes with `--log`, read evidence for each paper,
and filled `scope.md`, `evidence.md` and `rejected.md`. It wrote the
draft, ran `draft gate`, `references`, `render`, `dossier sections`,
`review verbatim scan`, `dossier stamp`, `draft evidence` and
`draft style`, and presented. It used `write` once to create the draft
and `edit` for every later change, as the OpenCode copy of the skill
asks. One `edit` failed because its old and new strings were identical.
The model moved on, and nothing else went wrong with the file tools.

**Where each check fired.**

- **Self-check.** The model ran `draft gate` twice, and both runs
  passed with 9 citations verified. It never wrote an unknown key, so
  nothing had to be fixed.
- **Mandatory check.** The plugin ran on every `write` and `edit` to the
  draft. A pass is silent, so the proof is the liveness record:
  `content/.gate-seen/` held the hash of the final draft, and a gate
  run by hand afterwards printed no warning. The style hook's advisory
  notes reached the model inside the tool result of four of the six
  successful draft writes.
- **Last check.** `draft render` produced `.tex`, `.pdf` and `.md`.
  Its first run warned that the comparison table had no caption line.
  The model fixed the caption and rendered again without the warning.

**Did the skill fit?** Yes. The largest prompt used 38% of the
131,072-token window. It would not fit an 8k or 16k window: the
system prompt with `AGENTS.md` and the skill list is about 18,000
tokens before the skill loads. A 32k window would overflow within the
first few retrievals.

**What the model got wrong.** The verbatim scan found passages of 47
to 62 words copied almost exactly from three sources, some of them in
paragraphs that do not cite the source. Step 17 of the skill says to
show those findings rather than summarise them away. The model ran the
scan and left the findings out of its final summary. That is not a
gate failure, since the scan is a review aid, but a person reading only
the summary would not know about the copied passages.

## ⛔ Codex: blocked by the sandbox in this container

**Codex 0.159.3**, with a custom provider on the Responses API. No
survey was drafted.

- **Codex's own sandbox cannot run a command here.** Its Linux sandbox
  uses bubblewrap, and this container's kernel refuses unprivileged user
  namespaces. Every shell command failed with `bwrap: No permissions to
  create new namespace`, so the model could not run retrieval, the
  gate or render.
- **Running without the sandbox was not attempted.** That needs
  `--dangerously-bypass-approvals-and-sandbox`, and the environment
  this was recorded in does not allow an unsandboxed agent on a live
  model without a person's explicit approval.
- **A model Codex does not know gets no `apply_patch`.** Under the name
  `qwen3.6-35b-a3b`, Codex offered only its shell tools. A draft
  written through the shell is invisible to the gate hook, which fires
  on `apply_patch`. A `model_catalog_json` file with an entry for the
  model, copied from a built-in model's entry with
  `"apply_patch_tool_type": "freeform"`, made Codex offer `apply_patch`.
  Asked to create a file with it, the model never called it and tried
  the shell instead. So a local-model
  setup on Codex needs that catalog entry, or the mandatory check is
  bypassed by default.
- **Skills and context.** Codex listed the nine project skills from
  `.agents/skills/` and read `AGENTS.md` natively. Its first request
  was about 14,000 tokens.
- **Hooks.** The run did not trust the project's hooks, so none fired;
  no session-start message reached the model.

## 🔎 Continue: what a real session showed

**Continue CLI (`cn`) 1.5.47.** Issue 901 lists four facts to confirm on
a real session before building its MCP server. The CLI's source and a
live probe answer three of them, and add a fourth.

- **Built-in tools can be excluded, but not from a project file.**
  `--exclude <tool>` works: a probe with `--exclude Bash` was offered no
  shell. The only file it reads permissions from is the user's
  `~/.continue/permissions.yaml`. Permissions in the project's
  `config.yaml` are marked "when implemented" in the CLI's precedence
  code. A project cannot exclude the write tools for itself today.
- **Project skills come from `.continue/skills/` and `.claude/skills/`**,
  plus the user's `~/.continue/skills/`. It does not read
  `.agents/skills/`.
- **It reads `AGENTS.md` natively**, taking the first of `AGENTS.md`,
  `AGENT.md`, `CLAUDE.md` and `CODEX.md` in the project root.
- **It loads Claude Code-style hooks but never runs them on a tool.**
  The CLI reads hook settings from `.claude/settings.json`,
  `.continue/settings.json` and their `.local` variants. But no tool
  call dispatches a `PostToolUse` or `PreToolUse` event; only its
  built-in git-ai tracker sees file edits. In the live probe, Continue
  wrote `content/drafts/probe.md` with `Write`, the project's gate hook
  did not run, and a gate run by hand printed the liveness warning. Even
  if dispatch is added later, Continue runs a hook's `command` string
  through a shell and ignores `args`, so the scaffolded Claude Code
  launcher would need a different shape.

Not yet confirmed: whether a local model through Continue calls MCP
tools reliably, since the MCP server is not built.

## 📋 Still to record

- **A Codex survey on a local model**, on a host where Codex's sandbox
  works or with a person's approval to run it unsandboxed. Use the
  model catalog entry above, or the run measures the shell path only.
- **The same OpenCode run on a smaller window**, 32k, to see where it
  overflows and how OpenCode compacts.
- **A Continue survey**, once the MCP server from issue 901 exists.
