# 🖥 Local models: recorded runs on Codex, OpenCode and Continue

Status: **measurements.**

[HARNESS.md](HARNESS.md) measured the plumbing with a scripted stand-in
model. This page records what a real local model did with it: one survey
drafted end to end through Codex and one through OpenCode, each committed
whole with its inputs, script and outputs
([`examples/codex/`](examples/codex/README.md),
[`examples/opencode/`](examples/opencode/README.md)), plus the Continue
facts
[issue 901](https://github.com/prasadtalasila/chitragupta/issues/901)
asked to confirm before building. Each record is one run on one model
over the five-paper sample corpus, so it makes no general quality claim.
[LLM-AGENTS.md](LLM-AGENTS.md) turns these runs into setup advice.

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
<harness>`, copied in the sample project's papers and `config.toml`, ran
a real `corpus sync`, and asked the harness's own `survey-writer` for a
survey, with the scoping questions answered up front. Each example's
`run.sh` is the script that ran. A logging proxy between harness and
server recorded every request, which is where the tool lists and context
sizes come from.

## 📊 Where each check fired

| Check | Codex | OpenCode |
| --- | --- | --- |
| Self-check, `draft gate` run by the model | ran twice, passed, warned twice that no hook had seen the draft | ran once, passed |
| Mandatory check, the hook or plugin | **never fired**: no `apply_patch` call was made | fired on every draft write, and **refused one** |
| Last check, `draft render` | passed, wrote a PDF and a `.markdown` file | passed, wrote `.tex`, `.pdf` and `.md` |
| Unknown citekeys in the final draft | none | none |

The only unknown key either run produced was a placeholder, and the
OpenCode plugin caught it.

## ✅ OpenCode: the plugin refused a write, and the model fixed it

The model followed the skill in order and wrote every file through
OpenCode's `write` and `edit` tools ([the
example](examples/opencode/README.md) has the run step by step). The
first `write` of the draft carried a placeholder `[@citekey]` in an HTML
comment above the reference list. The plugin returned `Citation gate
FAILED`, naming the line and the key, as the tool's result. The model
wrapped the placeholder in a code span. It did not replace it with a
real key, which is the failure the refusal's wording is written to
prevent.

The liveness warning also fires on the pipeline's own write: `draft
references` rewrote the draft after the plugin's last check, so a gate
run by hand afterwards warns that no automatic gate saw the current text.
The warning cannot tell a pipeline command from a shell write. It never
changes the gate's verdict, but it makes a correctly drafted survey look
ungated.

The verbatim scan found 25 overlaps with the sources, the longest six
running 27 to 54 words; the final summary said overlaps were found and
listed none. An earlier, uncommitted OpenCode run wrote no placeholder
and left the verbatim findings out of its summary entirely.

## ⛔ Codex: the gate hook never fired

[The example](examples/codex/README.md) has the run step by step.
Codex's bubblewrap sandbox needs unprivileged user namespaces, which the
recording host refuses, so every sandboxed command failed with `bwrap: No
permissions to create new namespace`. The run therefore used
`--dangerously-bypass-approvals-and-sandbox`, and
`--dangerously-bypass-hook-trust` so the project's hooks would run.

The model was never offered `apply_patch`. Codex sends `apply_patch` as
a Responses tool of type `custom`, and llama.cpp's server skips that
type with a warning. Under a model name Codex does not know, it offers
no `apply_patch` at all. A `model_catalog_json` entry cloned from a
built-in model makes Codex offer it, but only with
`"apply_patch_tool_type": "freeform"` (Codex 0.159.3 accepts no other
value), so llama.cpp still drops it. Codex has no
chat-completions wire API to fall back on.

So the model wrote every file with a shell here-document, and the gate
hook, which fires on `apply_patch`, never ran. Both of the model's own
`draft gate` runs printed the liveness warning, and the model read past
it both times. The gate passed, with 16 citations, all real, and render
would have refused an unknown key. But nothing would have told the model
to fix a bad key while it was drafting.

The run also skipped steps the skill requires: it made the dossier by
hand instead of running `dossier init`, logged no searches, and typed the
reference list instead of running `draft references`. An earlier,
uncommitted Codex run kept closer to the skill but also wrote everything
through the shell.

## 📏 Did the skill fit in context?

Yes, on both, with room to spare at 131,072 tokens.

| Measure | Codex | OpenCode |
| --- | --- | --- |
| Model requests | 22 | 19 |
| Largest prompt | 30,297 tokens | 44,486 tokens |
| Share of the window | 23% | 34% |
| Wall time | 20 minutes | 34 minutes |

It would not fit a small window. OpenCode's prompt is about 18,000
tokens before the skill loads and about 30,000 after, so a 32k window
overflows within the first few retrievals, and an 8k or 16k one cannot
hold the skill at all. Most of the base prompt is the harness's own
system prompt, `AGENTS.md` and the skill list, so splitting the skill
would not change that much.

## 🔎 Continue: what a real session showed

For the Continue CLI (`cn`) 1.5.47, the CLI's source and a live probe
answered three of issue 901's questions and added a fourth.

- A user can exclude built-in tools (`--exclude Bash` removed the
  shell), but a project file cannot: permissions come only from the
  user's `~/.continue/permissions.yaml`, and project `config.yaml`
  permissions are marked "when implemented" in the CLI's source.
- Project skills come from `.continue/skills/` and `.claude/skills/`,
  plus the user's `~/.continue/skills/`. Continue does not read
  `.agents/skills/`.
- It reads `AGENTS.md` natively, taking the first of `AGENTS.md`,
  `AGENT.md`, `CLAUDE.md` and `CODEX.md` in the project root.
- It loads Claude Code-style hooks from `.claude/settings.json`,
  `.continue/settings.json` and their `.local` variants, but no tool call
  dispatches a `PostToolUse` or `PreToolUse` event. In the probe,
  Continue wrote `content/drafts/probe.md` with `Write`, the gate hook
  did not run, and a gate run by hand printed the liveness warning. If
  dispatch is added later, the scaffolded launcher will still need a
  different shape, because Continue runs a hook's `command` string
  through a shell and ignores `args`.

## 📋 Still to record

- Codex with a server that accepts `custom` tools, so the model is
  offered `apply_patch` and the gate hook can fire (Ollama's or LM
  Studio's Responses support, through `--oss`).
- A 32k window, to see where each harness overflows and how it
  compacts.
- A Continue survey, once issue 901's MCP server exists.
