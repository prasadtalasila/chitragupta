"use strict";

const childProcess = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

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

function launch(BROWSER, userDataDir) {
  const proc = childProcess.spawn(BROWSER, [
    "--headless",
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

  function abandon(error) {
    gone = gone || error;
    for (const waiting of pending.values()) { waiting.reject(error); }
    pending.clear();
  }
  proc.on("error", abandon);
  proc.stdio[3].on("error", abandon);
  proc.stdio[4].on("error", abandon);
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
    await send("Emulation.setDeviceMetricsOverride", {
      width: 1280, height: 900, deviceScaleFactor: 1, mobile: false,
    });
  }

  async function close() {
    if (!proc.pid || proc.exitCode !== null || proc.signalCode !== null) { return; }
    const exited = new Promise((resolve) => { proc.once("exit", resolve); });
    await send("Browser.close", {}, false).catch(() => proc.kill("SIGKILL"));
    await exited;
  }

  return { send, attach, close, on: (listener) => listeners.push(listener) };
}

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
