import React, { useEffect, useMemo, useState } from "react";
import { Icon } from "./icons.jsx";
import { AppFrame, Chip, SignalArt, Spk } from "./kit.jsx";
import { Timeline } from "./razor.jsx";
import { A, DURATION, asset, timecode } from "./data.js";
import { SAMPLE, TEAM_CUE, fragments, REVIEW_AT } from "./sample.js";
import { t } from "./i18n/index.jsx";
import "./studio.css";

const BASE_STYLE = { size: 84, fill: "#ffffff", stroke: 7.9, outline: "#000000", shadow: true };
const FILLS = ["#ffffff", "#ffe08a", "#f5b8d0", "#b9a6ee", "#9fd3ff"];
const SCOPES = [["current", t("当前")], ["picked", t("已选 {n}", { n: 1 })], ["speaker", t("说话人")], ["all", t("全部")]];

function StyleTab({ style, setStyle, scope, setScope, sample }) {
  return (
    <div className="st-pane">
      <div className="app-row st-scope">
        <span className="t3">{t("应用到")}</span>
        {SCOPES.map(([k, l]) => (
          <button key={k} className={"app-btn" + (scope === k ? " soft" : "")} onClick={() => setScope(k)} aria-pressed={scope === k}>{l}</button>
        ))}
      </div>
      <div className="st-sample">
        <span className="burned-caption st-sample-text" style={{ position: "static", ...captionCss(style, 0.24) }}>{sample}</span>
        <span className="app-chip square st-aa">Aa</span>
      </div>
      <div className="st-row"><span className="t3">{t("预设")}</span><span className="app-field grow">{t("2Byte 默认")}<span className="grow" /><Icon name="chevDown" size={13} /></span><span className="app-btn soft">{t("样式库")}</span></div>
      <div className="st-section"><Icon name="chevDown" size={12} />{t("文字")}</div>
      <div className="st-row"><span className="t3">{t("字体")}</span><span className="app-field grow">{t("思源黑体 Heavy")}<span className="grow" /><Icon name="chevDown" size={13} /></span></div>
      <div className="st-row">
        <span className="t3">{t("字号")}</span>
        <span className="app-field st-num mono">{style.size}</span>
        <input type="range" min="56" max="120" value={style.size} aria-label={t("字号")} onChange={(e) => setStyle({ size: +e.target.value })} />
      </div>
      <div className="st-section"><Icon name="chevDown" size={12} />{t("外观")}</div>
      <div className="st-row">
        <span className="t3">{t("填充")}</span>
        {FILLS.map((c) => (
          <button key={c} className={"st-swatch" + (style.fill === c ? " is-on" : "")} style={{ background: c }} aria-label={t("填充色 {c}", { c })} onClick={() => setStyle({ fill: c })} />
        ))}
      </div>
      <div className="st-row">
        <span className="t3">{t("描边")}</span>
        <button className={"st-swatch" + (style.outline === "#000000" ? " is-on" : "")} style={{ background: "#000" }} aria-label={t("黑色描边")} onClick={() => setStyle({ outline: "#000000" })} />
        <button className={"st-swatch" + (style.outline === "#5b2440" ? " is-on" : "")} style={{ background: "#5b2440" }} aria-label={t("酒红描边")} onClick={() => setStyle({ outline: "#5b2440" })} />
        <span className="t3">{t("宽度")}</span>
        <span className="app-field st-num mono">{style.stroke.toFixed(1)}</span>
        <input type="range" min="0" max="14" step="0.1" value={style.stroke} aria-label={t("描边宽度")} onChange={(e) => setStyle({ stroke: +e.target.value })} />
      </div>
      <div className="st-row">
        <span className="t3">{t("阴影")}</span>
        <button className={"app-btn" + (style.shadow ? " soft" : "")} onClick={() => setStyle({ shadow: !style.shadow })} aria-pressed={style.shadow}>{style.shadow ? t("开启") : t("关闭|off")}</button>
        <span className="t3 st-note">{t("不透明度 57% · 距离 4px")}</span>
      </div>
    </div>
  );
}

// k: px per 1080p pixel; "cqw" renders relative to the preview frame width.
const captionCss = (s, k) => {
  const u = (v) => (k === "cqw" ? `${(v / 19.2).toFixed(3)}cqw` : `${v * k}px`);
  return {
    fontSize: u(s.size),
    color: s.fill,
    WebkitTextStroke: `${u(s.stroke * 2)} ${s.outline}`,
    textShadow: s.shadow ? `0 ${u(4)} ${u(6)} rgba(0,0,0,.57)` : "none",
  };
};

function OtherTab({ tab }) {
  if (tab === "ai")
    return (
      <div className="st-pane">
        <b>{t("AI 字幕设计")}</b>
        <p className="t3 st-p">{t("先描述字幕视觉要求，再生成三套可编辑的视觉与动效方案。")}</p>
        <span className="app-field st-prompt">{t("木刻压印，叠置木板，收拢退场")}</span>
        <a className="app-btn primary" href="#create"><Icon name="sparkle" size={13} />{t("看两件作品")}</a>
      </div>
    );
  if (tab === "clips")
    return (
      <div className="st-pane">
        <b>{t("剪辑助手 · {n} 条候选", { n: 3 })}</b>
        {[t("翻车后嘴硬，弹幕全在笑"), t("残血反杀，直播间瞬间炸了"), t("弹幕高峰，整屏都在刷同一句")].map((c) => (
          <span key={c} className="st-clip">{c}</span>
        ))}
        <a className="app-btn" href="#create">{t("展开剪辑助手")}</a>
      </div>
    );
  if (tab === "video")
    return (
      <div className="st-pane">
        <b>{t("画面")}</b>
        <div className="st-row"><span className="t3">{t("画幅")}</span><span className="app-field grow">16 : 9 · {t("示例画面")}</span></div>
        <div className="st-row"><span className="t3">{t("缩放")}</span><span className="app-field st-num mono">100%</span></div>
        <div className="st-row"><span className="t3">{t("位置")}</span><span className="app-field st-num mono">0, 0</span></div>
        <p className="t3 st-p">{t("成片的分辨率、帧率与码率在“压制成片”里选择。")}</p>
      </div>
    );
  return (
    <div className="st-pane">
      <b>{t("素材")}</b>
      <span className="st-clip"><Icon name="film" size={14} />{t("双人对话 · 示例画面.mp4")}</span>
      <span className="st-clip"><Icon name="volume" size={14} />{t("示例音轨 · 16 秒")}</span>
      <p className="t3 st-p">{t("把素材拖到时间轴即可加入新轨道。")}</p>
    </div>
  );
}

export function StudioWindow({ editState, dispatch, review = null, reduced, demo, manual, setManual, initialSelected = "a0", initialPlayhead = 400 }) {
  const texts = review == null ? {} : { [REVIEW_AT]: SAMPLE.readings[review] };
  const cues = useMemo(() => fragments(editState.cuts, texts).map((f) => ({ ...f, id: "a" + f.from, speaker: "S00" })), [editState.cuts, review]);
  const list = useMemo(() => [...cues, TEAM_CUE].sort((a, b) => a.start - b.start), [cues]);
  const [selectedId, setSelectedId] = useState(initialSelected);
  const [playhead, setPlayhead] = useState(initialPlayhead);
  const [tool, setTool] = useState("select");
  const [tab, setTab] = useState("style");
  const [playing, setPlaying] = useState(false);
  const [scope, setScope] = useState("all");
  const [global, setGlobal] = useState(BASE_STYLE);
  const [overrides, setOverrides] = useState({});
  const selected = list.find((c) => c.id === selectedId) || list[0];
  const styleOf = (c) => overrides[c.id] || global;
  const take = () => !manual && setManual(true);
  const select = (id, seek) => {
    setSelectedId(id);
    const c = list.find((x) => x.id === id);
    if (c && seek) setPlayhead(c.start + 10);
  };
  const seek = (t) => {
    setPlayhead(t);
    const hit = list.find((c) => t >= c.start && t < c.end && c.speaker === "S00") || list.find((c) => t >= c.start && t < c.end);
    if (hit) setSelectedId(hit.id);
  };
  const setStyle = (patch) => {
    take();
    if (scope === "all") {
      setGlobal((g) => ({ ...g, ...patch }));
      setOverrides({});
    } else {
      const ids = scope === "speaker" ? list.filter((c) => c.speaker === selected.speaker).map((c) => c.id) : [selected.id];
      setOverrides((o) => Object.fromEntries([...Object.entries(o), ...ids.map((id) => [id, { ...(o[id] || global), ...patch }])]));
    }
  };
  // keep a valid selection after cuts and merges
  useEffect(() => {
    if (!list.some((c) => c.id === selectedId)) {
      const c = list.find((x) => playhead >= x.start && playhead < x.end && x.speaker === "S00") || list[0];
      setSelectedId(c.id);
    }
  }, [list]);
  // the looping demo drives the replica until the visitor takes over
  const key = demo?.key, ms = demo?.ms || 0;
  const beat = key === "select" ? Math.floor(ms / 1500) : key === "style" ? (ms > 900) + (ms > 1900) + (ms > 2900) : ms < 120 ? 0 : 1;
  useEffect(() => {
    if (manual || !key) return;
    const at = (id) => list.find((x) => x.id === id) || list[0];
    if (key === "select") {
      setPlaying(false);
      setTool("select");
      setTab("style");
      setScope("all");
      setGlobal(BASE_STYLE);
      setOverrides({});
      const c = at(["a0", "b", "a9"][Math.min(2, beat)]);
      setSelectedId(c.id);
      setPlayhead(c.start + 300);
    }
    if (key === "style") {
      setPlaying(false);
      setTab("style");
      setScope("all");
      const c = at("a9");
      setSelectedId(c.id);
      setPlayhead(c.start + 300);
      setGlobal({ ...BASE_STYLE, fill: beat > 0 ? "#ffe08a" : BASE_STYLE.fill, size: beat > 1 ? 100 : BASE_STYLE.size, stroke: beat > 2 ? 10 : BASE_STYLE.stroke });
      setOverrides({});
    }
    if (key === "play" && beat === 0) {
      setPlayhead(3300);
      setPlaying(true);
    }
  }, [key, beat, manual]);
  // playback
  useEffect(() => {
    if (!playing) return;
    let raf, last = performance.now();
    const tick = (now) => {
      setPlayhead((p) => {
        const next = p + (now - last);
        last = now;
        if (next >= DURATION) {
          setPlaying(false);
          return DURATION;
        }
        return next;
      });
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing]);
  useEffect(() => {
    if (!playing) return;
    const hit = list.find((c) => playhead >= c.start && playhead < c.end && c.speaker === "S00");
    if (hit && hit.id !== selectedId) setSelectedId(hit.id);
  }, [playhead, playing]);
  const active = list.filter((c) => playhead >= c.start && playhead < c.end);
  const shown = active.length ? active : [];
  const idx = list.findIndex((c) => c.id === selected.id);
  const canMerge = selected.speaker === "S00" && selected.from > 0 && editState.cuts.includes(selected.from);
  const thumbs = asset(A + "product/dialogue-frame.webp");
  return (
    <div
      className="app studio-app"
      onPointerDown={take}
      onKeyDown={(e) => {
        take();
        if (e.key === " " && e.target === e.currentTarget) {
          e.preventDefault();
          setPlaying((p) => !p);
        }
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") {
          e.preventDefault();
          dispatch({ type: "undo" });
        }
      }}
      tabIndex={-1}
    >
      <div className="sd-bar">
        <Icon name="arrowLeft" size={17} />
        <b>{t("双人对话")}</b>
        <span className="t3">{t("示例工程")}</span>
        <span className="grow" />
        <span className="sd-icons t2" aria-hidden="true">
          <Icon name="home" size={17} /><Icon name="grid" size={17} /><Icon name="plus" size={17} /><Icon name="gear" size={17} /><Icon name="save" size={17} />
        </span>
        <button className="app-btn quiet icon-only" aria-label={t("撤销")} disabled={!editState.history.length} onClick={() => dispatch({ type: "undo" })}><Icon name="undo" size={17} /></button>
        <span className="app-btn quiet icon-only t3" aria-hidden="true"><Icon name="redo" size={17} /></span>
        <span className="app-btn on"><Icon name="list" size={14} />{t("字幕列表")}</span>
        <span className="app-btn on"><Icon name="panel" size={14} />{t("工具面板")}</span>
        <span className="app-btn quiet"><Icon name="swap" size={14} />{t("批量替换")}</span>
        <span className="app-btn quiet"><Icon name="users" size={14} />{t("说话人管理 · 待确认")}</span>
        <span className="app-btn quiet"><Icon name="export" size={14} />{t("导出字幕")}</span>
        <span className="app-btn primary"><Icon name="film" size={14} />{t("压制成片")}</span>
      </div>
      <div className="sd-hint t3">{t("Space：播放 / 暂停　Q / W：播放头前 / 后波纹剪切　双击时间轴字幕：直接编辑　Ctrl+Z：撤销")}</div>
      <div className="sd-upper">
        <aside className="sd-list">
          <b className="sd-panel-title">{t("字幕列表")}</b>
          <div className="sd-filters">
            <span className="app-btn soft">{t("全部 {n}", { n: list.length })}</span>
            <span className="app-btn">{t("建议确认 {n}", { n: 2 })}</span>
            <span className="app-btn">{t("需要检查 {n}", { n: review === null ? 1 : 0 })}</span>
            <span className="app-btn"><Icon name="play" size={10} />{t("开始审核")}</span>
          </div>
          <span className="app-field sd-search"><Icon name="search" size={14} />{t("搜索文本、说话人…")}<span className="grow" /><Icon name="filter" size={14} /></span>
          <div className="sd-th t3"><span>#</span><span>{t("开始时间")}</span><span>{t("说话人")}</span><span>{t("文本")}</span><span>{t("状态")}</span></div>
          <div className="sd-rows">
            {list.map((c, i) => {
              const done = c.speaker === "S01" || (review !== null && c.from <= 16 && c.to > 16);
              return (
                <button key={c.id} className={"sd-tr" + (c.id === selected.id ? " is-sel" : "")} onClick={() => { take(); select(c.id, true); }}>
                  <span className="t3">{i + 1}</span>
                  <span className="mono">{timecode(c.start).slice(3)}</span>
                  <Spk id={c.speaker} />
                  <span className="sd-text">{c.text}</span>
                  <span className={done ? "ok" : "warn"}>{done ? t("已完成") : t("待确认")}</span>
                </button>
              );
            })}
          </div>
          <div className="sd-jump">
            <span className="t3">{t("跳转")}</span>
            <span className="app-field mono">{idx + 1}</span>
            <span className="t3">/ {list.length}</span>
            <span className="grow" />
            <button className="app-btn" disabled={idx <= 0} onClick={() => { take(); select(list[idx - 1].id, true); }}>{t("上一条")}</button>
            <button className="app-btn" disabled={idx >= list.length - 1} onClick={() => { take(); select(list[idx + 1].id, true); }}>{t("下一条")}</button>
          </div>
        </aside>
        <div className="sd-preview">
          <SignalArt className="sd-scene" tc={timecode(playhead).slice(0, 8) + ":" + String(Math.floor((playhead % 1000) / 40)).padStart(2, "0")}>
            <div className="sd-captions">
              {shown.map((c) => (
                <span key={c.id} className={"burned-caption sd-cap" + (c.id === selected.id ? " is-sel" : "")} style={captionCss(styleOf(c), "cqw")}>
                  {c.text}
                  {c.id === selected.id && (
                    <span className="sd-handles" aria-hidden="true">
                      <i /><i /><i /><i /><i /><i /><i /><i />
                    </span>
                  )}
                </span>
              ))}
            </div>
          </SignalArt>
        </div>
        <aside className="sd-tool">
          <div className="app-row sd-tool-head"><b className="sd-panel-title">{t("工具面板")}</b><span className="grow" /><Icon name="chevRight" size={15} className="t3" /></div>
          <div className="app-tabs" role="tablist">
            {[["ai", "sparkle", t("AI设计")], ["style", "palette", t("样式")], ["video", "fit", t("视频")], ["clips", "scissors", t("剪辑助手")], ["assets", "image", t("素材")]].map(([k, ic, l]) => (
              <button key={k} role="tab" aria-selected={tab === k} onClick={() => { take(); setTab(k); }}>
                <Icon name={ic} size={14} />{l}
              </button>
            ))}
          </div>
          {tab === "style" ? (
            <StyleTab style={styleOf(selected)} setStyle={setStyle} scope={scope} setScope={(s) => { take(); setScope(s); }} sample={selected.text} />
          ) : (
            <OtherTab tab={tab} />
          )}
        </aside>
      </div>
      <div className="sd-tlbar">
        <b>{t("时间轴")}</b>
        <span className="sd-icons t2" aria-hidden="true"><Icon name="image" size={16} /><Icon name="layers" size={16} /><Icon name="cc" size={16} /></span>
        <span className="app-btn quiet"><Icon name="plus" size={14} />{t("添加字幕")}</span>
        <div className="sd-tools" role="radiogroup" aria-label={t("时间轴工具")}>
          <button role="radio" aria-checked={tool === "select"} className={"app-btn icon-only" + (tool === "select" ? " soft" : " quiet")} aria-label={t("选择工具")} onClick={() => { take(); setTool("select"); }}><Icon name="cursor" size={16} /></button>
          <button role="radio" aria-checked={tool === "razor"} className={"app-btn icon-only" + (tool === "razor" ? " soft" : " quiet")} aria-label={t("剃刀工具")} onClick={() => { take(); setTool("razor"); }}><Icon name="scissors" size={16} /></button>
        </div>
        {canMerge && (
          <button className="app-btn" onClick={() => { take(); dispatch({ type: "merge", at: selected.from }); }}><Icon name="merge" size={14} />{t("与前段合并")}</button>
        )}
        <span className="grow" />
        <button className="app-btn quiet icon-only" aria-label={t("上一条字幕")} onClick={() => { take(); idx > 0 && select(list[idx - 1].id, true); }}><Icon name="skipBack" size={16} /></button>
        <button className="app-btn icon-only sd-play" aria-label={playing ? t("暂停") : t("播放")} onClick={() => { take(); if (playhead >= DURATION - 50) setPlayhead(0); setPlaying(!playing); }}><Icon name={playing ? "pause" : "play"} size={16} /></button>
        <button className="app-btn quiet icon-only" aria-label={t("下一条字幕")} onClick={() => { take(); idx < list.length - 1 && select(list[idx + 1].id, true); }}><Icon name="skipFwd" size={16} /></button>
        <span className="app-field mono sd-tc">{timecode(playhead)}</span>
        <span className="t3 mono">/ 0:16 · 1x</span>
        <span className="grow" />
        <span className="sd-icons t2" aria-hidden="true"><Icon name="zoomOut" size={16} /><Icon name="zoomIn" size={16} /><Icon name="fit" size={16} /></span>
        <span className="app-chip square"><Icon name="bars" size={12} />{t("波形")}</span>
        <span className="app-chip square"><Icon name="image" size={12} />{t("缩略图")}</span>
        <span className="app-chip square"><Icon name="target" size={12} />{t("跟随")}</span>
        <span className="app-chip square"><Icon name="magnet" size={12} />{t("吸附")}</span>
      </div>
      <Timeline
        cues={cues}
        team={TEAM_CUE}
        cuts={editState.cuts}
        dispatch={dispatch}
        tool={tool}
        playhead={playhead}
        onSeek={seek}
        selectedId={selected.id}
        onSelect={select}
        onManual={take}
        thumbs={thumbs}
      />
    </div>
  );
}
