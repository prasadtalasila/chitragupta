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

**`opencode_apply_patch_args.json` is recorded**: the `args` OpenCode
1.18.33 passed to the plugin for an `apply_patch` call. Its envelope ends
without a newline after `*** End Patch`. **`opencode_write_args.json` and
`opencode_edit_args.json`** hold the key sets measured the same way
(`filePath`, `content`; `filePath`, `oldString`, `newString`), with
illustrative values.

In every fixture the patch *content* was scripted by the stand-in model
that drove the harness; the payload's shape is what the harness produced.

The patch text follows OpenAI's `apply_patch` (V4A) envelope, whose Lark
grammar Codex sends with its tool definition. Re-record the fixtures when
a harness's payload shape may have changed, following Task 0 of
[plans/812-harness-neutral-core.md](../../../plans/812-harness-neutral-core.md),
and record the date, harness version and capture method here.
