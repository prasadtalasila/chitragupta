/* C1/C2 for assets/webapp/, the JS mirror of tests/test_code_standards_scan.py
   -- see scripts/webapp_code_standards.js's own docstring for the two
   places this deliberately does not match the Python scan (an unnamed
   top-level module wrapper is not a C1 candidate; C2 counts real scanned
   lines, not `wc -l`), and code-standards-register.toml's header for why
   the register lives there rather than in a file of its own. */
"use strict";

const test = require("node:test");
const assert = require("node:assert");

const scan = require("../../scripts/webapp_code_standards.js");

function newOffenders(found, registered) {
  return Object.keys(found)
    .filter((name) => !(name in registered))
    .sort();
}

function fixedOffenders(found, registered) {
  return Object.keys(registered)
    .filter((name) => !(name in found))
    .sort();
}

test("no function in assets/webapp/ over C1 that the register does not already hold", () => {
  const [c1Register] = scan.register();
  const found = scan.longFunctions();
  const added = newOffenders(found, c1Register);
  assert.deepStrictEqual(
    added,
    [],
    `Functions over the ${scan.MAX_STATEMENTS}-statement limit that are not in ` +
      `code-standards-register.toml's c1js table:\n` +
      added.map((name) => `  ${name} -- ${found[name]} statements`).join("\n"),
  );
});

test("no module in assets/webapp/ over C2 that the register does not already hold", () => {
  const [, c2Register] = scan.register();
  const found = scan.longFiles();
  const added = newOffenders(found, c2Register);
  assert.deepStrictEqual(
    added,
    [],
    `Modules over the ${scan.MAX_CODE_LINES}-code-line limit that are not in ` +
      `code-standards-register.toml's c2js table:\n` +
      added.map((name) => `  ${name} -- ${found[name]} code lines`).join("\n"),
  );
});

test("the c1js register holds no entry that is already fixed", () => {
  const [c1Register] = scan.register();
  const fixed = fixedOffenders(scan.longFunctions(), c1Register);
  assert.deepStrictEqual(
    fixed,
    [],
    `These are now within the limit -- delete them from c1js:\n${fixed.map((n) => `  ${n}`).join("\n")}`,
  );
});

test("the c2js register holds no entry that is already fixed", () => {
  const [, c2Register] = scan.register();
  const fixed = fixedOffenders(scan.longFiles(), c2Register);
  assert.deepStrictEqual(
    fixed,
    [],
    `These are now within the limit -- delete them from c2js:\n${fixed.map((n) => `  ${n}`).join("\n")}`,
  );
});

test("every c1js/c2js register entry names a path that still exists", () => {
  const path = require("node:path");
  const fs = require("node:fs");
  const [c1Register, c2Register] = scan.register();
  const paths = new Set([
    ...Object.keys(c1Register).map((name) => name.split("::")[0]),
    ...Object.keys(c2Register),
  ]);
  const missing = [...paths].filter((p) => !fs.existsSync(path.join(scan.REPO_ROOT, p))).sort();
  assert.deepStrictEqual(missing, [], `register entries for files that no longer exist: ${missing}`);
});

test("every registered offender records its current count", () => {
  const [c1Register, c2Register] = scan.register();
  const recorded = { ...c1Register, ...c2Register };
  const counts = { ...scan.longFunctions(), ...scan.longFiles() };
  assert.deepStrictEqual(
    Object.keys(recorded).sort(),
    Object.keys(counts).sort(),
    "the c1js/c2js tables and the live scan disagree about which entries exist",
  );
  const drifted = Object.entries(recorded).filter(([name, was]) => was !== counts[name]);
  assert.deepStrictEqual(
    drifted,
    [],
    "register entries whose recorded count is stale (name, recorded, actual): " + JSON.stringify(drifted),
  );
});

test("the scan reaches assets/webapp/ and skips vendor/", () => {
  // Non-vacuity, the same reason test_the_scan_reaches_the_source_tree
  // exists on the Python side: a glob that silently matched nothing
  // would make every assertion above pass for the wrong reason.
  const scanned = new Set([...Object.keys(scan.longFiles()), ...Object.keys(scan.longFunctions())]);
  assert.ok([...scanned].every((p) => p.startsWith("assets/webapp/")));
  assert.ok(!Object.keys(scan.longFiles()).some((p) => p.includes("/vendor/")));
  assert.ok(!Object.keys(scan.longFunctions()).some((p) => p.includes("/vendor/")));
  // A file over C2 today, named directly rather than only implied by a
  // count -- if this ever comes back under 250 lines, this line (and the
  // matching code-standards-register.toml entry) needs deleting together.
  assert.ok(Object.keys(scan.longFiles()).includes("assets/webapp/app.js"));
});
