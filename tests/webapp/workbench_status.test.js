/* assets/webapp/workbench/status.js: what the placeholder page shows,
   built from text nodes only, so a hostile project name stays text. */
"use strict";

const test = require("node:test");
const assert = require("node:assert");

const status = require("../../assets/webapp/workbench/status.js");

function fakeDocument() {
  const created = [];
  return {
    created,
    createElement(tag) {
      const node = {
        tagName: tag.toUpperCase(),
        children: [],
        textContent: "",
        appendChild(child) {
          this.children.push(child);
          return child;
        },
      };
      created.push(node);
      return node;
    },
  };
}

function fakeRoot() {
  return {
    children: [],
    replaceChildren(...nodes) {
      this.children = nodes;
    },
  };
}

function text(root) {
  return root.children.map((n) => n.textContent).join("\n");
}

test("the status shows the project and the version", () => {
  const doc = fakeDocument();
  const root = fakeRoot();
  status.renderStatus(doc, root, { project: "thesis", version: "7.3.0" });
  assert.match(text(root), /thesis/);
  assert.match(text(root), /7\.3\.0/);
});

test("an HTML payload in the project name renders as literal text", () => {
  const doc = fakeDocument();
  const root = fakeRoot();
  const hostile = '<img src=x onerror="alert(1)">';
  status.renderStatus(doc, root, { project: hostile, version: "1" });
  assert.ok(text(root).includes(hostile));
  assert.deepStrictEqual(
    doc.created.map((n) => n.tagName).filter((t) => t !== "P" && t !== "H1"),
    [],
  );
});

test("without a token the page says where to find the URL", () => {
  const doc = fakeDocument();
  const root = fakeRoot();
  status.renderNoToken(doc, root);
  assert.match(text(root), /URL printed in the terminal/);
});

test("a refused request says the same, with the status code", () => {
  const doc = fakeDocument();
  const root = fakeRoot();
  status.renderRefused(doc, root, 401);
  assert.match(text(root), /401/);
  assert.match(text(root), /URL printed in the terminal/);
});
