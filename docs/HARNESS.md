# 🔌 Harnesses: one citekey gate on Claude Code, Codex and OpenCode

Status: **building, from 6.126.0.** Written 2026-09-29. Implements
[issue 812](https://github.com/prasadtalasila/chitragupta/issues/812)
(Claude Code and Codex) and
[issue 900](https://github.com/prasadtalasila/chitragupta/issues/900)
(OpenCode). Continue is split out to
[issue 901](https://github.com/prasadtalasila/chitragupta/issues/901).
The task-by-task plan is
[plans/812-harness-neutral-core.md](https://github.com/prasadtalasila/chitragupta/blob/main/plans/812-harness-neutral-core.md).

This document records why the pipeline is being made to run on more
than one agent harness, what the design session of 2026-09-26 to
2026-09-29 decided, and which designs it turned down and why. The
rejections matter as much as the decisions. Several of the rejected
designs look like the obvious fix, and each one fails the same test:
**can the model skip it?**

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
- [Designs turned down, and why](#-designs-turned-down-and-why)
- [Harness facts learned](#-harness-facts-learned)
- [Decisions a maintainer made](#-decisions-a-maintainer-made)
- [Measured, and what is still not](#-measured-and-what-is-still-not)

## 🎯 Why more than one harness

The Python package has always been harness-neutral: nothing under
`chitragupta/` calls a language model, and retrieval's embedding models
run locally. Everything above it assumed Claude Code. That shuts out
two kinds of user:

- **a researcher without a Claude Code subscription**, who drafts in
  Codex or OpenCode;
- **a researcher who keeps the corpus on their own hardware** and runs
  a local model through one of those harnesses.

The second is the harder case, because a small local model is the one
most likely to fabricate a citekey. So supporting another harness is
only worth doing if the one binding rule is exactly as strong there. A
harness where a fabricated key can slip through unnoticed is not
supported.

## ❗ The problem

Before this work, three facts made the gate Claude Code-only:

1. **The only automatic check was a Claude Code hook.**
   `.claude/hooks/citation_gate_hook.py` fires on Claude Code's
   `Write|Edit` matcher and reads `tool_input.file_path`.
2. **Codex's hook never fired on a draft.** Codex edits through
   `apply_patch`, whose payload carries the patch text in
   `tool_input.command` and no `file_path`. Even had the matcher
   matched, `draft_target` would have found no path and failed open:
   a gate that looks like it passed.
3. **Render let a fabricated key through in three formats.** Measured
   on 2026-09-26: `draft render --format md` refused a key missing from
   the ledger, but only as a side effect of building the numbered
   reference list. `--format docx` printed pandoc's citeproc warning
   and wrote the document anyway, and pdf and tex take the same path.

OpenCode read none of `.claude/settings.json`, so it had no check at
all.

## 🧱 The design: three checks over one gate

Every check calls `chitragupta/citation_gate.py`. No gate logic is
copied into a skill, a hook launcher or a plugin.

1. **Self-check (asked).** Before presenting, each skill runs
   `python -m chitragupta.draft gate` on its own draft and fixes what it
   reports. This step already existed in every skill; the work only
   made its wording harness-neutral.
2. **Mandatory check (enforced).** A thin per-harness launcher runs the
   existing hook scripts on every write to a draft. The model cannot
   skip it, and it is told to fix the key before it moves on.
3. **Last check.** `draft render` runs the gate before producing any
   format, so no draft with an unknown key becomes a document on any
   harness.

The mandatory check is the one that needed per-harness work, and it was
kept as small as possible:

- **The hooks stay in `.claude/hooks/`.** Codex's `.codex/hooks.json`
  and OpenCode's plugin both launch those same scripts. Moving them to
  a neutral folder would have churned about 28 test files and the
  coverage source for no change in behaviour.
- **The hooks learn one new payload shape**: `apply_patch` patch text.
  Codex and OpenCode use the same envelope (OpenAI's V4A grammar), so
  one parser, `.claude/hooks/patch_paths.py`, serves both. Every draft
  a patch adds, updates or moves is gated. A patch that mentions
  `content/drafts/` but whose headers cannot be read is **blocked**:
  the one deliberate exception to "malformed stdin fails open", because
  failing open there is exactly the silently inert gate HOOKS.md exists
  to prevent.
- **The OpenCode plugin is a transport.** It turns OpenCode's tool
  arguments into the payload the hooks already read, pipes it to
  `citation_gate_hook.py`, and hands the verdict back. Which writes are
  drafts, the size bound, the timeout and the fail-closed rules are the
  Python hook's, shared by all three harnesses.
- **A liveness warning covers the hook that never fires.** The gate
  hook records each draft it checked, and `draft gate` run by hand
  warns about a draft no hook has seen since it last changed. It is
  detection, never a verdict: it never changes the gate's exit code.

## 🗂 What each harness enforces

| Harness | Self-check | Mandatory check | Last check |
| --- | --- | --- | --- |
| Claude Code | the skill runs `draft gate` | `PostToolUse` hook on Write and Edit, after the write | `draft render` |
| Codex | the skill runs `draft gate` | `PostToolUse` hook on `apply_patch`, after the write, once the project's hooks are trusted | `draft render` |
| OpenCode | the skill runs `draft gate` | plugin on `tool.execute.after`, after the write | `draft render` |

**What none of them stops**: a write through the shell, such as
`echo ... >> content/drafts/x.md`. No harness's file-tool hook sees it,
on Claude Code today as on the other two. `draft render` refuses the
draft, and the skill's own `draft gate` run warns that no hook checked
it. A person copying text straight out of the raw draft file is outside
every check; nothing can see that.

## 🚫 Designs turned down, and why

**An MCP server with gated `draft_write` / `draft_edit` tools, as the
enforcement.** This was the issue's first proposal. The tools would run
the gate before writing, so a bad key would never reach disk through
them. But a pre-write gate enforces only if the model has no other way
to write, and on every harness it has one: its built-in edit tool, or
failing that the shell. On Codex, Claude Code and OpenCode the hook or
plugin already covers the built-in tools, so the server would be a
second write path to maintain and secure for no added guarantee. It
moved to #901, where Continue has no hooks at all and the server,
with Continue's built-in write tools excluded, *is* the enforcement.
Its security choices are recorded there: it writes only
`content/drafts/`, reads only `content/`, opens the ledger read-only
with no sync tool, speaks stdio only, and is launched through the
installed `chitragupta mcp` command so a planted `chitragupta/` cannot
be imported in its place.

**The gate in a script each skill runs, instead of a hook.** The
Agent Skills layout lets a skill carry `scripts/`, and every harness
here reads that layout. But the model decides whether to run a skill's
script. That is the "asked, not enforced" posture ARCHITECTURE.md rules
out, and the model likeliest to skip the step is also the likeliest to
fabricate. Kept as the self-check, never as the only check. No
`scripts/` folder was added either: the self-check is already one CLI
call, and a script in each of nine skills would be nine copies of it.

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

**One copy of each skill per harness.** Nine skills of 2,500-7,700
words each, copied three ways, would drift, and a copy that drifts on
the gate step is a fabrication path. There is one copy, in
`.claude/skills/`.

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
  `.claude/skills/` and `.agents/skills/` for compatibility.** So the
  existing skills load on OpenCode unchanged. Whether a skill found in
  two of those folders loads twice is not yet known.
  ([OpenCode skills](https://opencode.ai/docs/it/skills/))
- **OpenCode plugins** hook `tool.execute.before` and
  `tool.execute.after`. Its `edit` tool takes `filePath`, `oldString`,
  `newString` and `replaceAll`; its `apply_patch` tool takes
  `patchText`, whose paths are relative to the project root.
  ([OpenCode plugins](https://opencode.ai/docs/en/plugins/),
  [OpenCode tools](https://opencode.ai/docs/tools/))
- **Continue** reads Agent Skills and supports MCP, but has no hooks.
  Its CLI can mark a built-in tool `exclude`.
  ([Continue tool permissions](https://docs.continue.dev/cli/tool-permissions))
- **The Agent Skills specification** limits `description` to 1,024
  characters and allows only `name`, `description`, `license`,
  `compatibility`, `metadata` and `allowed-tools` in the frontmatter.
  Four skills' descriptions were over the limit, and every skill
  carried an unread `tags:` key.
  ([agentskills.io](https://agentskills.io))

## ⚖ Decisions a maintainer made

- **Render refusing in every format ships as MINOR** (2026-09-29).
  DEVELOPER-AGENTS.md calls a change MAJOR when it requires an existing
  user to change how they invoke the pipeline, and a docx render that
  succeeded with a warning now fails. The call was that writing a
  document with an unknown key was never intended behaviour, so this
  closes a gap rather than breaking an invocation. There is no flag to
  restore the old behaviour.
- **Continue is out of scope for now**, split to #901, together with
  the MCP server.
- **OpenCode is built alongside Codex**, not after it, since it needs
  no MCP server and reuses the same hook scripts.

## 🔬 Measured, and what is still not

**Measured on 2026-09-29**, with Codex 0.159.0 and OpenCode 1.18.33
installed in a scratch copy of a project scaffolded by
`chitragupta init`. No real model was used: a small local stand-in
answered each harness's model requests with scripted tool calls, so each
harness ran its own real tools, hooks and plugins, and the stand-in
logged exactly what the harness handed back to the model after each tool
call.

**Codex**, driven end to end:

- The gate hook fires on `apply_patch`, and **the model receives the
  gate's refusal in place of the tool's output**, naming the bad key and
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
  Codex was started, and Codex sets no project-directory variable. The
  first launcher, a relative `python .claude/hooks/<x>.py`, therefore
  failed to start from any subfolder, and the draft landed ungated. Each
  launcher line now walks up to the folder holding `.codex/hooks.json`
  and runs the hook from there, under `python -P`; blocking from
  `content/` was then measured.
- **Codex reads project skills only from `.agents/skills/`**, never
  `.claude/skills/`, so `init --agent codex` copies them there. It reads
  `AGENTS.md` natively.
- A skill with a `tags:` key loads. A `description` over 1,024
  characters loads but is cut at 1,024 in what the model sees, so the
  end of an over-long description -- often its "use X instead" routing
  -- would be lost.

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
  its input -- so the plugin needs only the after-hook.
- **Skill discovery.** It reads `.opencode/skills/`, `.claude/skills/`
  and `.agents/skills/` (and the user's global `~/.claude/skills/`),
  and loads one copy per skill name -- **chosen arbitrarily** when a name
  is in more than one folder: four runs picked different mixes, and
  `.opencode/skills/` does not take precedence. So the copies in those
  folders must be identical, which `init` guarantees by copying one
  tree. Only the environment variable
  `OPENCODE_DISABLE_EXTERNAL_SKILLS=1` restricts it to `.opencode/skills/`,
  and a project cannot set it.
- A skill with `tags:` loads, and a long description is kept whole.
- **One environment trap, not OpenCode's or this repository's.** In the
  container these were measured in, OpenCode's runtime never reaped a
  `git` child process -- it sat `<defunct>` -- and the agent loop waited on
  it forever: the title request went out and the turn itself never did.
  With `git` off `PATH` everything ran. A harness that stalls before its
  first real model call in a sandbox is worth checking for a zombie
  child before anything else.

**Still not measured:**

- whether a Codex `PostToolUse` advisory note (the style hook's) reaches
  the model -- the probe draft had no prose finding to report;
- local-model runs on either harness.
