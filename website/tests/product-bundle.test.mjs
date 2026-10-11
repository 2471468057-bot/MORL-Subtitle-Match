import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

test("standalone keeps one valid inline bundle and embedded image assets", () => {
  const html = fs.readFileSync(
    new URL("../product-build/打开产品介绍.html", import.meta.url),
    "utf8",
  );
  const scripts = [...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)];
  assert.equal(
    scripts.length,
    1,
    "replacement tokens must not duplicate the document",
  );
  assert.doesNotMatch(scripts[0][1], /\bsrc=/);
  assert.doesNotThrow(() => new vm.Script(scripts[0][2]));
  assert.equal(
    (html.replace(scripts[0][0], "").match(/<!doctype html>/gi) || []).length,
    1,
  );
  assert.match(scripts[0][2], /window\.__PRODUCT_ASSETS=/);
  assert.match(scripts[0][2], /data:image\/webp;base64,/);
  assert.doesNotMatch(html, /<link[^>]+rel="stylesheet"/i);
});
