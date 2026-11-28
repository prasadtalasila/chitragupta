"use strict";

const test = require("node:test");
const assert = require("node:assert");

const token = require("../../assets/webapp/workbench/token.js");

function fakes(hash, stored) {
  const calls = [];
  const data = stored === undefined ? {} : { [token.STORAGE_KEY]: stored };
  return {
    calls,
    data,
    location: { hash, pathname: "/" },
    history: { replaceState: (...args) => calls.push(args) },
    storage: {
      getItem: (key) => (key in data ? data[key] : null),
      setItem: (key, value) => {
        data[key] = value;
      },
    },
  };
}

test("a fragment token is stored and removed from the address bar", () => {
  const f = fakes("#token=abc", undefined);
  assert.strictEqual(token.takeToken(f.location, f.history, f.storage), "abc");
  assert.strictEqual(f.data[token.STORAGE_KEY], "abc");
  assert.deepStrictEqual(f.calls, [[null, "", "/"]]);
});

test("a fresh fragment token replaces an older stored one", () => {
  const f = fakes("#token=new", "old");
  assert.strictEqual(token.takeToken(f.location, f.history, f.storage), "new");
});

test("without a fragment the stored token is used and the URL is left alone", () => {
  const f = fakes("", "abc");
  assert.strictEqual(token.takeToken(f.location, f.history, f.storage), "abc");
  assert.deepStrictEqual(f.calls, []);
});

test("neither a fragment nor a stored token gives null", () => {
  const f = fakes("", undefined);
  assert.strictEqual(token.takeToken(f.location, f.history, f.storage), null);
});

test("an empty fragment token counts as none, and is still cleared from the URL", () => {
  const f = fakes("#token=", undefined);
  assert.strictEqual(token.takeToken(f.location, f.history, f.storage), null);
  assert.deepStrictEqual(f.calls, [[null, "", "/"]]);
});

test("storage that throws (private mode) still yields the fragment token", () => {
  const f = fakes("#token=abc", undefined);
  const broken = {
    getItem: () => {
      throw new Error("denied");
    },
    setItem: () => {
      throw new Error("denied");
    },
  };
  assert.strictEqual(token.takeToken(f.location, f.history, broken), "abc");
  const g = fakes("", undefined);
  assert.strictEqual(token.takeToken(g.location, g.history, broken), null);
});

test("the token goes in a bearer header", () => {
  assert.deepStrictEqual(token.authHeaders("abc"), { Authorization: "Bearer abc" });
});
