/* The exported topic-graph page, opened in a real headless browser and
   clicked through (#933).

   Every other file in this directory runs the DOM-free modules under
   node. The DOM wiring -- search.js, pickers.js, canvas.js,
   sidepanel.js and app.js: cytoscape construction, the gesture
   handlers, the panel's writers, Esc and the latch -- runs nowhere but
   a browser, so a break in it shipped silently until someone opened
   the page (#931's guards were all in that code). This file is the one
   place that code runs before a reader does.

   The page under test is what a reader would open: the fixture payload
   goes through the real exporter (`_app.write_app_dir`, the half of
   `corpus discover --app` after the corpus is read), so a file missing
   from its copy list fails here too, and it opens from file://, under
   index.html's own Content-Security-Policy.

   The browser is driven over the DevTools protocol on a pipe rather than
   through Playwright or puppeteer: nothing to install, and no second
   copy of Chrome downloaded behind the one CI's runner already has.
   Clicks and keys are dispatched as real input events at the element's
   on-screen position, not `emit("tap")`, so cytoscape's own event
   handling is under test as well.

   Off CI, with no browser found, every case skips with the instruction,
   the way code_standards.test.js does for acorn. On CI a missing browser
   fails instead, because there the runner image is meant to have one. */
"use strict";

const { describe, it, before, after, beforeEach, afterEach } = require("node:test");
const assert = require("node:assert");
const childProcess = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const { DATA } = require("./fixture.js");

const ROOT = path.join(__dirname, "..", "..");

// CHROME_PATH first, so a host whose browser is not on PATH (puppeteer's
// cache, a chrome-headless-shell) can still run this; then the names the
// Linux packages and GitHub's ubuntu runner image install under.
const CANDIDATES = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"];

function onPath(name) {
  for (const dir of (process.env.PATH || "").split(path.delimiter)) {
    const file = path.join(dir, name);
    if (dir && fs.existsSync(file)) { return file; }
  }
  return null;
}

function findBrowser() {
  if (process.env.CHROME_PATH) { return [process.env.CHROME_PATH, false]; }
  for (const name of CANDIDATES) {
    const found = onPath(name);
    if (found) { return [found, false]; }
  }
  const reason = "no Chrome or Chromium found -- install one, or set CHROME_PATH to its binary";
  if (process.env.CI) { throw new Error(reason); }
  return [null, reason];
}

const [BROWSER, skip] = findBrowser();

// The fixture through the real exporter. `-c` with the repository root as
// the working directory imports this checkout's chitragupta, which reads
// config.toml at import -- the same one-line setup the rest of the suite
// needs (DEVELOPER-AGENTS.md, "Finish the checkout").
function exportPage(dir) {
  const code = "import json, sys\n" +
    "from chitragupta.discover import _app\n" +
    "_app.write_app_dir(sys.argv[1], json.load(sys.stdin))\n";
  const run = childProcess.spawnSync("python3", ["-c", code, dir], {
    cwd: ROOT, input: JSON.stringify(DATA), encoding: "utf8",
  });
  assert.equal(run.status, 0, "the exporter failed:\n" + (run.error || run.stderr));
  return pathToFileURL(path.join(dir, "index.html")).href;
}

/* Installed ahead of every script on the page. Cytoscape skips an
   element whose id is already on the canvas without a word, warnings on
   or off -- which is how #931's collisions between a generated id and a
   topic label went unseen -- so the page cannot report it by itself. This
   wraps each instance's `add` and turns a dropped element into a console
   error, which the check below then fails on. It catches the
   `globalThis.cytoscape = ...` assignment the vendored bundle makes, so
   the page's own scripts run unmodified. */
const DROPPED_ELEMENTS = `(() => {
  let wrapped;
  Object.defineProperty(globalThis, "cytoscape", {
    configurable: true,
    get() { return wrapped; },
    set(factory) {
      wrapped = Object.assign(function (...args) {
        const cy = factory.apply(this, args);
        const add = cy.add;
        cy.add = function (elements) {
          const added = add.apply(this, arguments);
          if (Array.isArray(elements) && added.length !== elements.length) {
            console.error("cytoscape dropped " + (elements.length - added.length) +
              " of " + elements.length + " elements: a duplicate or invalid id");
          }
          return added;
        };
        return cy;
      }, factory);
    },
  });
})();`;

/* The DevTools protocol over --remote-debugging-pipe: JSON messages, each
   ended by a NUL byte, written to the browser's fd 3 and read from its
   fd 4. One session, attached to one page, is all this file needs. */
function launch(userDataDir) {
  const proc = childProcess.spawn(BROWSER, [
    "--headless",
    // CI's runner and this project's container both refuse the sandbox's
    // user namespace, and the page is a local file this test wrote.
    "--no-sandbox",
    "--remote-debugging-pipe",
    "--no-first-run",
    "--no-default-browser-check",
    "--user-data-dir=" + userDataDir,
    "about:blank",
  ], { stdio: ["ignore", "ignore", "ignore", "pipe", "pipe"] });
  const pending = new Map();
  const listeners = [];
  let nextId = 0;
  let buffered = "";
  let sessionId;
  let gone = null;

  // A browser that died, or a CHROME_PATH that names nothing runnable,
  // fails whatever was waiting on it, and whatever is sent after, instead
  // of hanging the run.
  function abandon(error) {
    gone = gone || error;
    for (const waiting of pending.values()) { waiting.reject(error); }
    pending.clear();
  }
  proc.on("error", abandon);
  proc.stdio[3].on("error", abandon);
  proc.on("exit", (code) => abandon(new Error("the browser exited (" + code + ")")));

  proc.stdio[4].on("data", (chunk) => {
    const parts = (buffered + chunk.toString("utf8")).split("\0");
    buffered = parts.pop();
    for (const raw of parts) {
      const message = JSON.parse(raw);
      const waiting = pending.get(message.id);
      if (waiting) {
        pending.delete(message.id);
        if (message.error) {
          waiting.reject(new Error(waiting.method + ": " + message.error.message));
        } else {
          waiting.resolve(message.result);
        }
      } else if (message.method) {
        listeners.forEach((listener) => listener(message.method, message.params));
      }
    }
  });

  function send(method, params, onSession = true) {
    if (gone) { return Promise.reject(gone); }
    const id = ++nextId;
    const message = { id, method, params: params || {} };
    if (onSession) { message.sessionId = sessionId; }
    proc.stdio[3].write(JSON.stringify(message) + "\0");
    return new Promise((resolve, reject) => pending.set(id, { method, resolve, reject }));
  }

  async function attach() {
    const { targetId } = await send("Target.createTarget", { url: "about:blank" }, false);
    ({ sessionId } = await send("Target.attachToTarget", { targetId, flatten: true }, false));
    await send("Runtime.enable");
    await send("Log.enable");
    await send("Page.enable");
    await send("Page.addScriptToEvaluateOnNewDocument", { source: DROPPED_ELEMENTS });
    // Wide enough that the panel sits beside the canvas, as on a laptop.
    await send("Emulation.setDeviceMetricsOverride", {
      width: 1280, height: 900, deviceScaleFactor: 1, mobile: false,
    });
  }

  async function close() {
    await send("Browser.close", {}, false).catch(() => {});
    // No pid is a browser that never started, which will never exit.
    if (proc.pid && proc.exitCode === null && proc.signalCode === null) {
      await new Promise((resolve) => { proc.once("exit", resolve); });
    }
  }

  return { send, attach, close, on: (listener) => listeners.push(listener) };
}

/* Anything the page says went wrong: an uncaught exception, a console
   error or warning (DROPPED_ELEMENTS above reports through one), and
   the browser's own log, which is where a Content-Security-Policy
   refusal and a missing file under file:// are reported. */
function problemsOf(method, params) {
  if (method === "Runtime.exceptionThrown") {
    const details = params.exceptionDetails;
    return [(details.exception && details.exception.description) || details.text];
  }
  if (method === "Runtime.consoleAPICalled" && ["error", "warning", "assert"].includes(params.type)) {
    return [params.type + ": " + params.args.map((arg) => arg.value || arg.description).join(" ")];
  }
  if (method === "Log.entryAdded" && ["error", "warning"].includes(params.entry.level)) {
    return [params.entry.level + ": " + params.entry.text + (params.entry.url ? " (" + params.entry.url + ")" : "")];
  }
  return [];
}

describe("the exported topic-graph page in a headless browser", { skip }, () => {
  let scratch;
  let pageUrl;
  let browser;
  let problems = [];
  let onLoad = null;

  async function evaluate(expression) {
    const result = await browser.send("Runtime.evaluate", {
      expression, returnByValue: true, awaitPromise: true,
    });
    if (result.exceptionDetails) {
      throw new Error("evaluate threw: " + result.exceptionDetails.exception.description);
    }
    return result.result.value;
  }

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  /* Polls until `expression` is truthy. A page that has already reported
     a problem is not going to get there -- a script that failed to load
     leaves the canvas empty for good -- so that stops the wait at once,
     with the page's own report, rather than at the deadline. */
  async function until(expression, what) {
    const deadline = Date.now() + 15000;
    let last;
    while (Date.now() < deadline && !problems.length) {
      last = await evaluate(expression);
      if (last) { return last; }
      await sleep(50);
    }
    assert.deepEqual(problems, [], "the page reported errors while waiting for " + what);
    throw new Error("timed out waiting for " + what + " (last value: " + JSON.stringify(last) + ")");
  }

  // The live cytoscape instance has no public handle on the page; the
  // container element's registry entry is cytoscape's own way back to it.
  const CY = 'document.getElementById("cy")._cyreg.cy';

  /* Where an element is drawn, in page coordinates: a node's centre, an
     edge's midpoint, or the middle of a DOM element. */
  function centreOf(cyElement) {
    return evaluate(`(() => {
      const element = ${cyElement};
      const box = document.getElementById("cy").getBoundingClientRect();
      const at = element.isNode() ? element.renderedPosition() : element.renderedMidpoint();
      return { x: box.left + at.x, y: box.top + at.y };
    })()`);
  }

  async function click({ x, y }) {
    await browser.send("Input.dispatchMouseEvent", { type: "mouseMoved", x, y });
    for (const type of ["mousePressed", "mouseReleased"]) {
      await browser.send("Input.dispatchMouseEvent", { type, x, y, button: "left", clickCount: 1 });
    }
  }

  async function press(key, code, keyCode) {
    for (const type of ["keyDown", "keyUp"]) {
      await browser.send("Input.dispatchKeyEvent", { type, key, code, windowsVirtualKeyCode: keyCode });
    }
  }

  const detailText = () => evaluate('document.getElementById("detail").textContent');

  before(async () => {
    scratch = fs.mkdtempSync(path.join(os.tmpdir(), "chitragupta-smoke-"));
    pageUrl = exportPage(path.join(scratch, "app"));
    browser = launch(path.join(scratch, "profile"));
    browser.on((method, params) => {
      problems.push(...problemsOf(method, params));
      if (method === "Page.loadEventFired" && onLoad) { onLoad(); }
    });
    await browser.attach();
  });

  after(async () => {
    if (browser) { await browser.close(); }
    if (scratch) { fs.rmSync(scratch, { recursive: true, force: true }); }
  });

  /* A fresh page per case, so no case leans on what an earlier one
     clicked. The layout is animated, so a case starts only once every
     node has stopped moving: a click aimed at a node still in flight
     lands on empty canvas. */
  beforeEach(async () => {
    problems = [];
    const loaded = new Promise((resolve) => { onLoad = resolve; });
    await browser.send("Page.navigate", { url: pageUrl });
    await loaded;
    const positions = `(() => {
      const cy = document.getElementById("cy")._cyreg;
      if (!cy || !cy.cy.nodes().length) { return false; }
      return JSON.stringify(cy.cy.nodes().map((n) => [n.id(), n.renderedPosition()]));
    })()`;
    let previous = await until(positions, "the canvas to draw");
    for (;;) {
      await sleep(200);
      const now = await until(positions, "the layout to settle");
      if (now === previous) { break; }
      previous = now;
    }
  });

  // Every case also holds the page to a clean console, so a regression
  // that only logs (a dropped element, a CSP refusal) still fails.
  afterEach(() => {
    assert.deepEqual(problems, [], "the page reported errors");
  });

  it("draws one node per fixture topic, each with the topic's label as its id", async () => {
    const ids = await evaluate(`${CY}.nodes().map((n) => n.id()).sort()`);
    assert.deepEqual(ids, DATA.topics.map((topic) => topic.label).sort());
  });

  it("fills the panel with a topic's papers when its node is clicked", async () => {
    await click(await centreOf(`${CY}.$id("digital twin")`));
    const text = await detailText();
    assert.match(text, /^digital twin/);
    assert.match(text, /Papers \(2\)/);
    for (const member of DATA.topics[0].members) {
      assert.ok(text.includes(member.title), member.title + " is not in the panel");
    }
  });

  it("fills the panel with the shared papers when an edge is clicked", async () => {
    await click(await centreOf(`${CY}.edges().filter((e) => e.data("family") === "overlap")[0]`));
    const text = await detailText();
    assert.match(text, /digital twin — machine learning/);
    assert.match(text, /These topics share 1 paper/);
    assert.ok(text.includes("A digital twin"));
  });

  it("shows the help text for a data-edge naming no edge, instead of throwing", async () => {
    // #931's guard, end to end: a panel link whose index the payload does
    // not hold, activated by a real click.
    const at = await evaluate(`(() => {
      const detail = document.getElementById("detail");
      detail.innerHTML = '<a data-edge="overlap:99" id="stale">stale link</a>';
      const box = document.getElementById("stale").getBoundingClientRect();
      return { x: box.left + box.width / 2, y: box.top + box.height / 2 };
    })()`);
    await click(at);
    assert.equal(await detailText(), "");
    assert.equal(await evaluate('document.getElementById("hint").hidden'), false);
  });

  it("releases the latched focus on Esc", async () => {
    const focused = `${CY}.nodes(".focused").map((n) => n.id())`;
    await click(await centreOf(`${CY}.$id("machine learning")`));
    assert.deepEqual(await evaluate(focused), ["machine learning"]);
    await press("Escape", "Escape", 27);
    assert.deepEqual(await evaluate(focused), []);
    assert.equal(await evaluate(`${CY}.elements(".faded").length`), 0);
  });

  // The two guards above, each against the shape it exists to catch:
  // without these a clean console could equally mean nothing was listening.
  it("reports a console error, so a clean run means the page logged none", async () => {
    await evaluate('console.error("planted")');
    await sleep(100);
    assert.deepEqual(problems, ["error: planted"]);
    problems = [];
  });

  it("reports an element cytoscape dropped for reusing a topic's id", async () => {
    await evaluate(`${CY}.add([{ data: { id: "digital twin" } }]).length`);
    await sleep(100);
    assert.deepEqual(problems, ["error: cytoscape dropped 1 of 1 elements: a duplicate or invalid id"]);
    problems = [];
  });
});
