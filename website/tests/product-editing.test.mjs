import test from "node:test";
import assert from "node:assert/strict";
import {
  words,
  sentence,
  initialEdit,
  edit,
  fragments,
  legalCuts,
} from "../product/edit-model.js";

function invariant(s) {
  const cues = fragments(s.cuts);
  assert.equal(cues.map((c) => c.text).join(""), sentence);
  assert.equal(cues[0].start, 420);
  assert.equal(cues.at(-1).end, 15260);
  for (let i = 0; i < cues.length; i++) {
    assert.ok(cues[i].end - cues[i].start >= 50);
    if (i)
      assert.equal(
        cues[i - 1].end,
        cues[i].start,
        "manual razor has a shared cut, no artificial gap",
      );
  }
}
test("all legal word cuts preserve non-uniform evidence and punctuation", () => {
  const evidence = JSON.stringify(words);
  assert.equal(
    sentence,
    "我们先沿着河边往前走，等队友拿齐补给，再一起去山顶看看有没有新的任务，路上遇到敌人就先找掩体，不要急着开枪。",
  );
  let s = initialEdit;
  for (const at of [
    23, 5, 17, 9, 1, 25, 2, 13, 4, 3, 6, 7, 8, 10, 11, 12, 14, 15, 16, 18, 19,
    20, 21, 22, 24,
  ]) {
    assert.ok(legalCuts(s.cuts).includes(at));
    s = edit(s, { type: "split", at });
    invariant(s);
    assert.equal(
      fragments(s.cuts).find((c) => c.from === at).start,
      words[at].start,
    );
  }
  assert.equal(fragments(s.cuts).length, 26);
  assert.deepEqual(legalCuts(s.cuts), []);
  assert.equal(JSON.stringify(words), evidence);
});
test("three cuts, adjacent merge, undo and reset round-trip without text/time loss", () => {
  let s = initialEdit;
  for (const at of [5, 17, 23]) s = edit(s, { type: "split", at });
  assert.deepEqual(s.cuts, [5, 17, 23]);
  invariant(s);
  s = edit(s, { type: "merge", at: 17 });
  assert.deepEqual(s.cuts, [5, 23]);
  invariant(s);
  s = edit(s, { type: "undo" });
  assert.deepEqual(s.cuts, [5, 17, 23]);
  invariant(s);
  for (let i = 0; i < 3; i++) s = edit(s, { type: "undo" });
  assert.deepEqual(s.cuts, []);
  invariant(s);
  s = edit(edit(initialEdit, { type: "split", at: 9 }), { type: "reset" });
  assert.deepEqual(s, initialEdit);
});
test("outside, duplicate and missing cut operations are no-ops", () => {
  let s = edit(initialEdit, { type: "split", at: 5 });
  for (const at of [-1, 0, 5, 26, 99, 2.5])
    assert.equal(edit(s, { type: "split", at }), s);
  assert.equal(edit(s, { type: "merge", at: 3 }), s);
});
test("candidate text uses the same word identity through cuts, merging and undo", () => {
  let s = initialEdit;
  for (const at of [5,9,13,17,20,23]) s=edit(s,{type:'split',at});
  const base = fragments(s.cuts);
  for (const word of ['人物，','任务，','战术，']) {
    const candidate = fragments(s.cuts,{16:word});
    assert.equal(candidate.map(c=>c.text).join(''), sentence.replace('任务，',word));
    assert.deepEqual(candidate.map(c=>[c.from,c.to,c.start,c.end]),base.map(c=>[c.from,c.to,c.start,c.end]));
    const merged=edit(s,{type:'merge',at:17});
    assert.equal(fragments(merged.cuts,{16:word}).map(c=>c.text).join(''),sentence.replace('任务，',word));
    assert.deepEqual(edit(merged,{type:'undo'}).cuts,s.cuts);
  }
});

