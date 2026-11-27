/* Headless Chrome over the DevTools protocol, shared by the two browser
   smoke tests: the exported topic-graph page (browser_smoke.test.js)
   and the webapp workbench (workbench_smoke.test.js). Not a test file:
   node --test's glob is *.test.js. */
"use strict";

const childProcess = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

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
  if (process.env.GITHUB_ACTIONS) {
    return [null, "headless Chrome is not run in GitHub Actions -- run this file locally"];
  }
  if (process.env.CHROME_PATH) { return [process.env.CHROME_PATH, false]; }
  for (const name of CANDIDATES) {
    const found = onPath(name);
    if (found) { return [found, false]; }
  }
  return [null, "no Chrome or Chromium found -- install one, or set CHROME_PATH to its binary"];
}

const DEADLINE_MS = 30000;

function withDeadline(promise, what) {
  let timer;
  const expired = new Promise((resolve, reject) => {
    timer = setTimeout(() => reject(new Error("timed out waiting for " + what)), DEADLINE_MS);
  });
  return Promise.race([promise, expired]).finally(() => clearTimeout(timer));
}

/* The DevTools protocol over --remote-debugging-pipe: JSON messages, each
   ended by a NUL byte, written to the browser's fd 3 and read from its
   fd 4. One session, attached to one page, is all this file needs. */
function launch(BROWSER, userDataDir) {
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
  proc.stdio[4].on("error", abandon);
  // A decoder, not chunk.toString(): a read can end inside a multi-byte
  // character, and the panel text the cases match on has an em dash.
  proc.stdio[4].setEncoding("utf8");
  proc.on("exit", (code) => abandon(new Error("the browser exited (" + code + ")")));

  proc.stdio[4].on("data", (chunk) => {
    const parts = (buffered + chunk).split("\0");
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
    return withDeadline(new Promise((resolve, reject) => pending.set(id, { method, resolve, reject })), method);
  }

  async function attach(initScript) {
    const { targetId } = await send("Target.createTarget", { url: "about:blank" }, false);
    ({ sessionId } = await send("Target.attachToTarget", { targetId, flatten: true }, false));
    await send("Runtime.enable");
    await send("Log.enable");
    await send("Page.enable");
    if (initScript) {
      await send("Page.addScriptToEvaluateOnNewDocument", { source: initScript });
    }
    // Wide enough that the panel sits beside the canvas, as on a laptop.
    await send("Emulation.setDeviceMetricsOverride", {
      width: 1280, height: 900, deviceScaleFactor: 1, mobile: false,
    });
  }

  async function close() {
    // No pid is a browser that never started, which will never exit.
    if (!proc.pid || proc.exitCode !== null || proc.signalCode !== null) { return; }
    const exited = new Promise((resolve) => { proc.once("exit", resolve); });
    // Asked first; killed if it did not answer, since one that has gone
    // silent will not exit on its own.
    await send("Browser.close", {}, false).catch(() => proc.kill("SIGKILL"));
    await exited;
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

module.exports = { findBrowser, launch, problemsOf, withDeadline, DEADLINE_MS };
