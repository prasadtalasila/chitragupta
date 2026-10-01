/* assets/webapp/index.html: the DOM-free modules, loaded the way the
   page loads them.

   Every other file in this directory reaches a module through
   `require`, which takes the CommonJS half of its wrapper. The page
   takes the other half: classic scripts, in index.html's order, each
   attaching its API to one shared `CHITRAGUPTA_APP` global and reading
   its dependencies back off it. Nothing else runs that half, so a
   module that attached under the wrong name, or a script order that put
   panel.js ahead of graph.js, would pass every other test and break
   only in a browser.

   It is also what makes CI's coverage threshold mean "every DOM-free
   module": node's coverage report only lists files a test loaded, so a
   new module with no test of its own would otherwise be absent from the
   report rather than failing it. Reading the list from index.html means
   a new script is loaded here, and measured, the moment the page
   ships it. */
"use strict";

const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const { DATA } = require("./fixture.js");

const WEBAPP = path.join(__dirname, "..", "..", "assets", "webapp");

// The payload, the vendored library, and the DOM wiring: everything the
// page loads that cannot run without a browser, or is not this
// project's code. The wiring is last in the page, after every module it
// reads from; the order test below holds it there.
const NOT_LOADED = new Set(["data.js", "vendor/cytoscape.min.js"]);
const DOM_WIRING = ["search.js", "pickers.js", "app.js"];

function pageScripts() {
  const html = fs.readFileSync(path.join(WEBAPP, "index.html"), "utf8");
  return [...html.matchAll(/<script src="\.\/([^"]+)"><\/script>/g)].map((m) => m[1]);
}

function domFreeScripts() {
  return pageScripts().filter((name) => !NOT_LOADED.has(name) && !DOM_WIRING.includes(name));
}

function loadAsThePageDoes() {
  const context = vm.createContext({});
  context.self = context;
  for (const name of domFreeScripts()) {
    const file = path.join(WEBAPP, name);
    new vm.Script(fs.readFileSync(file, "utf8"), { filename: file }).runInContext(context);
  }
  return context.CHITRAGUPTA_APP;
}

// Every top-level script in the directory is one of the three kinds
// above. Without this, a tag the regex above does not match (a `defer`,
// a missing `./`) or a module the page never names would drop out of
// the load below, and of the coverage report, with every other
// assertion here still passing.
test("every script in assets/webapp/ is loaded here, or named as not loadable", () => {
  const onDisk = fs.readdirSync(WEBAPP).filter((name) => name.endsWith(".js")).sort();
  const accounted = [...domFreeScripts(), ...DOM_WIRING].sort();
  assert.deepEqual(onDisk, accounted);
});

// The other way the bar can measure nothing: node scores 0 of 0 lines
// as 100%, so an include glob in ci.yml that drifted off this directory
// would pass with no file in the report. Read it from the step itself.
test("CI's coverage glob matches every module this file loads", () => {
  const ci = fs.readFileSync(path.join(__dirname, "..", "..", ".github", "workflows", "ci.yml"), "utf8");
  const glob = ci.match(/--test-coverage-include="([^"]+)"/);
  assert.ok(glob, "ci.yml's webapp step no longer passes --test-coverage-include");
  const pattern = new RegExp("^" + glob[1].replace(/[.]/g, "\\.").replace(/\*/g, "[^/]*") + "$");
  const unmatched = domFreeScripts().filter((name) => !pattern.test("assets/webapp/" + name));
  assert.deepEqual(unmatched, []);
});

test("the page loads the DOM wiring last, after every module it reads from", () => {
  const scripts = pageScripts();
  assert.deepEqual(scripts.slice(-DOM_WIRING.length), DOM_WIRING);
  assert.ok(domFreeScripts().length > 0);
});

test("every DOM-free module attaches its whole API to the shared global", () => {
  const app = loadAsThePageDoes();
  for (const name of domFreeScripts()) {
    const exported = Object.keys(require(path.join(WEBAPP, name)));
    const missing = exported.filter((key) => !(key in app));
    assert.deepEqual(missing, [], `${name} exports these under node but not on CHITRAGUPTA_APP`);
  }
});

test("a module reads its dependencies off the global, not off require", () => {
  // panel.js's topicHtml reaches into graph.js for the origin colours
  // and labels; the same output from both halves of the wrapper is the
  // evidence it found them.
  const panel = require(path.join(WEBAPP, "panel.js"));
  const topic = DATA.topics[0];
  assert.equal(loadAsThePageDoes().topicHtml(DATA, topic), panel.topicHtml(DATA, topic));
});
