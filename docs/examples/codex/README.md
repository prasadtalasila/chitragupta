# 🧪 Codex on a local model: one recorded survey

Status: **reference artefacts.** Recorded 2026-10-02.

**Written for** anyone deciding whether to draft with Codex against a
model on their own hardware. Everything under `content/` is the real
output of one run of [`run.sh`](run.sh): a survey drafted end to end by
Codex driving a local model over the five synthetic sample papers in
[`papers/`](papers/bibliography.bib). Nothing in it was edited
afterwards. [LOCAL-MODELS.md](../../LOCAL-MODELS.md) sets this run beside
the OpenCode one and says what each shows.

The honesty notes from [the examples map](../README.md) hold here too:
the sources are synthetic, and the draft is a sample of what this
harness and model did, not of scholarship. **One run says what happened
once.** A second run of the same script on the same model can take a
different path, and did -- see "Two runs, two paths" below.

## 🗺 What is here

| Path | What it is |
| --- | --- |
| [`prompt.txt`](prompt.txt) | the one message the run sent, answering the skill's scoping questions up front, since `codex exec` cannot stop to ask |
| [`run.sh`](run.sh) | the script that produced everything under `content/` |
| [`config.toml`](config.toml), [`papers/`](papers/bibliography.bib) | the inputs, the same as [`sample-project/`](../sample-project/)'s |
| [`content/drafts/dt-survey.md`](content/drafts/dt-survey.md) | the draft, gate-passed |
| `content/dossiers/dt-survey/` | the dossier files the model wrote |
| [`content/rendered/dt-survey.pdf`](content/rendered/dt-survey.pdf), [`dt-survey.markdown`](content/rendered/dt-survey.markdown) | the renders |
| `content/events.jsonl` | Codex's own event stream for the run (`codex exec --json`): every command, its output and every message |

## 🔄 Re-running it

You need `chitragupta-cli` from PyPI, the `codex` CLI, and a server that
speaks OpenAI's Responses API. The recorded run used:

| Item | Value |
| --- | --- |
| chitragupta | 6.128.0, `pip install chitragupta-cli` |
| Codex | 0.159.3 |
| Model | Qwen3.6-35B-A3B, Unsloth `UD-Q4_K_M` GGUF |
| Server | llama.cpp `llama-server` b11321 on CPU, 131,072-token context, one slot |

```bash
BASE_URL=http://127.0.0.1:18080/v1 MODEL=qwen3.6-35b-a3b bash run.sh /tmp/codex-run
```

`run.sh` scaffolds a fresh project with `chitragupta init --agent
codex` in the directory you give it, copies `papers/` and `config.toml`
in, runs a real `corpus sync`, and starts Codex. It never writes into
this directory.

It runs Codex with `--dangerously-bypass-approvals-and-sandbox` and
`--dangerously-bypass-hook-trust`. The first is needed on any host
where Codex's bubblewrap sandbox cannot create user namespaces, which
included the recording host: there, every sandboxed command fails. The
second trusts the project's hooks for this one invocation, so the gate
hook is allowed to run. Run it only in a scratch directory.

## 🔍 What the run did

| Measure | Value |
| --- | --- |
| Wall time | 20 minutes |
| Model requests | 22 |
| Shell commands | 31 |
| `apply_patch` calls | 0 |
| Largest prompt | 30,297 tokens |
| Draft | 839 words, 16 citations of 4 of the 5 sample papers |

It read the skill, checked the ledger, ran four retrievals and wrote the
draft. It ran `draft gate`, `dossier sections`, the verbatim scan,
`dossier stamp` and `draft render`, and presented.

**Every file it wrote went through the shell**, as a `cat > file <<
EOF` here-document: the scope, the retrieval log, the evidence, the
rejected list and the draft, twice. It never called `apply_patch`, and
it could not have: llama.cpp's server drops a Responses tool of type
`custom`, which is how Codex sends `apply_patch`, so the model was never
offered it.

**Where each check fired.**

- **Self-check.** `draft gate` ran twice and passed both times, all 16
  citations verified. Both runs also printed the liveness warning: no
  automatic gate had checked the draft since it last changed.
- **Mandatory check.** It never fired. The gate hook runs on
  `apply_patch`, and no `apply_patch` call was made. The liveness
  warning is the only sign of that, and the model read past it.
- **Last check.** `draft render` passed the gate and wrote the PDF.

**Where it left the skill.**

- It never ran `dossier init`. It made the dossier folder with `mkdir`
  and wrote `scope.md` itself, so the dossier has no `README.md`,
  `steering.md` or `revisions.md`, and no corpus fingerprint.
- It passed the slug, not the draft's path, to `retrieve search --log`,
  so no search was logged. It then wrote `retrieval.md` by hand. That
  file looks like a log but is the model's own account of its searches.
- It typed the References list into the draft rather than running
  `draft references`.
- It asked for `--format markdown`, which pandoc accepts and names
  `dt-survey.markdown`, rather than `--format md`.

**What it did well.** The first verbatim scan found passages copied
from the sources. The model rewrote them and scanned again, and the
second scan found no run of eight or more words in common with any
source.

## 🔀 Two runs, two paths

An earlier run of the same prompt, on the same model and package, took
the skill's path more closely. It ran `dossier init`, logged all four
searches, ran `draft references` and rendered `md`, `tex` and `pdf`. It
wrote every file through the shell too, and its draft gate passed with
17 citations and the same liveness warning. The model server ran out of
memory during its final style fixes, so it never finished, and its
output is not committed. Read the two together as a range, not a
verdict.
