// The OpenCode side of chitragupta's hooks (#900): turn a file tool's
// arguments into the payload .claude/hooks/*.py already read, run the
// hook, and hand its verdict back. No citekey logic lives here -- which
// writes are drafts, the size bound, the timeout and the fail-closed
// rules are the Python hooks', shared with Claude Code and Codex
// (docs/HARNESS.md). Kept apart from ../plugins/ so that directory's one
// file exports exactly one plugin.
import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const HOOKS = join(ROOT, ".claude", "hooks");
// The same bound .claude/settings.json gives each hook.
const HOOK_TIMEOUT_MS = 30_000;
// OpenCode's file-writing tools. `apply_patch` carries the patch text,
// every other one a `filePath` (https://opencode.ai/docs/tools/).
export const WRITERS = new Set(["write", "edit", "multiedit", "apply_patch"]);
const DRAFT_MARKERS = ["content/drafts/", "content\\drafts\\"];

export function payloadFor(tool, args, root = ROOT) {
  if (tool === "apply_patch") {
    // Codex's shape: the hooks read patch text from tool_input.command.
    return { tool_name: tool, tool_input: { command: String(args?.patchText ?? "") }, cwd: root };
  }
  return { tool_name: tool, tool_input: { file_path: String(args?.filePath ?? "") }, cwd: root };
}

export function touchesDrafts(payload) {
  const input = payload.tool_input;
  const text = String(input.command ?? input.file_path ?? "");
  return DRAFT_MARKERS.some((marker) => text.includes(marker));
}

export function runHook(script, payload, spawn = spawnSync) {
  // `python`, as every launcher here names it (docs/HOOKS.md's launcher contract).
  const result = spawn("python", [join(HOOKS, script)], {
    input: JSON.stringify(payload),
    encoding: "utf8",
    timeout: HOOK_TIMEOUT_MS,
  });
  if (result.error || result.status !== 0) {
    return { failed: true, detail: String(result.error ?? result.stderr ?? "") };
  }
  const out = (result.stdout ?? "").trim();
  if (!out) return {};
  try {
    return JSON.parse(out);
  } catch {
    return { failed: true, detail: out.slice(0, 500) };
  }
}

// A throw fails the tool call, and OpenCode hands the model the error's
// message as the call's result (measured on OpenCode 1.18.33 for write,
// edit and apply_patch). The output is rewritten too, so the refusal still
// leads the result if a later OpenCode swallows a hook's error.
export function deliver(output, message) {
  output.output = `${message}\n\n${output.output ?? ""}`;
  throw new Error(message);
}

// The whole after-write check for one call, split from the plugin so a
// test can drive it without OpenCode.
export function afterWrite(tool, args, output, run = runHook) {
  const payload = payloadFor(tool, args);
  const gate = run("citation_gate_hook.py", payload);
  if (gate.failed) {
    if (touchesDrafts(payload)) {
      deliver(
        output,
        "chitragupta: the citation gate could not run, so this draft was not " +
          `checked and the write is refused until it can. ${gate.detail}`,
      );
    }
    return;
  }
  if (gate.decision === "block") deliver(output, gate.reason);
  const note = run("style_check_hook.py", payload).hookSpecificOutput?.additionalContext;
  if (note) output.output = `${output.output ?? ""}\n\n${note}`;
}
