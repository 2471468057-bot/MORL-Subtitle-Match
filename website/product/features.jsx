import React, { useEffect, useRef, useState } from "react";
import { Icon } from "./icons.jsx";
import { AppFrame, Check, Chip, Mascot, SignalArt, Spk } from "./kit.jsx";
import { Section } from "./chapter.jsx";
import { useLoop } from "./motion.js";
import { timecode } from "./data.js";
import { SAMPLE, TEAM_CUE, words, clock, phrase, bare, CUT_AT, REVIEW_AT } from "./sample.js";
import libraryData from "./glossary-data.json";
import { COPY, rich, t } from "./i18n/index.jsx";
import "./features.css";

// Every demo plays by itself while visible; hovering pauses it, clicking hands it over.
function useDemo(durations, reduced, still) {
  const ref = useRef();
  const [hover, setHover] = useState(false);
  const [manual, setManual] = useState(false);
  const loop = useLoop(ref, durations, { reduced, paused: hover || manual, still });
  const bind = {
    ref,
    onPointerEnter: (e) => e.pointerType === "mouse" && setHover(true),
    onPointerLeave: () => setHover(false),
  };
  return { ...loop, bind, manual, take: () => setManual(true), resume: () => setManual(false) };
}
const Resume = ({ demo }) =>
  demo.manual ? (
    <button className="demo-resume" onClick={demo.resume}>
      <Icon name="refresh" size={13} />{COPY.resume}
    </button>
  ) : null;
// One frame size for every demonstration: 1280 x 700, scaled to the page width.
const frame = (demo, node) => (
  <div className="demo" {...demo.bind}>
    <AppFrame design={1280} fluidBelow={0.6} maxScale={1.3}>{node}</AppFrame>
    <Resume demo={demo} />
  </div>
);

/* ── 1. 候选字幕 / 优先审核（字幕工作台审核模式）────────────────────── */
// Three readings of one word in the sample; the second one is right.
const READINGS = ["MOSS", "FireRed", "Qwen"].map((src, i) => ({ src, word: SAMPLE.readings[i], current: i === 0 }));
const BASE = phrase(9, REVIEW_AT) + (SAMPLE.spaced ? " " : "");

function ReviewDemo({ reduced }) {
  const demo = useDemo([1900, 1200, 2800], reduced, 2);
  const [pick, setPick] = useState(null);
  const [adopted, setAdopted] = useState(null);
  useEffect(() => {
    if (demo.manual) return;
    setPick(demo.step >= 1 ? 1 : null);
    setAdopted(demo.step >= 2 ? 1 : null);
  }, [demo.step, demo.manual]);
  const adopt = (i) => {
    demo.take();
    setPick(i);
    setAdopted(i);
  };
  const shown = READINGS[adopted ?? 0].word;
  const queue = [
    { no: 4, time: "00:05.730", spk: "S00", text: BASE + shown, tag: adopted != null ? ["ok", t("已完成")] : ["warn", t("需要检查")] },
    { no: 3, time: "00:05.450", spk: "S01", text: TEAM_CUE.text, tag: ["info", t("建议确认")] },
    { no: 6, time: "00:13.560", spk: "S00", text: phrase(23, 26), tag: ["info", t("建议确认")] },
  ];
  const settled = [
    { no: 1, time: "00:00.420", spk: "S00", text: phrase(0, 5) },
    { no: 2, time: "00:03.490", spk: "S00", text: phrase(5, 9) },
    { no: 5, time: "00:10.060", spk: "S00", text: phrase(17, 23) },
  ];
  const current = adopted != null ? 1 : 0;
  return frame(
    demo,
    <div className="app demo-app rv">
      <div className="rv-bar">
        <Icon name="arrowLeft" size={15} />
        <b>{t("双人对话")}</b>
        <span className="t3">{t("示例工程")}</span>
        <span className="grow" />
        <span className="app-btn on"><Icon name="list" size={13} />{t("字幕列表")}</span>
        <span className="app-btn soft">{t("■ 退出审核")}</span>
      </div>
      <div className="rv-body">
        <aside className="rv-list">
          <b>{t("字幕列表")}</b>
          <div className="rv-filters">
            <span className="app-btn">{t("全部 {n}", { n: 6 })}</span>
            <span className="app-btn">{t("建议确认 {n}", { n: 2 })}</span>
            <span className="app-btn soft">{t("需要检查 {n}", { n: 1 })}</span>
          </div>
          <span className="t3 rv-hint">{t("有分歧的句子排在最前面")}</span>
          {queue.map((q, i) => (
            <div key={q.no} className={"rv-row" + (i === current ? " is-current" : "") + (q.tag[0] === "ok" ? " is-done" : "")}>
              <div className="app-row">
                <span className="mono t3">#{q.no}</span>
                <span className="mono t3">{q.time}</span>
                <Spk id={q.spk} />
                <span className="grow" />
                <Chip tone={q.tag[0]}>{q.tag[1]}</Chip>
              </div>
              <span className="rv-text">{q.text}</span>
            </div>
          ))}
          <span className="t3 rv-hint rv-sep">{t("模型写法一致，无需检查")}</span>
          {settled.map((q) => (
            <div key={q.no} className="rv-row is-quiet">
              <div className="app-row">
                <span className="mono t3">#{q.no}</span>
                <span className="mono t3">{q.time}</span>
                <Spk id={q.spk} />
              </div>
              <span className="rv-text">{q.text}</span>
            </div>
          ))}
        </aside>
        <div className="rv-main">
          <SignalArt className="rv-frame" tc="00:00:06:18">
            <div className="rv-caps">
              <span className="burned-caption rv-cap">{BASE}<mark key={shown}>{shown}</mark></span>
            </div>
          </SignalArt>
          <div className="rv-strip">
            <div className="app-row rv-head">
              <b className="rv-warn">{t("⚠ 候选文本存在差异")}</b>
              <span className="t3 grow rv-reason">{t("模型对「{w}」存在分歧", { w: SAMPLE.readings.map(bare).join(" / ") })}</span>
              <span className="mono t2">{t("审核进度 {n} / {total}", { n: adopted != null ? 2 : 1, total: 3 })}</span>
              <span className="app-btn primary">{t("当前正确")}</span>
              <span className="app-btn">{t("重听")}</span>
            </div>
            <div className="rv-cards">
              {READINGS.map((r, i) => (
                <button key={r.src} className={"rv-card" + (pick === i ? " is-on" : "") + (adopted === i ? " is-adopted" : "")} onClick={() => adopt(i)} aria-label={t("采用候选 {n}：{src}", { n: i + 1, src: r.src })}>
                  <span className="app-row">
                    <span className="rv-num mono">{i + 1}</span>
                    {r.current && <span className="app-chip square accent">{t("当前")}</span>}
                    <span className="app-chip square">{r.src}</span>
                  </span>
                  <span className="rv-cand">
                    {BASE}
                    <mark className={r.current ? "" : "diff"}>{r.word}</mark>
                  </span>
                </button>
              ))}
              <div className={"rv-saved" + (adopted != null ? " on" : "")}>{adopted != null ? t("✓ 已采用候选 {n} · 下一条", { n: adopted + 1 }) : t("按数字键采用，Enter 表示当前正确")}</div>
            </div>
            <div className="rv-legend t3 mono">{t("[1–4] 采用并下一条　[↑↓] 切换　[Space] 重听　[E] 编辑　[Enter] 当前正确")}</div>
          </div>
        </div>
      </div>
    </div>,
  );
}

/* ── 2. AI 词库校对 ─────────────────────────────────────────── */
const SUGG = [
  { id: "a", time: "00:03.5", no: 2, spk: "S00", hit: [t("明日方舟"), t("已确认词条")], on: true },
  { id: "b", time: "00:05.4", no: 3, spk: "S01", hit: [t("明日方舟"), t("已确认词条")], on: true },
  { id: "d", time: "00:11.7", no: 5, spk: "S00", hit: [t("明日方舟"), t("已确认词条")], on: true },
  { id: "c", time: "00:13.6", no: 6, spk: "S00", hit: [t("参考词条，待你确认")], on: false },
].map((s, i) => ({ ...s, ...SAMPLE.proofread[i] }));
function ProofreadDemo({ reduced }) {
  const demo = useDemo([1900, 900, 3200], reduced, 2);
  const [checked, setChecked] = useState({ a: true, b: true, d: true, c: false });
  const [written, setWritten] = useState([]);
  useEffect(() => {
    if (demo.manual) return;
    setChecked({ a: true, b: true, d: true, c: false });
    setWritten(demo.step >= 2 ? ["a", "b", "d"] : []);
  }, [demo.step, demo.manual]);
  const pending = SUGG.filter((s) => checked[s.id] && !written.includes(s.id)).length;
  return frame(
    demo,
    <div className="app demo-app pf">
      <div className="pf-head">
        <span className="app-btn"><Icon name="arrowLeft" size={13} />{t("返回结果")}</span>
        <b>{t("AI 词库校对")}</b>
        <span className="grow" />
        <span className="t3">{t("已按词库匹配 {n} 条字幕", { n: 6 })}</span>
      </div>
      <div className="pf-body">
        <aside className="pf-libs">
          <b>{t("使用的词库")}</b>
          {[t("明日方舟"), t("绝区零"), t("洛克王国：世界")].map((n, i) => (
            <span className="app-row" key={n}><Check on={i === 0} label={n} />{n}</span>
          ))}
          <span className="t3 pf-small">{t("已选 1 个词库，有效 10 个规范词")}</span>
          <b className="pf-sub">{t("添加专有名词")}</b>
          <span className="t3 pf-small">{t("每行一个正确写法；常被听错的写法用 → 连到正确写法")}</span>
          <span className="app-field pf-add">{SAMPLE.proofAdd[0]}<br />{SAMPLE.proofAdd[1]}</span>
        </aside>
        <div className="pf-main">
          <div className="app-row pf-tools">
            <b>{t("修改建议")}</b>
            <span className="t3">{t("共 {n} 处，已勾选 {m} 处", { n: SUGG.length, m: SUGG.filter((s) => checked[s.id]).length })}</span>
            <span className="grow" />
            <span className="app-btn on">{t("按词库匹配")}</span>
            <span className="app-btn soft">{t("AI 校对建议")}</span>
          </div>
          {SUGG.map((s) => {
            const done = written.includes(s.id);
            return (
              <div key={s.id} className={"pf-item" + (done ? " is-done" : "") + (!checked[s.id] ? " is-off" : "")}>
                <Check
                  on={checked[s.id] || done}
                  label={t("勾选第 {no} 条：{from} 改为 {to}", { no: s.no, from: s.from, to: s.to })}
                  onChange={(v) => {
                    if (done) return;
                    demo.take();
                    setChecked({ ...checked, [s.id]: v });
                  }}
                />
                <div className="pf-lines">
                  <div className="app-row pf-meta">
                    <span className="mono t3">{s.time}</span>
                    <span className="t3">#{s.no}</span>
                    <Spk id={s.spk} />
                    <span className="grow" />
                    {done ? <Chip tone="ok" icon="check">{t("已写回")}</Chip> : !checked[s.id] ? <span className="t3">{t("未勾选 · 保持原文")}</span> : <span className="t3">{t("待你复核")}</span>}
                  </div>
                  <div className="pf-line"><span className="pf-k">{t("原文")}</span><span>{s.pre}<del>{s.from}</del>{s.post}</span></div>
                  <div className="pf-line"><span className="pf-k">{t("建议")}</span><span>{s.pre}<ins>{s.to}</ins>{s.post}</span></div>
                  {done && <div className="pf-line pf-after"><span className="pf-k">{t("套用后")}</span><span>{s.pre}{s.to}{s.post}</span></div>}
                  <div className="t3 pf-hit">{t("命中：")}<span>{s.from} → {s.to}</span>{s.hit.map((h) => " · " + h).join("")}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
      <div className="pf-foot">
        <span className="t3">{t("勾选的修改只有点击应用后才写回字幕；写回后可在字幕工作台撤销。")}</span>
        <span className="grow" />
        <button className="app-btn primary" disabled={!pending} onClick={() => { demo.take(); setWritten([...written, ...SUGG.filter((s) => checked[s.id]).map((s) => s.id)]); }}>
          {pending ? t("应用所选 {n} 处修改", { n: pending }) : t("已写回 {n} 处", { n: written.length })}
        </button>
      </div>
    </div>,
  );
}

/* ── 3. 术语库 ─────────────────────────────────────────────── */
const ADD = SAMPLE.add;
const termName = (r) => SAMPLE.glossary?.[r.id] ?? r.name;
// Library names, categories and sources are interface text; the terms stay Chinese.
const GAME = { ark: t("明日方舟"), zzz: t("绝区零"), roco: t("洛克王国：世界") };
const CATEGORY = { 角色: t("角色"), 精灵: t("精灵") };
const SOURCE = { 内置参考: t("内置参考"), 手动添加: t("手动添加") };
function GlossaryDemo({ reduced }) {
  const demo = useDemo([1600, 1700, 1700, 1700, 1200], reduced, 3);
  const base = libraryData.find((g) => g.id === "ark");
  const [game, setGame] = useState("ark");
  const [added, setAdded] = useState(false);
  const [confirmed, setConfirmed] = useState([]);
  const [typed, setTyped] = useState(["", ""]);
  useEffect(() => {
    if (demo.manual) return;
    setGame("ark");
    setAdded(demo.step >= 2);
    setConfirmed(demo.step >= 3 ? ["ark2"] : []);
    if (demo.step !== 1) setTyped(demo.step >= 2 ? ["", ""] : ["", ""]);
  }, [demo.step, demo.manual]);
  useEffect(() => {
    if (demo.manual || demo.step !== 1) return;
    // type the alias, then the canonical name (3 keystrokes later), within the step
    const n = Math.floor(demo.ms / Math.min(260, 1500 / Math.max(ADD.alias.length, 3 + ADD.name.length)));
    setTyped([ADD.alias.slice(0, n), ADD.name.slice(0, Math.max(0, n - 3))]);
  }, [demo.ms, demo.step, demo.manual]);
  const lib = libraryData.find((g) => g.id === game);
  const rows = [
    ...(added && game === "ark" ? [{ id: "new", name: ADD.name, alias: ADD.alias, category: "角色", status: "confirmed", source: "手动添加", fresh: true }] : []),
    ...lib.rows.map((r) => (confirmed.includes(r.id) ? { ...r, status: "confirmed", fresh: true } : r)),
  ];
  const count = (st) => rows.filter((r) => r.status === st).length;
  return frame(
    demo,
    <div className="app demo-app gl">
      <div className="gl-top">
        <b>{t("术语库")}</b>
        <Chip>{t("{n} 个游戏", { n: libraryData.length })}</Chip>
        <span className="t3">{t("让角色名、技能和游戏专名更容易识别正确。")}</span>
      </div>
      <div className="gl-body">
        <aside className="gl-libs">
          <div className="app-row"><b>{t("我的词库")}</b><span className="grow" /><span className="t3 gl-new"><Icon name="plus" size={13} />{t("新建")}</span></div>
          {libraryData.map((g) => {
            const n = g.id === game ? count("confirmed") : g.rows.filter((r) => r.status === "confirmed").length;
            const m = g.id === game ? count("reference") : g.rows.filter((r) => r.status === "reference").length;
            return (
              <button key={g.id} className="gl-lib" aria-pressed={g.id === game} onClick={() => { demo.take(); setGame(g.id); }}>
                <span className="gl-book"><Icon name="book" size={14} /></span>
                <span><b>{GAME[g.id] || g.name}</b><small>{t("{n} 已确认 · {m} 参考", { n, m })}</small></span>
              </button>
            );
          })}
          <span className="gl-sync t3"><i />{t("内置词库示例")}</span>
        </aside>
        <div className="gl-main">
          <div className="app-row gl-head">
            <b>{t("{name} · 游戏", { name: GAME[lib.id] || lib.name })}</b>
            <span className="grow" />
            <Chip tone="ok">{t("{n} 条已确认", { n: count("confirmed") })}</Chip>
            <Chip tone="info">{t("{n} 条参考", { n: count("reference") })}</Chip>
          </div>
          <div className="gl-add">
            <b>{t("添加术语")}</b>
            <span className={"app-field gl-in" + (typed[0] ? " on" : "")}>{typed[0] ? <span>{typed[0]}</span> : <span className="t3">{t("别名 / 常见错词")}</span>}</span>
            <Icon name="arrowRight" size={14} className="t3" />
            <span className={"app-field gl-in" + (typed[1] ? " on" : "")}>{typed[1] ? <span>{typed[1]}</span> : <span className="t3">{t("规范写法 / 最终输出")}</span>}</span>
            <span className="app-btn"><Icon name="plus" size={13} />{t("添加术语")}</span>
          </div>
          <div className="gl-table">
            <div className="gl-tr gl-th"><span>{t("术语 / 纠错")}</span><span>{t("分类")}</span><span>{t("来源")}</span><span>{t("状态")}</span></div>
            {rows.slice(0, 9).map((r) => (
              <div key={r.id} className={"gl-tr" + (r.fresh ? " is-fresh" : "")}>
                <b>{termName(r)}{r.alias && <span className="t3 gl-alias"> ← {r.alias}</span>}</b>
                <span>{CATEGORY[r.category] || r.category}</span>
                <span className="t3">{r.source.startsWith("http") ? t("Wiki 名称清单") : SOURCE[r.source] || r.source}</span>
                <span>
                  {r.status === "confirmed" ? <Chip tone="ok">{t("已确认")}</Chip> : (
                    <button className="app-btn quiet gl-confirm" onClick={() => { demo.take(); setConfirmed([...confirmed, r.id]); }}>{t("参考 · 确认")}</button>
                  )}
                </span>
              </div>
            ))}
          </div>
          <div className="app-row gl-foot">
            <span className="t3">{t("已确认的词条会用于之后每一次识别与校对")}</span>
            <span className="grow" />
            <span className="app-btn"><Icon name="globe" size={13} />{t("日常增量更新")}</span>
            <span className="app-btn primary"><Icon name="check" size={13} />{t("用于本批字幕")}</span>
          </div>
        </div>
      </div>
    </div>,
  );
}

/* ── 4. 字级时间轴 / 分轨 ───────────────────────────────────── */
const T0 = 5200,
  T1 = 10400;
const CUE_WORDS = words.slice(9, 17); // the cue a9: 5730 → 9600, runs to 10060
const at = (ms) => `${((ms - T0) / (T1 - T0)) * 100}%`;
const span = (a, b) => ({ left: at(Math.max(T0, a)), width: `${((Math.min(T1, b) - Math.max(T0, a)) / (T1 - T0)) * 100}%` });

function WordWave() {
  const bars = [];
  let seed = 5;
  const rnd = () => ((seed = (seed * 9301 + 49297) % 233280) / 233280);
  for (let t = T0; t < T1; t += 50) {
    const on = words.some((w) => t >= w.start && t < w.end) || (t >= TEAM_CUE.start && t < TEAM_CUE.end);
    bars.push(on ? 0.3 + rnd() * 0.7 : 0.04 + rnd() * 0.06);
  }
  return (
    <svg className="tm-wave" viewBox={`0 0 ${bars.length} 100`} preserveAspectRatio="none" aria-hidden="true">
      {bars.map((a, i) => <rect key={i} x={i + 0.2} width="0.6" y={50 - a * 46} height={a * 92} rx="0.3" />)}
    </svg>
  );
}

function TimingDemo({ reduced }) {
  const demo = useDemo([5600, 1500, 2300, 700], reduced, 2);
  const [cut, setCut] = useState(false);
  const [aim, setAim] = useState(false);
  const [now, setNow] = useState(7450);
  useEffect(() => {
    if (demo.manual) return;
    setCut(demo.step === 2);
    setAim(demo.step === 1);
    if (demo.step === 1 || demo.step === 2) setNow(7290);
  }, [demo.step, demo.manual]);
  useEffect(() => {
    if (demo.manual || demo.step !== 0) return;
    setNow(5350 + demo.ms * 0.82);
  }, [demo.ms, demo.step, demo.manual]);
  const cueA = cut
    ? [{ id: "a1", start: 5730, end: 7290, text: phrase(9, CUT_AT) }, { id: "a2", start: 7290, end: 10060, text: phrase(CUT_AT, 17) }]
    : [{ id: "a", start: 5730, end: 10060, text: phrase(9, 17) }];
  const lanes = [
    { id: "prev", start: 3490, end: 5730, text: phrase(5, 9) },
    ...cueA,
  ];
  const caps = [
    ...(now >= TEAM_CUE.start && now < TEAM_CUE.end ? [{ spk: "S01", text: TEAM_CUE.text }] : []),
    ...lanes.filter((c) => now >= c.start && now < c.end).map((c) => ({ spk: "S00", text: c.text })),
  ];
  const ticks = [];
  for (let ms = 5200; ms <= 10400; ms += 200) ticks.push(ms);
  return (
    <div className="demo" {...demo.bind}>
      <AppFrame design={1280} fluidBelow={0.6} maxScale={1.3}>
        <div className="app demo-app tm">
          <div className="tm-bar">
            <b>{t("时间轴")}</b>
            <span className="app-chip square"><Icon name="zoomIn" size={12} />{t("放大 · {range} 秒", { range: "05.2 – 10.4" })}</span>
            <span className="sd-tools">
              <span className={"app-btn icon-only" + (aim || cut ? " quiet" : " soft")}><Icon name="cursor" size={15} /></span>
              <button className={"app-btn icon-only" + (aim ? " soft" : " quiet")} aria-label={t("在「{w}」后切开", { w: bare(words[CUT_AT - 1].text) })} onClick={() => { demo.take(); setAim(false); setCut(!cut); }}><Icon name="scissors" size={15} /></button>
            </span>
            <span className="grow" />
            <span className="app-chip square"><Spk id="S00" />{t("主播")}</span>
            <span className="app-chip square"><Spk id="S01" />{t("队友")}</span>
            <span className="app-field mono tm-tc">{timecode(now)}</span>
          </div>
          <div className="tm-top">
            <SignalArt className="tm-frame" tc={timecode(now).slice(0, 8) + ":" + String(Math.floor((now % 1000) / 40)).padStart(2, "0")}>
              <div className="tm-caps">
                {caps.map((c) => <span key={c.spk + c.text} className={"burned-caption tm-cap " + (c.spk === "S01" ? "s1" : "s0")}>{c.text}</span>)}
              </div>
            </SignalArt>
            <div className="tm-compare">
              <b>{t("同一句字幕，两种时间")}</b>
              <div className="tm-cmp">
                <span className="t3">{t("一般自动字幕 · 整句一段")}</span>
                <div className="tm-cmp-bar"><i style={{ left: 0, right: 0 }}>05.730 ──────────── 10.060</i></div>
              </div>
              <div className="tm-cmp">
                <span className="t3">{t("兔白字幕 · {n} 个字词，各有起止", { n: CUE_WORDS.length })}</span>
                <div className="tm-cmp-bar words">
                  {CUE_WORDS.map((w) => (
                    <i key={w.i} className={now >= w.start && now < w.end ? "on" : ""} style={{ left: `${((w.start - 5730) / 4330) * 100}%`, width: `${((w.end - w.start) / 4330) * 100}%` }} title={`${w.text} ${clock(w.start)}–${clock(w.end)}`} />
                  ))}
                </div>
              </div>
              <p className="t3">{t("切句时，刀口落在字与字之间，前后两段的时间自动接好，不用重新打轴。")}</p>
            </div>
          </div>
          <div className="tm-tl">
            <div className="tm-inner">
            <div className="tm-ruler">
              <span className="tm-label" />
              <div className="tm-track">
                {ticks.map((ms) => (
                  <i key={ms} className={ms % 1000 === 0 ? "major" : ""} style={{ left: at(ms) }}>
                    {ms % 1000 === 0 && <span className="mono">{clock(ms).slice(3)}</span>}
                  </i>
                ))}
              </div>
            </div>
            <div className="tm-row tm-words-row">
              <span className="tm-label">{t("字级")} <small>S00</small></span>
              <div className="tm-track">
                {CUE_WORDS.map((w) => (
                  <span key={w.i} className={"tm-word" + (now >= w.start && now < w.end ? " on" : "") + (w.i === CUT_AT && (aim || cut) ? " edge" : "")} style={span(w.start, w.end)}>
                    <b>{w.text}</b>
                    <small className="mono">{clock(w.start).slice(3)}</small>
                  </span>
                ))}
              </div>
            </div>
            <div className="tm-row">
              <span className="tm-label"><i className="dot s0" />A {t("主播")} <b>S00</b></span>
              <div className="tm-track">
                {lanes.map((c) => (
                  <span key={c.id} className={"tm-clip s0" + (now >= c.start && now < c.end ? " on" : "") + (c.id.startsWith("a") ? " cur" : "")} style={span(c.start, c.end)}>
                    {c.text}
                  </span>
                ))}
                {(aim || cut) && (
                  <span className={"tm-razor" + (cut ? " done" : "")} style={{ left: at(7290) }}>
                    <span className="tm-tip">{cut ? t("已切开 · 两段时间自动接好") : <>{t("在「{w}」后切开", { w: bare(words[CUT_AT - 1].text) })} · 00:07.290</>}</span>
                  </span>
                )}
              </div>
            </div>
            <div className="tm-row">
              <span className="tm-label"><i className="dot s1" />B {t("队友")} <b>S01</b></span>
              <div className="tm-track">
                <span className={"tm-clip s1" + (now >= TEAM_CUE.start && now < TEAM_CUE.end ? " on" : "")} style={span(TEAM_CUE.start, TEAM_CUE.end)}>{TEAM_CUE.text}</span>
              </div>
            </div>
            <div className="tm-row short">
              <span className="tm-label">A1 <small>{t("波形")}</small></span>
              <div className="tm-track"><WordWave /></div>
            </div>
            <span className="tm-head" style={{ "--x": (now - T0) / (T1 - T0) }} />
            </div>
          </div>
        </div>
      </AppFrame>
      <Resume demo={demo} />
    </div>
  );
}

/* ── 5. 导出字幕与压制成片 ─────────────────────────────────── */
function ExportDemo({ reduced }) {
  const demo = useDemo([1500, 900, 1400, 2400, 3000], reduced, 4);
  const [fmt, setFmt] = useState({ SRT: true, ASS: false, TXT: false, JSON: false });
  const s = demo.step;
  useEffect(() => {
    if (demo.manual) return;
    setFmt({ SRT: true, ASS: s >= 1, TXT: false, JSON: false });
  }, [s, demo.manual]);
  const exported = demo.manual ? false : s >= 2;
  const rendering = !demo.manual && s === 3;
  const done = demo.manual || s >= 4;
  const pct = rendering ? Math.min(100, Math.round((demo.ms / 2300) * 100)) : 100;
  const picked = Object.keys(fmt).filter((k) => fmt[k]);
  return frame(
    demo,
    <div className="app demo-app ex">
      <div className="app ex-dialog">
        <div className="ex-title">
          <Mascot size={22} />
          <b>{t("导出字幕")}</b>
          <span className="grow" />
          <Icon name="x" size={15} className="t3" />
        </div>
        <div className="ex-body">
          <span>{t("双人对话 · 示例素材")}</span>
          <span className="t3">{t("选择要导出的说话人。时间位置与空白均保留。")}</span>
          <span className="app-row"><Check on label={t("全部说话人")} />{t("全部说话人")}</span>
          <div className="ex-spk">
            <span className="app-row"><Check on label="S00" /><Spk id="S00" />{t("主播")} · {t("{n} 条字幕", { n: 5 })}</span>
            <span className="app-row"><Check on label="S01" /><Spk id="S01" />{t("队友")} · {t("1 条字幕")}</span>
          </div>
          <div className="ex-field"><span className="t3">{t("文件名")}</span><span className="app-field">{t("双人对话")}</span></div>
          <div className="ex-field">
            <span className="t3">{t("格式")}</span>
            <span className="ex-fmts">
              {Object.keys(fmt).map((k) => (
                <span key={k} className="app-row"><Check on={fmt[k]} label={k} onChange={(v) => { demo.take(); setFmt({ ...fmt, [k]: v }); }} />{k}</span>
              ))}
            </span>
          </div>
          <div className="ex-field"><span className="t3">{t("导出方式")}</span><span className="app-field">{t("合并文件")}<span className="grow" /><Icon name="chevDown" size={13} /></span></div>
        </div>
        <div className="ex-actions">
          {exported && <span className="ex-toast"><Icon name="check" size={13} />{t("已导出 {list}", { list: picked.join(" + ") })}</span>}
          <span className="grow" />
          <span className="app-btn primary">{t("选择目录并导出")}</span>
          <span className="app-btn">{t("取消")}</span>
        </div>
      </div>
      <div className="app ex-render">
        <div className="ex-rhead">
          {done ? <><span className="ex-ok"><Icon name="check" size={14} strokeWidth="2.6" /></span><b>{t("压制完成")}</b></> : <><Icon name="film" size={16} /><b>{rendering ? t("正在压制成片…") : t("压制成片")}</b></>}
          <span className="grow" />
          <span className="t3 mono">{rendering ? pct + "%" : ""}</span>
        </div>
        <SignalArt className="ex-thumb" tc="00:00:06:18">
          <div className="ex-caps"><span className="burned-caption">{phrase(9, 17)}</span></div>
          {done && <span className="ex-play"><Icon name="play" size={20} /></span>}
        </SignalArt>
        <div className="ex-bar"><i style={{ width: (rendering ? pct : done ? 100 : 0) + "%" }} /></div>
        <dl className="ex-info">
          {[[t("格式"), "H.264"], [t("分辨率"), "1920 × 1080"], [t("帧率"), "60 fps"], [t("时长"), "00:16"], [t("大小"), done ? "19.2 MB" : "—"], [t("平均码率"), done ? "9.6 Mb/s" : "—"]].map(([k, v]) => (
            <div key={k}><dt>{k}</dt><dd>{v}</dd></div>
          ))}
        </dl>
        <div className="ex-ractions">
          <span className={"app-btn" + (done ? " primary" : "")}><Icon name="play" size={13} />{t("播放成片")}</span>
          <span className="app-btn"><Icon name="folder" size={13} />{t("在文件夹中显示")}</span>
        </div>
      </div>
    </div>,
    800,
  );
}

/* ── sections ─────────────────────────────────────────────── */
const feature = (id, ink, tone, icons, Demo) =>
  function Feature({ reduced }) {
    const c = COPY[id];
    return (
      <Section
        id={id}
        ink={ink}
        tone={tone}
        reduced={reduced}
        title={rich(c.title)}
        lede={rich(c.lede)}
        points={c.points.map(([head, text], i) => [icons[i], head, rich(text)])}
      >
        <Demo reduced={reduced} />
      </Section>
    );
  };
export const ReviewFeature = feature("review", "var(--violet)", true, ["flag", "layers", "keyboard"], ReviewDemo);
export const ProofreadFeature = feature("proofread", "var(--apricot)", false, ["checkCircle", "book", "undo"], ProofreadDemo);
export const GlossaryFeature = feature("glossary", "var(--sea)", true, ["book", "plus", "globe"], GlossaryDemo);
export const TimingFeature = feature("timing", "var(--berry-tx)", false, ["users", "clock", "scissors"], TimingDemo);
export const ExportFeature = feature("export", "var(--mauve)", true, ["users", "film", "folder"], ExportDemo);
export { ReviewDemo, ProofreadDemo, GlossaryDemo, TimingDemo, ExportDemo };
