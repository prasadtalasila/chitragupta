# 🖥 Local models: recorded runs on Codex, OpenCode and Continue

Status: **two runs recorded.** Written 2026-10-02 for
[issue 904](https://github.com/prasadtalasila/chitragupta/issues/904),
with the Continue facts
[issue 901](https://github.com/prasadtalasila/chitragupta/issues/901)
asked to confirm before building.

[HARNESS.md](HARNESS.md) measured the plumbing with a scripted stand-in
model. This file records what a real local model did with it: one
survey drafted end to end through Codex, and one through OpenCode. Each
run is committed whole as a self-contained example, with its inputs,
its script and everything it wrote:
[`examples/codex/`](examples/codex/README.md) and
[`examples/opencode/`](examples/opencode/README.md). This page compares
them and records what they showed about each harness. It makes no
general quality claim. Each record is one run on one model over the
five-paper sample corpus, and a second run could go differently.
[LLM-AGENTS.md](LLM-AGENTS.md) turns these runs into setup advice for
each agent.

## 🧭 Table of contents

- [The setup both runs shared](#-the-setup-both-runs-shared)
- [Where each check fired](#-where-each-check-fired)
- [OpenCode: the plugin refused a write, and the model fixed it](#-opencode-the-plugin-refused-a-write-and-the-model-fixed-it)
- [Codex: the gate hook never fired](#-codex-the-gate-hook-never-fired)
- [Did the skill fit in context?](#-did-the-skill-fit-in-context)
- [Continue: what a real session showed](#-continue-what-a-real-session-showed)
- [Still to record](#-still-to-record)

## 🧪 The setup both runs shared

| Item | Value |
| --- | --- |
| Date | 2026-10-02 |
| chitragupta | 6.128.0 from PyPI, `pip install chitragupta-cli` |
| Codex | 0.159.3 |
| OpenCode | 1.18.34 |
| Model | Qwen3.6-35B-A3B, Unsloth `UD-Q4_K_M` GGUF |
| Server | llama.cpp `llama-server` b11321, CPU, one slot |
| Context | 131,072 tokens |
| Speed | about 88 tokens/s prompt, 14 tokens/s output |

Each run scaffolded a fresh project with `chitragupta init --agent
<harness>`, copied in the sample project's papers and `config.toml`,
ran a real `corpus sync`, and sent the same prompt: draft a survey with
the harness's own copy of `survey-writer`, with the skill's scoping
questions answered up front. Each example's `run.sh` is the script that
ran. The one change since is a guard that refuses to run into an
existing directory. A logging proxy between each harness and the server
recorded every request, which is where the tool lists and context sizes
come from.

## 📊 Where each check fired

| Check | Codex | OpenCode |
| --- | --- | --- |
| Self-check, `draft gate` run by the model | ran twice, passed, warned twice that no hook had seen the draft | ran once, passed |
| Mandatory check, the hook or plugin | **never fired**: no `apply_patch` call was made | fired on every draft write, and **refused one** |
| Last check, `draft render` | passed, wrote a PDF and a `.markdown` file | passed, wrote `.tex`, `.pdf` and `.md` |
| Unknown citekeys in the final draft | none | none |

Neither model left a citekey that is missing from the ledger in its
final draft. The only unknown key either run produced was a placeholder,
and the OpenCode plugin caught it.

## ✅ OpenCode: the plugin refused a write, and the model fixed it

[The example](examples/opencode/README.md) has the run step by step.
In short, the model followed the skill in order, wrote every file it
authored through OpenCode's `write` and `edit` tools, and finished in 34
minutes.

The mandatory check worked as designed on a real model. The first
`write` of the draft carried a placeholder `[@citekey]` in an HTML
comment above the reference list. The plugin returned `Citation gate
FAILED`, naming the line and the key, as the tool's result. The model
read the line and wrapped the placeholder in a code span. It did not
replace the placeholder with a real key, which is the failure the
refusal's wording is written to prevent.

The liveness warning also fires on the pipeline's own write. `draft
references` rewrote the draft after the plugin's last check. The model's
own gate run came before that and saw no warning, but a gate run by hand
after the session warns that no automatic gate saw the current text.
The warning cannot tell a pipeline command from a shell write. It never
changes the gate's verdict, but it makes a correctly drafted survey look
ungated.

The model only half followed the skill's reporting step. The verbatim
scan found 25 overlaps with the sources, the longest six running 27 to
54 words. The final summary said overlaps were found and listed none of
them.

An earlier OpenCode run, on the same model with chitragupta 6.128.5
installed from a checkout, went the same way apart from the refusal: it
wrote no placeholder, the plugin passed every write, and its summary
left the verbatim findings out entirely. It is not committed.

## ⛔ Codex: the gate hook never fired

[The example](examples/codex/README.md) has the run step by step.

Codex's sandbox could not run anything on the recording host. Its
bubblewrap sandbox needs unprivileged user namespaces, which the host
refuses, so every sandboxed command fails with `bwrap: No permissions
to create new namespace`. The run therefore used
`--dangerously-bypass-approvals-and-sandbox`, and
`--dangerously-bypass-hook-trust` so the project's hooks would run.

The model was never offered `apply_patch`. Codex sends `apply_patch` as
a Responses tool of type `custom`, and llama.cpp's server skips that
type with a warning. Under a model name Codex does not know, it offers
no `apply_patch` at all. A `model_catalog_json` entry cloned from a
built-in model makes Codex offer it, but only with
`"apply_patch_tool_type": "freeform"` (Codex 0.159.3 accepts no other
value), so llama.cpp still drops it. Codex no longer has a
chat-completions wire API to fall back on.

So the model wrote every file with a shell here-document, and the gate
hook, which fires on `apply_patch`, never ran. The liveness warning
showed it: both of the model's own `draft gate` runs printed it, and the
model read past it both times. The gate itself passed, with 16
citations, all real. Render would have refused an unknown key, so
nothing ungated could have become a document. But nothing would have
told the model to fix a bad key while it was drafting.

The run also skipped steps the skill requires. It never ran `dossier
init` and made the dossier folder by hand. It passed the slug rather
than the draft's path to `retrieve search --log`, so nothing was
logged, and then wrote `retrieval.md` itself. It typed the reference
list rather than running `draft references`. It did rewrite the
passages its first verbatim scan flagged, and its second scan was
clean.

An earlier Codex run with the same prompt kept closer to the skill: it
ran `dossier init`, logged its searches, ran `draft references` and
rendered three formats. It also wrote everything through the shell, and
its gate passed with the same liveness warning. The model server ran out
of memory during its final edits, so it never finished, and it is not
committed.

## 📏 Did the skill fit in context?

Yes, on both, with room to spare at 131,072 tokens.

| Measure | Codex | OpenCode |
| --- | --- | --- |
| Model requests | 22 | 19 |
| Largest prompt | 30,297 tokens | 44,486 tokens |
| Share of the window | 23% | 34% |
| Wall time | 20 minutes | 34 minutes |

It would not fit a small window. OpenCode's prompt is about 18,000
tokens before the skill loads and about 30,000 once it has, so a 32k
window overflows within the first few retrievals, and an 8k or 16k one
cannot hold the skill at all. Splitting the skill would not change that
much, because most of the base prompt is the harness's own system
prompt, `AGENTS.md` and the skill list.

## 🔎 Continue: what a real session showed

This section covers the Continue CLI (`cn`), version 1.5.47. Issue 901
lists four facts to confirm on a real session before building its MCP
server. The CLI's source and a live probe answer three of them and add
a fourth.

- A user can exclude built-in tools, but a project file cannot.
  `--exclude <tool>` works: a probe with `--exclude Bash` was offered no
  shell. The only file Continue reads permissions from is the user's
  `~/.continue/permissions.yaml`. Permissions in the project's
  `config.yaml` are marked "when implemented" in the CLI's precedence
  code, so a project cannot exclude the write tools for itself today.
- Project skills come from `.continue/skills/` and `.claude/skills/`,
  plus the user's `~/.continue/skills/`. Continue does not read
  `.agents/skills/`.
- It reads `AGENTS.md` natively, taking the first of `AGENTS.md`,
  `AGENT.md`, `CLAUDE.md` and `CODEX.md` in the project root.
- It loads Claude Code-style hooks but never runs them on a tool call.
  The CLI reads hook settings from `.claude/settings.json`,
  `.continue/settings.json` and their `.local` variants, yet no tool
  call dispatches a `PostToolUse` or `PreToolUse` event; only its
  built-in git-ai tracker sees file edits. In the live probe, Continue
  wrote `content/drafts/probe.md` with `Write`, the project's gate hook
  did not run, and a gate run by hand printed the liveness warning. If
  dispatch is added later, the scaffolded Claude Code launcher will
  still need a different shape, because Continue runs a hook's `command`
  string through a shell and ignores `args`.

Whether a local model through Continue calls MCP tools reliably is not
yet confirmed, since the MCP server is not built.

## 📋 Still to record

- Codex with a server that accepts `custom` tools, so the model is
  offered `apply_patch` and the gate hook can fire. Issue 904 named
  Ollama's and LM Studio's Responses support, through `--oss`.
- A 32k window, to see where each harness overflows and how it
  compacts.
- A Continue survey, once issue 901's MCP server exists.
