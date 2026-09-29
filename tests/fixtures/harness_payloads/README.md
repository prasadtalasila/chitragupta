# Harness payload fixtures

Tool payloads the hook adapters read on Codex and OpenCode (#812, #900).

**Status: constructed, not recorded.** Written 2026-09-29 from the
documented shapes, because no Codex or OpenCode session was available in
the environment that built the adapters:

- Codex: `PostToolUse` payloads carry `tool_name: "apply_patch"` and the
  patch text in `tool_input.command`, plus `cwd`
  (<https://developers.openai.com/codex/hooks>).
- OpenCode: the `args` a `tool.execute.before` hook sees -- `filePath`
  and `content` for `write`; `filePath`, `oldString` and `newString` for
  `edit`; `patchText` for `apply_patch`
  (<https://opencode.ai/docs/tools/>).

The patch text follows OpenAI's `apply_patch` (V4A) envelope. The paths
are illustrative, and `/project` stands for the project root.

Replace each file with a payload recorded from a real session, following
Task 0 of [plans/812-harness-neutral-core.md](../../../plans/812-harness-neutral-core.md).
When you do, record here the date, the harness version and how each
payload was captured, and change the status above. Until then, the
adapters' tests prove the code matches the documentation, not the
harness.
