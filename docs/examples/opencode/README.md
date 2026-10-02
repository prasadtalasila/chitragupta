# 🧪 OpenCode on a local model: one recorded survey

Status: **reference artefacts.** Recorded 2026-10-02.

**Written for** anyone deciding whether to draft with OpenCode against
a model on their own hardware. Everything under `content/` is the real
output of one run of [`run.sh`](run.sh): a survey drafted end to end by
OpenCode driving a local model over the five synthetic sample papers in
[`papers/`](papers/bibliography.bib). Nothing in it was edited
afterwards. [LOCAL-MODELS.md](../../LOCAL-MODELS.md) sets this run beside
the Codex one and says what each shows.

The honesty notes from [the examples map](../README.md) hold here too:
the sources are synthetic, and the draft is a sample of what this
harness and model did, not of scholarship. **One run says what happened
once**; a second run of the same script can take a different path.

## 🗺 What is here

| Path | What it is |
| --- | --- |
| [`prompt.txt`](prompt.txt) | the one message the run sent, answering the skill's scoping questions up front, since `opencode run` cannot stop to ask |
| [`run.sh`](run.sh) | the script that produced everything under `content/` |
| [`opencode-provider.json`](opencode-provider.json) | the local-model provider, read through `OPENCODE_CONFIG` |
| [`config.toml`](config.toml), [`papers/`](papers/bibliography.bib) | the inputs, the same as [`sample-project/`](../sample-project/)'s |
| [`content/drafts/dt-survey.md`](content/drafts/dt-survey.md) | the draft, gate-passed and referenced |
| `content/dossiers/dt-survey/` | the dossier, from `dossier init` and the model's own edits |
| [`content/rendered/dt-survey.pdf`](content/rendered/dt-survey.pdf), [`dt-survey.md`](content/rendered/dt-survey.md), [`dt-survey.tex`](content/rendered/dt-survey.tex) | the renders |
| `content/events.jsonl` | OpenCode's own event stream for the run (`opencode run --format json`): every tool call, its result and every message |

## 🔄 Re-running it

You need `chitragupta-cli` from PyPI, the `opencode` CLI, and a server
with an OpenAI-compatible chat-completions endpoint. The recorded run
used:

| Item | Value |
| --- | --- |
| chitragupta | 6.128.0, `pip install chitragupta-cli` |
| OpenCode | 1.18.34 |
| Model | Qwen3.6-35B-A3B, Unsloth `UD-Q4_K_M` GGUF |
| Server | llama.cpp `llama-server` b11321 on CPU, 131,072-token context, one slot |

```bash
BASE_URL=http://127.0.0.1:18080/v1 bash run.sh /tmp/opencode-run
```

`run.sh` scaffolds a fresh project with `chitragupta init --agent
opencode` in the directory you give it, copies `papers/` and
`config.toml` in, runs a real `corpus sync`, and starts OpenCode. It
never writes into this directory. The provider comes from
`opencode-provider.json`, so the project's own `.opencode/opencode.json`
keeps the skill deny list `init` wrote. To use another model, edit the
model's name and limits there.

OpenCode needs no sandbox flag: it runs its tools directly. One
environment trap is recorded in [HARNESS.md](../../HARNESS.md): in some
containers OpenCode never reaps a `git` child and stalls before its
first model call. The recorded run had `git` off `PATH` for that
reason, and `run.sh` does not need it.

## 🔍 What the run did

| Measure | Value |
| --- | --- |
| Wall time | 34 minutes |
| Model requests | 19 |
| Tool calls | 34: 26 `bash`, 4 `write`, 2 `read`, 1 `edit`, 1 `skill` |
| Largest prompt | 44,486 tokens |
| Draft | 1,623 words with references, 13 citations of all 5 sample papers |

It followed the skill in order. It checked the ledger, ran `dossier
init` and `outline --check`, filled `scope.md`, logged four searches
and five evidence reads, and wrote `evidence.md` and `rejected.md`.
It wrote the draft, ran `draft gate`, `references`, `dossier sections`,
`render` in three formats, `draft evidence`, `draft style`, the
verbatim scan and `dossier stamp`, and presented. Every file it wrote
itself, rather than through a pipeline command, went through OpenCode's
own `write` and `edit` tools.

**Where each check fired.**

- **Mandatory check.** It fired, and it refused. The model's first
  `write` of the draft put a placeholder `[@citekey]` inside an HTML
  comment it had written above the reference list. The plugin handed
  back `Citation gate FAILED`, naming line 81 and `@citekey`, as the
  tool's result. The model read the line, wrapped the placeholder in a
  code span with one `edit`, and the plugin passed the edit. It did not
  swap in a real key.
- **Self-check.** `draft gate` then passed with 13 citations verified.
- **Last check.** `draft render` passed the gate and wrote `.tex`,
  `.pdf` and `.md`.

**The liveness warning fires afterwards, and here it is a false alarm.**
`draft references` rewrote the draft after the plugin's last check, so a
gate run by hand on the committed draft prints "no automatic gate has
checked" it. The text that changed is the References section the
pipeline itself generated from gated keys. The warning cannot tell its
own pipeline's write from a shell write.

**Where it left the skill.**

- The verbatim scan found passages of 27 to 54 words copied almost
  exactly from the sources, some in paragraphs that do not cite them.
  The final summary says overlaps were found "across all 5 papers" but
  lists none. The skill asks for the long and short findings to be
  shown, not summarised.
- The draft runs to 1,623 words against the 800 to 1,200 asked for.
