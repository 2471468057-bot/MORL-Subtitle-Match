// Hand-authored non-uniform evidence. This is not inference output.
// Manual split contract: studio_timing.resolve_split + studio_commands._splice_split.
export const words = [
  ["我们", 420, 880],
  ["先", 970, 1200],
  ["沿着", 1220, 1690],
  ["河边", 1770, 2300],
  ["往前走，", 2350, 3130],
  ["等", 3490, 3740],
  ["队友", 3780, 4260],
  ["拿齐", 4300, 4790],
  ["补给，", 4840, 5400],
  ["再", 5730, 5960],
  ["一起", 5990, 6470],
  ["去", 6490, 6690],
  ["山顶", 6740, 7240],
  ["看看", 7290, 7740],
  ["有没有", 7800, 8460],
  ["新的", 8510, 8960],
  ["任务，", 9020, 9600],
  ["路上", 10060, 10530],
  ["遇到", 10560, 11030],
  ["敌人", 11110, 11630],
  ["就", 11700, 11930],
  ["先找", 11970, 12410],
  ["掩体，", 12480, 13080],
  ["不要", 13560, 14030],
  ["急着", 14090, 14580],
  ["开枪。", 14630, 15260],
].map(([text, start, end], i) => ({ text, start, end, i }));
export const sentence = words.map((w) => w.text).join("");
export const initialEdit = { cuts: [], history: [] };
export function fragments(cuts, texts = {}) {
  const edges = [0, ...cuts, words.length];
  return edges.slice(0, -1).map((from, i) => {
    const to = edges[i + 1];
    return {
      from,
      to,
      text: words
        .slice(from, to)
        .map((w) => texts[w.i] || w.text)
        .join(""),
      start: words[from].start,
      end: to === words.length ? words.at(-1).end : words[to].start,
    };
  });
}
export function legalCuts(cuts) {
  return words
    .slice(1)
    .map((w) => w.i)
    .filter(
      (i) =>
        !cuts.includes(i) &&
        fragments(cuts).some(
          (f) =>
            i > f.from &&
            i < f.to &&
            words[i].start - f.start >= 50 &&
            f.end - words[i].start >= 50,
        ),
    );
}
export function edit(state, action) {
  if (action.type === "demo") {
    // Only the local demo controller issues this; it never runs after manual takeover.
    const cuts = [...new Set(action.cuts)].filter(i => Number.isInteger(i) && i > 0 && i < words.length).sort((a,b)=>a-b);
    return cuts.join(',') === state.cuts.join(',') ? state : {...state, cuts};
  }
  if (action.type === "reset") return { ...initialEdit };
  if (action.type === "undo")
    return state.history.length
      ? { cuts: state.history.at(-1), history: state.history.slice(0, -1) }
      : state;
  let cuts = state.cuts;
  if (action.type === "split" && legalCuts(cuts).includes(action.at))
    cuts = [...cuts, action.at].sort((a, b) => a - b);
  if (action.type === "merge" && cuts.includes(action.at))
    cuts = cuts.filter((i) => i !== action.at);
  if (cuts === state.cuts) return state;
  return { cuts, history: [...state.history, state.cuts] };
}
export const clock = (ms) =>
  `${String(Math.floor(ms / 60000)).padStart(2, "0")}:${((ms % 60000) / 1000).toFixed(3).padStart(6, "0")}`;
