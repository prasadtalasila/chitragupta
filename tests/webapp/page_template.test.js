/* chitragupta/discover/_page_template.py: the --html page's escaper.

   That page is one Python string with its script inline, so there is no
   module to require(); the function is lifted out of the template text
   and run as written. It must agree with panel.js's escapeHtml on the
   same hostile input (#856): both pages render the same corpus-derived
   labels, and the --html one escaped three characters of the five. */
"use strict";

const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");

const panel = require("../../assets/webapp/panel.js");

const TEMPLATE = fs.readFileSync(
  path.join(__dirname, "..", "..", "chitragupta", "discover", "_page_template.py"),
  "utf8"
);

// Read from the .py source, not Python's evaluated TEMPLATE: the two are
// the same text only while esc() holds no backslash, which a "\\" in a
// future regex would change.
function templateEsc() {
  const source = TEMPLATE.match(/function esc\(text\) \{[\s\S]*?\n\}/);
  assert.ok(source, "the --html page's esc() is gone or renamed");
  return new Function(source[0] + "\nreturn esc;")();
}

const HOSTILE = "<a href=\"x\" title='y'>&</a>";

test("all five HTML-significant characters are escaped", () => {
  assert.equal(
    templateEsc()(HOSTILE),
    "&lt;a href=&quot;x&quot; title=&#39;y&#39;&gt;&amp;&lt;/a&gt;"
  );
});

test("it escapes exactly as panel.js does", () => {
  const esc = templateEsc();
  for (const input of [HOSTILE, "plain label", "", null, undefined, 0, "\"onmouseover=\""]) {
    assert.equal(esc(input), panel.escapeHtml(input), JSON.stringify(input));
  }
});
