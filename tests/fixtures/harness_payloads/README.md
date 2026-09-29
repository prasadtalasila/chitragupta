# Harness payload fixtures

Tool payloads the hook adapters read on Codex and OpenCode (#812, #900).

**The two Codex fixtures are recorded**: the `PostToolUse` payloads
Codex 0.159.0 sent on 2026-09-29, with the project path replaced by
`/project` and the home directory by `/home/user`.

- `codex_apply_patch.json`: from a session started in the project's
  `content/` folder, so its patch path is relative to that `cwd` -- why
  `draft_target` resolves a patch path against the payload's `cwd`.
- `codex_apply_patch_multi.json`: one patch adding two drafts, from the
  project root.

**The OpenCode fixtures are constructed**, because no live OpenCode tool
call could be driven in the environment that built the adapters. They
hold the `args` OpenCode's tools take -- `filePath` and `content` for
`write`; `filePath`, `oldString` and `newString` for `edit`; `patchText`
for `apply_patch` (<https://opencode.ai/docs/tools/>, and its bundled
source).

The patch text follows OpenAI's `apply_patch` (V4A) envelope, whose Lark
grammar Codex sends with its tool definition. Replace a constructed file
with a recorded one when a live session is available, following Task 0
of [plans/812-harness-neutral-core.md](../../../plans/812-harness-neutral-core.md),
and record the date, harness version and capture method here.
