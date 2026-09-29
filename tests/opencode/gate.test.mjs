// node --test for .opencode/chitragupta/gate.js (#900).
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  WRITERS,
  afterWrite,
  deliver,
  payloadFor,
  runHook,
  touchesDrafts,
} from "../../.opencode/chitragupta/gate.js";

test("write and edit pass the file path, as Claude Code's hooks read it", () => {
  const p = payloadFor("edit", { filePath: "/p/content/drafts/a.md", oldString: "x" }, "/p");
  assert.deepEqual(p, {
    tool_name: "edit",
    tool_input: { file_path: "/p/content/drafts/a.md" },
    cwd: "/p",
  });
});

test("apply_patch passes the patch text where Codex's hooks read it", () => {
  const p = payloadFor("apply_patch", { patchText: "*** Begin Patch\n*** End Patch\n" }, "/p");
  assert.equal(p.tool_input.command, "*** Begin Patch\n*** End Patch\n");
});

test("missing arguments become empty strings, never undefined", () => {
  assert.equal(payloadFor("write", undefined, "/p").tool_input.file_path, "");
  assert.equal(payloadFor("apply_patch", {}, "/p").tool_input.command, "");
});

test("only writes that mention a draft count as touching drafts", () => {
  assert.equal(touchesDrafts(payloadFor("write", { filePath: "content/drafts/a.md" })), true);
  assert.equal(touchesDrafts(payloadFor("write", { filePath: "content\\drafts\\a.md" })), true);
  assert.equal(touchesDrafts(payloadFor("write", { filePath: "README.md" })), false);
  const patch = "*** Begin Patch\n*** Add File: content/drafts/a.md\n*** End Patch\n";
  assert.equal(touchesDrafts(payloadFor("apply_patch", { patchText: patch })), true);
});

test("a hook that cannot start is a failure, not a pass", () => {
  const spawn = () => ({ error: new Error("ENOENT"), status: null, stdout: "", stderr: "" });
  assert.equal(runHook("citation_gate_hook.py", {}, spawn).failed, true);
});

test("a hook that exits non-zero is a failure", () => {
  const spawn = () => ({ status: 1, stdout: "", stderr: "Traceback" });
  assert.deepEqual(runHook("citation_gate_hook.py", {}, spawn), { failed: true, detail: "Traceback" });
});

test("a hook that prints nothing passes", () => {
  const spawn = () => ({ status: 0, stdout: "", stderr: "" });
  assert.deepEqual(runHook("citation_gate_hook.py", {}, spawn), {});
});

test("a hook that prints non-JSON is a failure", () => {
  const spawn = () => ({ status: 0, stdout: "Traceback ...", stderr: "" });
  assert.equal(runHook("citation_gate_hook.py", {}, spawn).failed, true);
});

test("a hook's JSON comes back parsed", () => {
  const spawn = () => ({ status: 0, stdout: '{"decision": "block", "reason": "r"}\n' });
  assert.deepEqual(runHook("citation_gate_hook.py", {}, spawn), { decision: "block", reason: "r" });
});

test("delivering a refusal reaches both the tool output and a thrown error", () => {
  const output = { output: "wrote it" };
  assert.throws(() => deliver(output, "refused"), /refused/);
  assert.match(output.output, /^refused\n\nwrote it$/);
});

test("the documented OpenCode writers are all watched", () => {
  for (const tool of ["write", "edit", "apply_patch"]) assert.ok(WRITERS.has(tool));
});

const draft = { filePath: "/p/content/drafts/a.md" };
const hooks = (gate, style = {}) => (script) =>
  script === "citation_gate_hook.py" ? gate : style;

test("a blocking gate refuses the write with the gate's reason", () => {
  const output = { output: "" };
  assert.throws(
    () => afterWrite("write", draft, output, hooks({ decision: "block", reason: "@x not found" })),
    /@x not found/,
  );
});

test("a gate that cannot run refuses a draft write", () => {
  assert.throws(
    () => afterWrite("write", draft, { output: "" }, hooks({ failed: true, detail: "ENOENT" })),
    /could not run/,
  );
});

test("a gate that cannot run leaves any other write alone", () => {
  const output = { output: "ok" };
  afterWrite("write", { filePath: "/p/README.md" }, output, hooks({ failed: true, detail: "x" }));
  assert.equal(output.output, "ok");
});

test("a passing gate appends the style report and does not refuse", () => {
  const style = { hookSpecificOutput: { additionalContext: "a prose finding" } };
  const output = { output: "ok" };
  afterWrite("write", draft, output, hooks({}, style));
  assert.equal(output.output, "ok\n\na prose finding");
});

test("a passing gate with no style findings changes nothing", () => {
  const output = { output: "ok" };
  afterWrite("edit", draft, output, hooks({}, {}));
  assert.equal(output.output, "ok");
});
