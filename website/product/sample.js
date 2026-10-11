// The sample in the page language. Timing, segmentation and cut rules stay in
// edit-model.js (tested on the Chinese text); here only the text of each word
// changes, so every language cuts, merges and plays the same way.
import S from "@lang/sample";
import { words as base, fragments as baseFragments, legalCuts, clock } from "./edit-model.js";
import { TEAM_CUE as BASE_TEAM } from "./data.js";

export { legalCuts, clock };
export const SAMPLE = S;
export const words = S.words ? base.map((w, i) => ({ ...w, text: S.words[i] })) : base;
const join = (parts) => parts.join(S.spaced ? " " : "");
// Text of words [from, to), with optional per-word replacements { index: text }.
export const phrase = (from, to, texts = {}) => join(words.slice(from, to).map((w) => texts[w.i] ?? w.text));
export const fragments = (cuts, texts = {}) => baseFragments(cuts).map((f) => ({ ...f, text: phrase(f.from, f.to, texts) }));
export const TEAM_CUE = S.team ? { ...BASE_TEAM, text: S.team } : BASE_TEAM;
// The word whose three readings the review demo compares, and the razor demo's cut.
export const REVIEW_AT = 16;
export const CUT_AT = 13;
export const bare = (text) => text.replace(/[，,、。.！!？?]+$/, "");
