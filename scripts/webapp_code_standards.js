#!/usr/bin/env node
/**
 * C1 and C2 for `assets/webapp/`, the JavaScript mirror of
 * `scripts/code_standards.py`. Same two rules (docs/CODE-STANDARDS.md), same
 * ratchet (`code-standards-register.toml`'s `c1js`/`c2js` tables, added
 * alongside `c1`/`c2` rather than in a second root-level file -- see that
 * file's own header for why it lives at the root and why counts are real
 * values). `tests/webapp/code_standards.test.js` is what enforces this and
 * is still the authority, exactly as `tests/test_code_standards_scan.py` is
 * for the Python side; this module is only the scan the test and a hand run
 * share.
 *
 * CommonJS, not `.mjs`: `tests/webapp/*.test.js` already `require()`s its
 * sibling modules, and a plain `.js` file with no package.json `"type"`
 * field is CommonJS by Node's own default -- matching that is what let this
 * land with no change to how the existing tests load anything.
 *
 * **Why a second scanner instead of one that reads both languages.** Python
 * has no JS parser and Node has no Python one, and each side already reads
 * its own register format with its own stdlib (`tomllib` here, a hand-rolled
 * reader below -- Node has nothing like `tomllib`, and pulling in an npm
 * TOML package for one shared data file was not worth the dependency).
 *
 * **What does not carry over from the Python side, and why:**
 *
 * - **A function is reported only when it has a real, derivable name.**
 *   Every file in `assets/webapp/` is a UMD module: an anonymous IIFE at the
 *   top of the file holds the *entire* module body as its own statements
 *   (`(function () { ...the whole file... })()`, or the two-argument
 *   `root`/`factory` form). That top-level anonymous function is the JS
 *   analogue of Python module-level code, which C1 never counts either --
 *   reporting it would flag every one of these files for holding more than
 *   25 top-level statements, which is a fact about the module, not about a
 *   function anyone reads as one unit. A *named* function is always
 *   reported however deeply it sits inside that wrapper (`families.js`'s
 *   `computePath` is the one real offender today), and an anonymous
 *   function nested inside a *named* one is reported too, keyed by its
 *   line for uniqueness -- only a function with no named ancestor at all is
 *   exempt. The gap this leaves: a genuinely long anonymous callback sitting
 *   directly at a file's top level, outside any module wrapper, would not
 *   be caught. None of the six files here have one.
 * - **C2's line count is real, scanned code, not `wc -l`.** Blank lines and
 *   whole-line comments are excluded the same way C2 excludes them, which
 *   matters more here than on the Python side: these files open with long
 *   `/* ... *&#47;` rationale banners in the same style CODE-STANDARDS.md
 *   requires of the Python side, and `wc -l` would count every line of
 *   them. A block comment line only counts as "whole-line" when nothing
 *   but the comment shares that line -- a trailing `// why` after real code
 *   still counts as code, matching C2's own rule.
 *
 * Usage:
 *   node scripts/webapp_code_standards.js [--json]
 */

"use strict";

const fs = require("node:fs");
const path = require("node:path");
const acorn = require("acorn");

const REPO_ROOT = path.resolve(__dirname, "..");

const MAX_STATEMENTS = 25;
const MAX_CODE_LINES = 250;

// `vendor/` ships a third-party library (cytoscape.min.js), not code this
// project wrote -- same reasoning `bench/` gets for staying out of the
// Python scan, see CODE-STANDARDS.md.
const ROOTS = ["assets/webapp"];
const EXCLUDED_DIRS = new Set(["vendor"]);

const REGISTER_PATH = path.join(REPO_ROOT, "code-standards-register.toml");

const FUNCTION_TYPES = new Set(["FunctionDeclaration", "FunctionExpression", "ArrowFunctionExpression"]);

// The ESTree node types acorn emits that this scan treats as one statement.
// `BlockStatement`/`Program` are deliberately absent: they are containers,
// not something a body "does", so counting them would charge every `if`
// and `function` twice, once for itself and once for the block it opens.
const STATEMENT_TYPES = new Set([
  "ExpressionStatement",
  "VariableDeclaration",
  "IfStatement",
  "ForStatement",
  "ForInStatement",
  "ForOfStatement",
  "WhileStatement",
  "DoWhileStatement",
  "SwitchStatement",
  "ReturnStatement",
  "ThrowStatement",
  "TryStatement",
  "BreakStatement",
  "ContinueStatement",
  "LabeledStatement",
  "DebuggerStatement",
  "FunctionDeclaration",
  "ClassDeclaration",
]);

function isNode(value) {
  return Boolean(value) && typeof value === "object" && typeof value.type === "string";
}

/** Every child that is itself an ESTree node, generic over the node's
 * shape -- the JS analogue of `ast.iter_child_nodes`. */
function* childNodes(node) {
  for (const key of Object.keys(node)) {
    if (key === "loc" || key === "range" || key === "start" || key === "end") continue;
    const value = node[key];
    if (Array.isArray(value)) {
      for (const item of value) if (isNode(item)) yield item;
    } else if (isNode(value)) {
      yield value;
    }
  }
}

/** Statements in a function body, not descending into a nested function or
 * class -- mirrors `scripts/code_standards.py`'s `statement_count`. The
 * nested definition itself still counts as one statement of the parent
 * (declaring it is something the parent does); its own body is counted
 * separately, when `collectDefinitions` reaches it in its own right. */
function statementCount(fnNode) {
  let count = 0;
  const pending = [...childNodes(fnNode)];
  while (pending.length) {
    const child = pending.pop();
    if (STATEMENT_TYPES.has(child.type)) count++;
    if (FUNCTION_TYPES.has(child.type) || child.type === "ClassDeclaration") continue;
    pending.push(...childNodes(child));
  }
  return count;
}

function keyName(key) {
  if (key.type === "Identifier") return key.name;
  if (key.type === "Literal") return String(key.value);
  return "<computed>";
}

function memberName(member) {
  const objectPart = member.object.type === "Identifier" ? member.object.name : "<expr>";
  return `${objectPart}.${keyName(member.property)}`;
}

/** The name a function is known by, from the node holding it -- a named
 * declaration or expression, a variable it initialises, an object property,
 * or an assignment's left-hand side. Falls back to a line-numbered
 * placeholder, unique within a file, when none of those apply (an IIFE
 * argument, a bare callback). */
function nameHint(parent, child) {
  if (child.id && child.id.name) return child.id.name;
  if (parent.type === "VariableDeclarator" && parent.id.type === "Identifier") return parent.id.name;
  if (parent.type === "Property") return keyName(parent.key);
  if (parent.type === "AssignmentExpression" && parent.left.type === "MemberExpression") {
    return memberName(parent.left);
  }
  if (parent.type === "AssignmentExpression" && parent.left.type === "Identifier") return parent.left.name;
  return `<anonymous@${child.loc.start.line}>`;
}

function collectDefinitions(node, prefix, out) {
  for (const child of childNodes(node)) {
    if (FUNCTION_TYPES.has(child.type)) {
      const name = prefix + nameHint(node, child);
      out.push([name, statementCount(child)]);
      collectDefinitions(child, `${name}.`, out);
    } else {
      collectDefinitions(child, prefix, out);
    }
  }
}

/** Every function in `source` as `[qualifiedName, statementCount]`, in the
 * same shape `scripts/code_standards.py`'s `functions()` returns. */
function functions(source) {
  const ast = acorn.parse(source, { ecmaVersion: "latest", sourceType: "script", locations: true });
  const out = [];
  collectDefinitions(ast, "", out);
  return out;
}

/** Physical lines that are neither blank nor a whole-line comment -- see
 * the module docstring for why this scans real comment spans rather than
 * treating every `wc -l` line as code. */
function codeLines(source) {
  const comments = [];
  acorn.parse(source, {
    ecmaVersion: "latest",
    sourceType: "script",
    locations: true,
    onComment: comments,
  });
  const lines = source.split("\n");
  const wholeCommentLines = new Set();
  for (const comment of comments) {
    if (comment.type === "Line") {
      if (lines[comment.loc.start.line - 1].slice(0, comment.loc.start.column).trim() === "") {
        wholeCommentLines.add(comment.loc.start.line);
      }
      continue;
    }
    for (let lineNo = comment.loc.start.line; lineNo <= comment.loc.end.line; lineNo++) {
      const line = lines[lineNo - 1];
      const before = lineNo === comment.loc.start.line ? line.slice(0, comment.loc.start.column) : "";
      const after = lineNo === comment.loc.end.line ? line.slice(comment.loc.end.column) : "";
      if (before.trim() === "" && after.trim() === "") wholeCommentLines.add(lineNo);
    }
  }
  let count = 0;
  lines.forEach((line, idx) => {
    if (line.trim() !== "" && !wholeCommentLines.has(idx + 1)) count++;
  });
  return count;
}

function jsFiles(roots) {
  const found = [];
  for (const root of roots) {
    const walk = (dir) => {
      for (const entry of fs.readdirSync(path.join(REPO_ROOT, dir), { withFileTypes: true })) {
        if (EXCLUDED_DIRS.has(entry.name)) continue;
        const rel = path.join(dir, entry.name);
        if (entry.isDirectory()) walk(rel);
        else if (entry.name.endsWith(".js")) found.push(rel);
      }
    };
    walk(root);
  }
  return found.sort();
}

/** `[qualifiedName, count]` pairs whose last path segment is a real name --
 * see the module docstring's first bullet for why an unnamed top-level
 * wrapper is excluded here rather than reported and then registered. */
function namedOverLimit(entries) {
  return entries.filter(([name, count]) => {
    const last = name.split(".").pop();
    return count > MAX_STATEMENTS && !last.startsWith("<anonymous@");
  });
}

/** `{qualifiedName: statementCount}` for every named function over C1, across `roots`. */
function longFunctions(roots) {
  const found = {};
  for (const relPath of jsFiles(roots || ROOTS)) {
    const source = fs.readFileSync(path.join(REPO_ROOT, relPath), "utf8");
    for (const [name, count] of namedOverLimit(functions(source))) {
      found[`${relPath}::${name}`] = count;
    }
  }
  return found;
}

/** `{path: codeLineCount}` for every module over C2, across `roots`. */
function longFiles(roots) {
  const found = {};
  for (const relPath of jsFiles(roots || ROOTS)) {
    const source = fs.readFileSync(path.join(REPO_ROOT, relPath), "utf8");
    const count = codeLines(source);
    if (count > MAX_CODE_LINES) found[relPath] = count;
  }
  return found;
}

/** A minimal reader for this repository's own TOML register, not a general
 * TOML parser: array-of-tables sections (`[[c1js]]`), each holding a
 * `name = "..."` string and one more `key = integer` pair, blank lines and
 * `#`-led comments ignored. That is the entire grammar
 * `code-standards-register.toml` uses. */
function readRegisterTable(text, table) {
  const entries = [];
  let current = null;
  for (const rawLine of text.split("\n")) {
    const line = rawLine.trim();
    if (line === "" || line.startsWith("#")) continue;
    if (line === `[[${table}]]`) {
      current = {};
      entries.push(current);
      continue;
    }
    if (line.startsWith("[[")) {
      current = null;
      continue;
    }
    if (current === null) continue;
    const match = line.match(/^(\w+)\s*=\s*(.+)$/);
    if (!match) continue;
    const [, key, rawValue] = match;
    const quoted = rawValue.match(/^"(.*)"$/);
    current[key] = quoted ? quoted[1] : Number(rawValue);
  }
  return entries;
}

/** `[{name: statements}, {name: codeLines}]`, the JS-scoped `c1js`/`c2js`
 * tables in the same register the Python scan reads its own `c1`/`c2`
 * tables from. */
function register() {
  const text = fs.readFileSync(REGISTER_PATH, "utf8");
  const c1 = Object.fromEntries(readRegisterTable(text, "c1js").map((e) => [e.name, e.statements]));
  const c2 = Object.fromEntries(readRegisterTable(text, "c2js").map((e) => [e.name, e.code_lines]));
  return [c1, c2];
}

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

/** Every crossing not already in the register, plus every register entry
 * that has come back under its threshold -- the ratchet's two failure
 * directions, exactly as `tests/test_code_standards_scan.py` checks them. */
function findings() {
  const [c1Register, c2Register] = register();
  const c1 = longFunctions();
  const c2 = longFiles();
  return {
    newFunctions: newOffenders(c1, c1Register).map((name) => [name, c1[name]]),
    fixedFunctions: fixedOffenders(c1, c1Register),
    newFiles: newOffenders(c2, c2Register).map((name) => [name, c2[name]]),
    fixedFiles: fixedOffenders(c2, c2Register),
  };
}

function formatFindings(found) {
  const lines = [];
  for (const [name, count] of found.newFunctions) {
    lines.push(`C1  ${name}  ${count} statements (limit ${MAX_STATEMENTS})`);
  }
  for (const [name, count] of found.newFiles) {
    lines.push(`C2  ${name}  ${count} code lines (limit ${MAX_CODE_LINES})`);
  }
  for (const name of found.fixedFunctions) lines.push(`C1 fixed, delist: ${name}`);
  for (const name of found.fixedFiles) lines.push(`C2 fixed, delist: ${name}`);
  return lines.length ? lines.join("\n") : "no findings: nothing over C1 or C2 that the register does not hold.";
}

module.exports = {
  REPO_ROOT,
  MAX_STATEMENTS,
  MAX_CODE_LINES,
  ROOTS,
  REGISTER_PATH,
  statementCount,
  functions,
  codeLines,
  longFunctions,
  longFiles,
  register,
  findings,
  formatFindings,
};

if (require.main === module) {
  const found = findings();
  if (process.argv.includes("--json")) {
    console.log(JSON.stringify(found, null, 2));
  } else {
    console.log(formatFindings(found));
  }
}
