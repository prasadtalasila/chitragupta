/* assets/webapp/workbench/: the page loads only its own files, by src,
   and none of them builds markup from strings (#1262).

   Loading every script index.html names except the DOM wiring (main.js)
   is also what puts each module in node's coverage report -- the same
   reason tests/webapp/browser_load.test.js exists for the topic graph. */
"use strict";

const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const DIR = path.join(__dirname, "..", "..", "assets", "webapp", "workbench");
const HTML = fs.readFileSync(path.join(DIR, "index.html"), "utf8");
const DOM_WIRING = "main.js";

function scripts() {
  return [...HTML.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/g)];
}

test("every script is external, same-directory, with no inline body", () => {
  const found = scripts();
  assert.ok(found.length > 0);
  for (const [, attrs, body] of found) {
    assert.match(attrs, /src="\.\/[a-z]+\.js"/);
    assert.strictEqual(body.trim(), "");
  }
});

test("the DOM wiring is the last script, after every module it reads", () => {
  const names = scripts().map(([, attrs]) => attrs.match(/src="\.\/([a-z]+\.js)"/)[1]);
  assert.strictEqual(names[names.length - 1], DOM_WIRING);
});

function modules() {
  return scripts()
    .map(([, attrs]) => attrs.match(/src="\.\/([a-z]+\.js)"/)[1])
    .filter((name) => name !== DOM_WIRING);
}

test("every module the page names loads under node", () => {
  for (const name of modules()) {
    assert.strictEqual(typeof require(path.join(DIR, name)), "object");
  }
});

test("in a browser the modules share one global, which main.js reads", () => {
  const sandbox = { URLSearchParams };
  sandbox.self = sandbox;
  vm.createContext(sandbox);
  for (const name of modules()) {
    const file = path.join(DIR, name);
    new vm.Script(fs.readFileSync(file, "utf8"), { filename: file }).runInContext(sandbox);
  }
  for (const fn of ["takeToken", "authHeaders", "renderStatus", "renderNoToken", "renderRefused"]) {
    assert.strictEqual(typeof sandbox.CHITRAGUPTA_WORKBENCH[fn], "function", fn);
  }
});

test("no inline event handler or style attribute in the page", () => {
  assert.doesNotMatch(HTML, /\son[a-z]+\s*=/i);
  assert.doesNotMatch(HTML, /\sstyle\s*=/i);
  assert.doesNotMatch(HTML, /<style\b/i);
});

test("no workbench script builds markup from strings or evaluates code", () => {
  const banned = /\.innerHTML|\.outerHTML|insertAdjacentHTML|document\.write|\beval\(|new Function\(/;
  for (const name of fs.readdirSync(DIR).filter((n) => n.endsWith(".js"))) {
    assert.doesNotMatch(fs.readFileSync(path.join(DIR, name), "utf8"), banned, name);
  }
});

test("every script in workbench/ is a module the page loads, or the wiring", () => {
  const onDisk = fs.readdirSync(DIR).filter((n) => n.endsWith(".js")).sort();
  assert.deepStrictEqual(onDisk, [...modules(), DOM_WIRING].sort());
});

test("CI and the local check measure the workbench modules", () => {
  const root = path.join(__dirname, "..", "..");
  for (const file of [".github/workflows/ci.yml", "scripts/check_local.sh"]) {
    const text = fs.readFileSync(path.join(root, file), "utf8");
    assert.ok(text.includes('--test-coverage-include="assets/webapp/workbench/*.js"'), file);
  }
});
