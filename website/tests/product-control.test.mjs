import test from "node:test";
import assert from "node:assert/strict";
import { mayDemonstrate, nextDemoCut, cutsAtProgress, DEMO_CUTS, RECOGNIZED_CUTS } from "../product/demo.js";
import {
  edit,
  initialEdit,
  legalCuts,
  fragments,
  sentence,
} from "../product/edit-model.js";

test("idle demonstrations yield to pointer, focus, manual pin, reduced motion and hidden pages", () => {
  const allowed = {
    visible: true,
    occupied: false,
    focused: false,
    reduced: false,
    suspended: false,
    hidden: false,
  };
  assert.equal(mayDemonstrate(allowed), true);
  for (const key of ["occupied", "focused", "reduced", "suspended", "hidden"])
    assert.equal(mayDemonstrate({ ...allowed, [key]: true }), false);
  assert.equal(mayDemonstrate({ ...allowed, visible: false }), false);
});
test("the sample starts from recognized cues that the razor demo only refines", () => {
  assert.ok(RECOGNIZED_CUTS.every((i) => DEMO_CUTS.includes(i)));
  assert.ok(DEMO_CUTS.length > RECOGNIZED_CUTS.length);
});
test('scroll milestones produce 1, 2, 4, 7 complete contiguous fragments', () => {
  for (const [progress, count] of [[0,1],[.3,2],[.5,4],[.8,7]]) {
    let s = initialEdit;
    for (const at of DEMO_CUTS.slice(0,cutsAtProgress(progress))) s=edit(s,{type:'split',at});
    const cues=fragments(s.cuts);
    assert.equal(cues.length,count);
    assert.equal(cues.map(c=>c.text).join(''),sentence);
    cues.forEach((cue,i)=>{assert.ok(cue.end>cue.start);if(i)assert.equal(cues[i-1].end,cue.start);});
  }
});
test("progressive demonstration appends around manual cuts without resetting text or time", () => {
  let s = edit(edit(initialEdit, { type: "split", at: 2 }), {
    type: "split",
    at: 17,
  });
  const manual = s.cuts.slice();
  let steps = 0,
    at;
  while ((at = nextDemoCut(s.cuts, legalCuts(s.cuts))) !== undefined) {
    s = edit(s, { type: "split", at });
    steps++;
    assert.ok(manual.every((i) => s.cuts.includes(i)));
    const cues = fragments(s.cuts);
    assert.equal(cues.map((c) => c.text).join(""), sentence);
    for (let i = 1; i < cues.length; i++)
      assert.equal(cues[i - 1].end, cues[i].start);
    assert.ok(steps < 10);
  }
  assert.deepEqual(s.cuts, [2, 5, 9, 13, 17, 20, 23]);
});
