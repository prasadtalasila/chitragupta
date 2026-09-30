// chitragupta's citation gate on OpenCode (#900, docs/HARNESS.md). The
// check runs after the write, on the file on disk, as the hooks do on
// Claude Code and Codex. `tool.execute.after` receives the call's own
// `args` (measured on OpenCode 1.18.33), so nothing is remembered between
// the two hooks.
import { WRITERS, afterWrite } from "../chitragupta/gate.js";

export const ChitraguptaGate = async () => ({
  "tool.execute.after": async (input, output) => {
    if (WRITERS.has(input.tool)) afterWrite(input.tool, input.args, output);
  },
});
