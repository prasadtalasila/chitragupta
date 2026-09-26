# 🔌 A harness-neutral core with thin per-harness adapters (#812)

Status: **design, unbuilt.** Written 2026-09-26. Implements
[issue 812](https://github.com/prasadtalasila/chitragupta/issues/812).
Nothing is built yet. Record here which PR closed each step, and what
changed along the way.

Everything under `chitragupta/` is already harness-neutral. It makes no
LLM call, and retrieval's embedding models run locally. Everything above
it assumes Claude Code: `.claude/settings.json`, `.claude/hooks/`,
`.claude/skills/` and `.claude/agents/`. This plan moves the parts that
have to hold on every harness down into layer 1. It then gives each
harness a thin adapter over that core, so the pipeline can be driven from
Codex or Continue, including against a model hosted on the user's own
machine.

**Written for** whoever builds 812, one step at a time. It assumes
[docs/HOOKS.md](../docs/HOOKS.md), whose three-layer rule (checks,
adapters, launcher) this plan extends rather than replaces. It also
assumes [docs/CLI.md](../docs/CLI.md)'s tier-1 promise: the gate chain
imports nothing outside the standard library.
[DEVELOPER-AGENTS.md](../DEVELOPER-AGENTS.md) covers the cycle around
each step.

**Assumed, and not re-argued:** the decision between the two shapes. The
issue's "Alternatives Considered" rejects per-harness copies, because
nine 5,000-7,700-word skills copied three ways will drift, and a drifted
gate is a way for a fabricated citekey to get through. The choice made is
a neutral core with thin adapters.

**Not covered here:** developing chitragupta *itself* from Codex or
Continue. `code_standards_hook.py` gets a Codex adapter almost for free
in step 3, but `DEVELOPER-AGENTS.md`'s workflow stays Claude Code-first.
Also not covered: a container image for a second harness, since
`docker/Dockerfile.claude` stays as it is. This plan does not judge
whether a given local model writes *good* prose; it makes sure a bad
model cannot fabricate a citekey unnoticed.

## 🔑 The constraint every step answers to

> **On every supported harness, a fabricated citekey is stopped by
> something the model cannot skip -- and a harness where that cannot be
> arranged is not supported.**

This constraint is what orders the work. Today the only automatic
enforcement is `citation_gate_hook.py`, and it depends on four Claude
Code facts:

- the `Write|Edit` matcher;
- a `tool_input.file_path` in the payload;
- the `${CLAUDE_PROJECT_DIR}` placeholder;
- `.claude/settings.json` being read at all.

On the other two harnesses:

| Harness | Hooks | What happens to the gate today |
| --- | --- | --- |
| Claude Code | yes | enforced after the write lands, measured in `docs/HOOKS.md` |
| Codex | yes: `PostToolUse` with a compatible `{"decision": "block"}` shape, configured in `.codex/hooks.json` or `config.toml` | **silently inert.** Edits go through `apply_patch`, whose payload carries the patch text in `tool_input.command` and has no `file_path`. The matcher never fires. If it did, `draft_target._file_path` returns `""` and the hook fails open |
| Continue | none in its config reference | not enforced; only the skill's instruction |

Two things that look like a portable gate are not one:

- **A git pre-commit hook.** `content/drafts/` is gitignored, so a draft
  is never committed and the hook never sees it.
- **The skills' instruction to run `draft gate`.** That is the "asked,
  not enforced" posture ARCHITECTURE.md's "Grounding is enforced, not
  requested" rules out. A local model is the likeliest to skip the step,
  and also the likeliest to fabricate.

Today `render` does not run the gate. Only `draft unit accept` refuses an
ungated draft, and that is on the book track only.

## 🏗 The target shape

```text
chitragupta/                    layer 1 -- harness-neutral checks, stdlib gate chain
├── citation_gate.py            unchanged
├── render_output/              gains: refuses a draft the gate fails (step 1)
├── mcp_server.py               new: stdlib MCP stdio server, gated write tools (step 2)
└── hook_launchers.py           reads every harness's launcher config (step 3)

.agents/                        the neutral source of truth
├── skills/<name>/SKILL.md      canonical skills; Codex reads this path natively (step 4)
└── hooks/                      adapters: payload in, one envelope out (step 3)
    ├── draft_target.py         learns every harness's payload shape
    ├── envelope.py             emits only the field the named host consumes
    └── *_hook.py               the four hooks, moved, with `--harness <name>`

.claude/  .codex/  .continue/   layer 3 -- launchers and generated copies only
```

The rule that keeps this honest is the one `docs/HOOKS.md` already
states for `.claude/hooks/`: **an adapter contains no logic anyone could
want to run by hand**. Adding harnesses adds adapters, and no checks.
The per-harness directories hold launcher config plus generated files,
and never anything hand-edited that another harness lacks.

## 🪜 The steps, in order

Each step is one PR, can be released on its own, and leaves every
existing Claude Code project working. Steps 1 and 2 come first because
they are what makes any second harness safe to support.

### 1. The gate runs at render, on every harness

`draft render` runs `citation_gate.check_text` on the text it is about to
render. If the gate reports `FAIL`, render refuses with the same
citekey-naming report the gate prints. This puts the invariant at the
output boundary, so no harness, hook or model can render around it. It
stays on the tier-1 chain, because `render_output` already imports
`citation_gate`.

- **Decision needed: what a refusal means for the version.** Rendering a
  draft that renders today becomes an error. `DEVELOPER-AGENTS.md`'s
  versioning section calls a change MAJOR when it "requires an existing
  user to change how they invoke" the pipeline, and a user whose draft
  now refuses to render has to. Recommended: MAJOR. Do not add an
  escape-hatch flag, because the gate must not be individually
  disableable (`docs/HOOKS.md`, "Deliberately not done").
- **Decision needed: the gate's corpus-independence.** HOOKS.md measured
  that the gate exits 0 on a citation-free draft with no ledger at all.
  Render has to keep that property, or a pre-sync teaching draft stops
  rendering.
- This is not a new check promoted into a gate. It is the existing gate
  invoked at a second point, and the issue's success criterion is worded
  to allow exactly that.

### 2. A gated write path the model calls: a stdlib MCP server

`chitragupta mcp` (and `python -m chitragupta.mcp_server`) is a stdio
Model Context Protocol server. It exposes:

- `draft_write(path, text)`: runs the gate on `text` **before** writing,
  refuses on `FAIL`, and writes only under `content/drafts/`;
- `draft_edit(path, old, new)`: an exact-span replacement with the same
  pre-write gate on the resulting text;
- `draft_gate(path)` and `draft_style(path)`, the hand-runnable checks as
  tools;
- `retrieval_search(...)`, so a harness without a shell tool can still
  retrieve.

It checks before the write, which is stronger than today's post-write
hook. A bad citekey never reaches disk by this path. It is also the only
enforcement available on Continue, and it gives a local model one short
tool description in place of a paragraph of rules about `Edit` and
`Write`.

- **Decision needed: SDK or stdlib.** The `mcp` Python SDK is the easy
  path, but it would take the server off tier 1. **Recommended: stdlib.**
  MCP over stdio is newline-delimited JSON-RPC, and the server needs only
  `initialize`, `tools/list` and `tools/call`. Pin the protocol version
  it speaks, and test it against a recorded handshake from each harness.
- **Decision needed: does MCP become the canonical write path on Claude
  Code too?** Recommended: yes. Every skill then says "write drafts with
  `draft_write` / `draft_edit`", on every harness, and the hooks become
  the backstop for a model that uses a built-in write tool anyway. That
  unifies the skill prose, which step 4 depends on.
- **To confirm:** whether Continue and Codex can be configured to hide
  their built-in file-write tools from the agent. If they can, the
  scaffold should do so. If they cannot, the MCP path is advisory on
  Continue, and render (step 1) is Continue's only hard stop. The
  supported-harness table in the docs must then say so plainly.

### 3. Hook adapters that understand more than one harness

Move `.claude/hooks/` to `.agents/hooks/`. Point `.claude/settings.json`
at the new path, and add a `.codex/hooks.json` that registers the same
four hooks.

- **`draft_target.py` learns Codex's payload.** `tool_name ==
  "apply_patch"`, with the patch in `tool_input.command`. The target
  paths are read from the patch's own file headers, and **every** draft a
  patch touches is gated, since one patch can add, update or move several
  files. An unparseable patch that mentions `content/drafts/` must fail
  *closed* (block and say why), not open. That is a deliberate reversal
  of today's "malformed stdin fails open", scoped to the one case where
  failing open is the silently inert gate. The header grammar must be
  taken from Codex's own `apply_patch` specification, not from examples,
  and pinned by a test built from a recorded real payload.
- **`envelope.py`** emits exactly the field the host named by `--harness`
  consumes. `docs/HOOKS.md` already records that emitting several
  delivers the payload twice on Claude Code.
- **The repo root** still comes from the hook's own location on disk,
  which works from `.agents/hooks/` unchanged.
- **`hook_launchers.py`** reads `.codex/hooks.json` as well as
  `.claude/settings.json`, and reports a dead launcher in either. That
  keeps the named layer-1 exception ("may read the launcher config,
  never a payload") intact.
- **Measure before relying on it.** Repeat `docs/HOOKS.md`'s six trials
  on Codex and add the results to that document's table. The trials are:
  payload delivery on write, delivery on edit, mixed stdout, a blocking
  hook co-firing with an advisory one, a dead launcher, and a
  mid-session config change. Two Codex facts also need measuring:
  whether a project's hooks need a trust step before they run, which
  would be another way for the gate to go silently inert, and which
  working directory and environment a hook is launched with.

### 4. One canonical set of skills, in neutral wording

- **Location.** `.agents/skills/` becomes the source. Codex reads it
  natively. `.claude/skills/` becomes a generated copy, written by
  `chitragupta init` and checked by a drift test, not a symlink, since
  symlinks do not survive the release zip or a Windows checkout. **To
  confirm:** whether Claude Code also reads `.agents/skills/`. If it
  does, the copy is unnecessary, and keeping it would load every skill
  twice.
- **Vocabulary.** Replace harness tool names with capabilities:
  - "`Edit`, never `Write`" becomes "`draft_edit`, never `draft_write`",
    which works because step 2 made those the canonical tools;
  - TodoWrite becomes "keep a checklist";
  - "multiple Agent calls in one message" becomes "dispatch in parallel
    where the harness can; otherwise use the `quick` depth's inline
    path", which `deep-research` already has.

  `AGENTS.md` gains a short glossary mapping each capability to each
  harness's tool.
- **Subagents.** `.claude/agents/*.md` stays for Claude Code. Codex gets
  generated `.codex/agents/*.toml` from the same source. Continue has
  none, so `deep-research` and the review panel fall back to inline.
- **Test churn.** About 27 test files pin `.claude/` paths or skill text.
  The `test_skill_*_step.py` scans move to the canonical path, and one
  new test asserts every generated copy matches its source. Move them in
  this step's PR, not piecemeal.

### 5. `chitragupta init --agent claude|codex|continue`

`init.COPY_VERBATIM` scaffolds `.claude` unconditionally today. It
becomes the neutral core (`.agents/`, `AGENTS.md`, `SOUL.md`, `docs/`,
`assets/`, `config.toml`) plus each named harness's launcher and
generated files. `--agent` repeats, so one project can serve more than
one harness. **Decision needed:** the default. Recommended: `claude`,
since it keeps every existing invocation's output unchanged and so makes
this a MINOR bump rather than MAJOR.

Knock-on effects to sweep in the same PR:

- the release archive's denylist (`scripts/release.py`'s
  `EXCLUDE_TOP_LEVEL`), since `.agents/`, `.codex/` and `.continue/` all
  ship unless excluded;
- the test-enforced command table in `docs/PACKAGING.md`, together with
  its leaf-command count;
- the review-aid docs, if any aid is touched;
- `init.py`'s `DELIBERATE_DIFFERENCES`;
- `chitragupta doctor`, which must report per harness.

### 6. Continue

Scaffold `.continue/`:

- an MCP server entry for `chitragupta mcp`;
- **one short rule** pointing at `AGENTS.md`. Rules are appended to
  *every* request's system message, so the nine skills must never be
  rules; that would be roughly 50,000 words on every call;
- one slash-command prompt per skill, generated from the canonical
  source.

**To confirm:** whether Continue now reads `AGENTS.md` natively (its
issue 6716 requested it). If it does, the rule is unnecessary. Continue's
row in the supported-harness table carries whatever step 2's
built-in-tool question found.

### 7. Local models

The harnesses already reach local models: Codex through
`--oss`/`--local-provider` with Ollama or LM Studio, and Continue through
an Ollama model block. What does not fit is the size of chitragupta's
instructions:

- **The context budget.** A skill is roughly 7,000-10,000 tokens.
  `AGENTS.md` and `SOUL.md` add roughly 5,500. Retrieval output comes on
  top. Split each skill into a **core** (the procedure, the gate, the
  dossier contract) and **reference** files loaded on demand. The
  `deep-research/reference.md` split is the precedent.
  **Decision needed:** the core's size bound, and whether a test enforces
  it. Recommended: measure first. Draft one core, run it on the sample
  project with a 32k-context model, and set the bound from what actually
  fit.
- **Tool calling.** Both harnesses require a model with function
  calling. Some models advertise it and still fail Continue's agent-mode
  check. `docs/LOCAL-MODELS.md` names the models actually run end to end,
  with the date and harness version. It makes no general quality claim.
- **Exact-span edits.** `agenda-reviser` and `draft-reviser` depend on
  `old_string` matching exactly. `draft_edit` should return the nearest
  near-match on a miss, so a weaker model can correct itself rather than
  fall back to rewriting the whole file.
- **Record the runs.** For each non-Claude harness, draft one survey end
  to end over `docs/examples/sample-project/` on a local model, and
  record where the gate fired and what it caught. That run is the issue's
  last success criterion, and the evidence that steps 1-6 hold.

## ❓ Open questions this plan does not settle

1. **Whether render refusing is MAJOR** (step 1). It is recommended here,
   but it is the maintainer's call under `DEVELOPER-AGENTS.md`'s
   versioning section.
2. **Whether either harness can hide its built-in write tools** (step 2).
   This decides whether Continue gets two hard stops or one.
3. **Whether Claude Code reads `.agents/skills/`** (step 4). This decides
   whether a generated `.claude/skills/` exists at all.
4. **How Codex's hook trust model treats a freshly scaffolded project**
   (step 3). If project hooks wait for approval, the session preflight
   has to say so on the first run, or the gate is inert until someone
   notices.
5. **Where `CLAUDE.md`'s router goes for a non-Claude harness.** Codex
   reads `AGENTS.md`, whose pointer back to the developer route already
   exists, so the router may need no Codex equivalent. That should be
   confirmed on a real Codex session before the docs say it.
