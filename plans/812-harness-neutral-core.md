# 🔌 Claude Code, Codex and OpenCode on one shared core (#812, #900)

Status: **design, unbuilt.** Written 2026-09-26, rescoped 2026-09-29.
Implements [issue 812](https://github.com/prasadtalasila/chitragupta/issues/812)
(Claude Code and Codex) and
[issue 900](https://github.com/prasadtalasila/chitragupta/issues/900)
(OpenCode). Continue is split out to
[issue 901](https://github.com/prasadtalasila/chitragupta/issues/901) and
is not planned here. Record here which PR closed each step, and what
changed along the way.

**Written for** whoever builds it, one step at a time. It assumes
[docs/HOOKS.md](../docs/HOOKS.md)'s three-layer rule (checks, adapters,
launcher) and [docs/CLI.md](../docs/CLI.md)'s tier-1 promise: the gate
chain imports nothing outside the standard library.
[DEVELOPER-AGENTS.md](../DEVELOPER-AGENTS.md) covers the cycle around
each step.

## ❗ The problem

The citekey gate is enforced only by a Claude Code `PostToolUse` hook,
`.claude/hooks/citation_gate_hook.py`. Today it blocks after a draft is
written, and the model has to fix the key before it moves on.

- **Codex** has compatible hooks, but edits go through `apply_patch`,
  whose payload carries the patch in `tool_input.command` with no
  `file_path`. The matcher never fires, and if it did,
  `draft_target._file_path` returns `""` and the hook fails open.
- **OpenCode** does not read `.claude/settings.json` at all.
- **Render** refuses an unknown key only for `--format md`. Measured on
  2026-09-26: `--format docx` prints pandoc's `[WARNING] Citeproc:
  citation ... not found` and writes the document anyway. pdf and tex
  take the same `pandoc --citeproc` path.

## 🧱 The solution: two layers over one gate

Both layers call `chitragupta/citation_gate.py`. No gate logic is copied
into a skill, hook or plugin.

1. **Self-check (asked).** Each skill ends with "run `scripts/check
   <draft>`, fix every finding, then finish". The model checks its own
   output before it is done, so a well-behaved model never trips layer 2.
2. **Mandatory check (enforced).** A thin per-harness wrapper runs the
   gate on every write to a draft. The model cannot skip it.

`draft render` refusing an unknown key in every format is the last
check behind both.

| Harness | Self-check | Mandatory check | Last check |
| --- | --- | --- | --- |
| Claude Code | skill script | `PostToolUse` hook, after the write | render |
| Codex | skill script | `PostToolUse` hook on `apply_patch`, after the write | render |
| OpenCode | skill script | plugin `tool.execute.before`, before the write | render |

A write through the shell (`echo ... >> draft.md`) passes layer 2 on
every harness, as it does on Claude Code today. Render catches it. The
docs say so.

## 🪜 The steps, in order

Each step is one PR, can be released on its own, and leaves every
existing Claude Code project working.

### 1. Render refuses an unknown key in every format

- `draft render` runs `citation_gate.check_text` on the text before
  pandoc runs, for md, docx, pdf and tex, and refuses on `FAIL` with the
  gate's citekey-naming report.
- A citation-free draft still renders with no ledger (HOOKS.md measured
  the gate exits 0 there).
- No escape-hatch flag: the gate must not be individually disableable.
- **Version: MINOR.** Writing a document with an unknown key was never
  intended behaviour, so this is treated as closing a gap, not breaking
  an invocation.
- This is the existing gate invoked at a second point, not a new check
  promoted into a gate.

### 2. Skills in the standard Agent Skills layout, one copy

- Each skill becomes `SKILL.md` plus `scripts/`, `references/` and
  `assets/`.
  - `scripts/check` is a thin call to `python -m chitragupta.draft gate`
    and `style`.
  - `references/` holds the detail loaded on demand, so `SKILL.md` stays
    small enough for a local model's context.
    `deep-research/reference.md` is the precedent.
- Tool names become capabilities: "edit the draft", not "`Edit`, never
  `Write`"; "keep a checklist", not TodoWrite; parallel dispatch where
  the harness can, otherwise `deep-research`'s inline path.
- Each skill ends with the self-check instruction.
- Skills live in one folder read by all three harnesses. If one does not
  read it, `init` copies the skills there and a test fails when the copy
  drifts. Not a symlink: symlinks do not survive the release zip or a
  Windows checkout.
- Subagents: `.claude/agents/*.md` stays; Codex gets
  `.codex/agents/*.toml` generated from the same source, with a drift
  test.
- The ~27 test files that pin `.claude/skills/` or skill text move in
  this PR, not piecemeal.

### 3. Codex enforcement

- Move the hook wrappers from `.claude/hooks/` to a shared `hooks/`
  folder; point `.claude/settings.json` at it. The repo root still comes
  from each hook's own location on disk.
- `draft_target.py` learns the `apply_patch` payload: read every target
  path from the patch's file headers and gate **every** draft the patch
  adds, updates or moves. A patch that mentions `content/drafts/` but
  cannot be parsed is **blocked**, not let through. The header grammar
  comes from Codex's own `apply_patch` specification, pinned by a test
  built from a recorded real payload.
- Each wrapper emits only the output field its host consumes
  (`--harness <name>`). HOOKS.md records that emitting several delivers
  the payload twice on Claude Code.
- Add `.codex/hooks.json` registering the same hooks.
- `hook_launchers.py` reads `.codex/hooks.json` as well as
  `.claude/settings.json`, and `doctor` reports a dead launcher in
  either.
- Measure on a real Codex session and add to HOOKS.md's table:
  HOOKS.md's six trials, plus whether Codex asks the user to trust
  project hooks before they run (if so, the session preflight must say
  so, or the gate is inert until someone notices), and which working
  directory and environment a hook is launched with.

### 4. OpenCode enforcement (#900)

- `draft gate --stdin <path>`: the existing gate reading the proposed
  text from stdin. A new input mode, not a new check.
- A project plugin, `.opencode/plugins/chitragupta/index.ts`:
  - hooks `tool.execute.before` for OpenCode's file-writing tools;
  - for a target inside `content/drafts/` with a `.md` or `.tex` suffix,
    computes the file's text after the write and pipes it to
    `draft gate --stdin`;
  - on `FAIL`, throws with the gate's report, so the write does not
    happen and the model sees which key failed on which line;
  - if the gate cannot run for a draft path, throws too;
  - holds no citekey logic of its own.
- Measure on a real OpenCode session: the argument shapes each file tool
  passes, that a throw blocks the write and its message reaches the
  model, and how the plugin finds the interpreter.

### 5. The MCP server (#900; reused by #901)

`chitragupta mcp`, a stdlib stdio MCP server, registered in
`opencode.json`. On OpenCode it is a convenience; the plugin is the
enforcement. #901 later makes it Continue's enforcement.

- `draft_write(path, text)`: gate `text`, refuse on `FAIL`, else write.
- `draft_edit(path, old, new)`: exact-span replacement; gate the result,
  refuse on `FAIL`, else write.
- A refusal names each bad key and its line.
- Speaks only `initialize`, `tools/list` and `tools/call`, at a pinned
  protocol version, tested against a recorded handshake.

Security, limited to what the new server adds:

- **Writes only drafts.** The root is fixed at startup from `--root`,
  never from a tool argument. A path is accepted only if it resolves
  inside `content/drafts/`, has a `.md` or `.tex` suffix, and contains
  no `..` or symlink.
- **Reads only `content/`.**
- **Cannot change the ledger.** Opened read-only (`mode=ro`); no sync or
  import tool.
- **Local only.** stdio; no network port, no subprocess started from a
  tool argument.
- **Loads only the installed package.** Launched through the installed
  `chitragupta mcp` command, so a planted `chitragupta/` cannot be
  imported in its place (#822, as `safe_path.py` does for the hooks).
- **Standard library only.**

### 6. `chitragupta init --agent claude|codex|opencode`

- Scaffolds the shared core (skills, `AGENTS.md`, `SOUL.md`, `docs/`,
  `assets/`, `config.toml`) plus each named harness's wrapper. The flag
  repeats; the default is `claude`, so existing invocations are
  unchanged.
- `doctor` reports a missing or dead wrapper per harness.
- Sweep in the same PR: `scripts/release.py`'s `EXCLUDE_TOP_LEVEL`,
  `docs/PACKAGING.md`'s command table and leaf-command count, and
  `init.py`'s `DELIBERATE_DIFFERENCES`.

### 7. Local-model runs

On Codex and OpenCode, draft one survey end to end with a local model
over `docs/examples/sample-project/`. Record in `docs/LOCAL-MODELS.md`
the date, model and harness version, and where each layer fired. No
general quality claim.

## ❓ To confirm before the step that needs it

1. Which skills folder each of the three harnesses reads (step 2).
2. Codex's `apply_patch` grammar and hook trust behaviour (step 3).
3. OpenCode's `tool.execute.before` argument shapes, and that a throw
   blocks the write (step 4).
4. Where `CLAUDE.md`'s router goes for Codex and OpenCode. Both read
   `AGENTS.md`, whose pointer to the developer route already exists;
   confirm on a real session before the docs say it.
