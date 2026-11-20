// The demo's browser half: drives the sample project's offline topic map
// (content/topic_map.html) in headless Chrome and writes numbered PNG
// frames that ffmpeg joins into a clip (SKILL.md, "Capture the topic map").
// With STILL_PNG it also writes the README's still: topic-1 selected, in a
// 1040x600 viewport at twice the pixel density, so the README can show it
// at close to its own size instead of shrinking a 1280px frame.
//
// Usage: node capture_topic_map.js TOPIC_MAP_HTML FRAMES_DIR [STILL_PNG]
// Needs puppeteer-core on NODE_PATH and CHROME_PATH naming a Chrome or
// Chromium binary; neither is a dependency of this repository.
"use strict";

const fs = require("fs");
const path = require("path");
const puppeteer = require("puppeteer-core");

const [html, outdir, still] = process.argv.slice(2);
if (!html || !outdir || !process.env.CHROME_PATH) {
  console.error("usage: CHROME_PATH=... node capture_topic_map.js TOPIC_MAP_HTML FRAMES_DIR");
  process.exit(2);
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function main() {
  fs.mkdirSync(outdir, { recursive: true });
  const browser = await puppeteer.launch({
    executablePath: process.env.CHROME_PATH,
    headless: true,
    args: ["--no-sandbox", "--disable-dev-shm-usage", "--force-color-profile=srgb"],
    defaultViewport: { width: 1280, height: 720 },
  });
  const page = await browser.newPage();
  await page.goto("file://" + path.resolve(html), { waitUntil: "load" });
  await sleep(300);

  let frame = 0;
  const name = (n) => path.join(outdir, `f${String(n).padStart(4, "0")}.png`);
  // One screenshot, copied `hold` times: at ffmpeg's fixed frame rate
  // that is the moment's time on screen, without more CDP round trips.
  async function shot(hold) {
    const first = name(frame++);
    await page.screenshot({ path: first });
    for (let i = 1; i < hold; i++) fs.copyFileSync(first, name(frame++));
  }

  await shot(20); // the whole graph
  for (let i = 0; i < 5; i++) {
    const dot = await page.$("#dot-" + i);
    if (!dot) break;
    await dot.click(); // fills the side panel with that topic
    await sleep(150);
    await shot(22);
  }
  const tree = await page.$("#treebox");
  if (tree) {
    await page.evaluate((el) => { el.open = true; }, tree);
    await sleep(150);
    await shot(20);
  }
  if (still) await readmeStill(browser, html, still);

  await browser.close();
  console.log(`${frame} frames written to ${outdir}`);
}

// Opens the map afresh at 1040x600 (the graph is laid out once, on load,
// so a resized page keeps the 1280px layout), then clicks the dots in turn
// until the panel's heading is topic-1, and screenshots. 1040px is the
// narrowest width at which the viewer keeps every topic label inside the
// canvas.
async function readmeStill(browser, html, file) {
  const page = await browser.newPage();
  await page.setViewport({ width: 1040, height: 600, deviceScaleFactor: 2 });
  await page.goto("file://" + path.resolve(html), { waitUntil: "load" });
  await sleep(300);
  for (let i = 0; ; i++) {
    const dot = await page.$("#dot-" + i);
    if (!dot) throw new Error("no topic-1 dot: the README still was not written");
    await dot.click();
    await sleep(150);
    const heading = await page.$eval("#detail h2, #detail h3", (el) => el.textContent.trim());
    if (heading === "topic-1") break;
  }
  await page.screenshot({ path: file });
  console.log(`README still written to ${file}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
