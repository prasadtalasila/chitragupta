// chitragupta's citation gate on OpenCode (#900, docs/HARNESS.md). The
// arguments are remembered before the call, because the after-call hook
// is not documented to receive them, and the check runs after the write,
// on the file on disk, as the hooks do on Claude Code and Codex.
import { WRITERS, afterWrite } from "../chitragupta/gate.js";

export const ChitraguptaGate = async () => {
  const pending = new Map();
  return {
    "tool.execute.before": async (input, output) => {
      if (WRITERS.has(input.tool)) pending.set(input.callID, output.args);
    },
    "tool.execute.after": async (input, output) => {
      if (!pending.has(input.callID)) return;
      const args = pending.get(input.callID);
      pending.delete(input.callID);
      afterWrite(input.tool, args, output);
    },
  };
};
