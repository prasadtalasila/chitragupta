"use strict";

const { describe, it, before, after } = require("node:test");
const assert = require("node:assert");
const childProcess = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const headless = require("./headless.js");

const ROOT = path.join(__dirname, "..", "..");
const [BROWSER, skip] = headless.findBrowser();

function startServer(project) {
  fs.copyFileSync(path.join(ROOT, "config.toml.example"), path.join(project, "config.toml"));
  const server = childProcess.spawn("python3", ["-m", "chitragupta", "webapp", "--no-browser"], {
    cwd: project,
    env: { ...process.env, PYTHONPATH: ROOT, CHITRAGUPTA_PROJECT: project },
    stdio: ["ignore", "pipe", "inherit"],
  });
  const url = new Promise((resolve, reject) => {
    let seen = "";
    server.stdout.setEncoding("utf8");
    server.stdout.on("data", (chunk) => {
      seen += chunk;
      const found = seen.match(/http:\/\/127\.0\.0\.1:\d+\/#token=\S+/);
      if (found) { resolve(found[0]); }
    });
    server.on("exit", (code) => reject(new Error("the server exited (" + code + ")")));
  });
  return { server, url: headless.withDeadline(url, "the server's URL") };
}

describe("the webapp workbench in a headless browser", { skip }, () => {
  let scratch;
  let server;
  let browser;
  let url;
  const problems = [];

  async function evaluate(expression) {
    const { result } = await browser.send("Runtime.evaluate", { expression, returnByValue: true });
    return result.value;
  }

  async function statusText() {
    const settleBy = Date.now() + headless.DEADLINE_MS;
    let text = "";
    while (Date.now() < settleBy) {
      text = await evaluate("document.getElementById('status').textContent");
      if (text && !text.includes("Connecting")) { return text; }
      await new Promise((resolve) => setTimeout(resolve, 50));
    }
    return text;
  }

  async function load(target, how) {
    const loaded = new Promise((resolve) => browser.on((m) => m === "Page.loadEventFired" && resolve()));
    await how(target);
    await headless.withDeadline(loaded, "the page to load");
  }

  before(async () => {
    scratch = fs.mkdtempSync(path.join(os.tmpdir(), "workbench-smoke-"));
    const project = path.join(scratch, "a-project");
    fs.mkdirSync(project);
    ({ server, url } = startServer(project));
    url = await url;
    browser = headless.launch(BROWSER, path.join(scratch, "profile"));
    browser.on((method, params) => problems.push(...headless.problemsOf(method, params)));
    await browser.attach();
    await load(url, (target) => browser.send("Page.navigate", { url: target }));
  });

  after(async () => {
    if (browser) { await browser.close(); }
    if (server) { server.kill("SIGTERM"); }
    fs.rmSync(scratch, { recursive: true, force: true });
  });

  it("shows the project the server was started in", async () => {
    assert.match(await statusText(), /Project: a-project/);
  });

  it("leaves no token in the address bar and sets no cookie", async () => {
    assert.ok(!(await evaluate("location.href")).includes("token"));
    assert.strictEqual(await evaluate("document.cookie"), "");
    assert.ok(await evaluate("sessionStorage.getItem('chitragupta.token') !== null"));
  });

  it("still works after a reload, from sessionStorage", async () => {
    await load(null, () => browser.send("Page.reload"));
    assert.match(await statusText(), /Project: a-project/);
  });

  it("reports nothing wrong: no exception, console error or CSP refusal", () => {
    assert.deepStrictEqual(problems, []);
  });
});
