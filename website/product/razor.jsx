import React, { useMemo, useRef, useState } from "react";
import { t } from "./i18n/index.jsx";
import { Icon } from "./icons.jsx";
import { words, legalCuts, clock, bare } from "./sample.js";
import { DURATION, timecode } from "./data.js";

const pct = (ms) => `${(ms / DURATION) * 100}%`;

// A1 waveform drawn from the sample's own speech timing: loud inside words,
// quiet in the gaps. Deterministic, so every visit looks the same.
function Waveform({ team }) {
  const bars = useMemo(() => {
    const out = [];
    let seed = 7;
    const rnd = () => ((seed = (seed * 9301 + 49297) % 233280) / 233280);
    for (let t = 0; t < DURATION; t += 70) {
      const inWord = words.some((w) => t >= w.start && t < w.end) || (t >= team.start && t < team.end);
      out.push(inWord ? 0.35 + rnd() * 0.65 : 0.05 + rnd() * 0.08);
    }
    return out;
  }, [team]);
  return (
    <svg className="wave" viewBox={`0 0 ${bars.length} 100`} preserveAspectRatio="none" aria-hidden="true">
      {bars.map((a, i) => (
        <rect key={i} x={i + 0.15} width="0.7" y={50 - a * 46} height={a * 92} rx="0.3" />
      ))}
    </svg>
  );
}

// Multi-track timeline with a razor that only cuts at known word boundaries.
// Split rules live in edit-model.js (manual split contract of the desktop app).
export function Timeline({ cues, team, cuts, dispatch, tool, playhead, onSeek, selectedId, onSelect, onManual, thumbs, ghost = null }) {
  const lane = useRef();
  const [hoverAt, setHover] = useState(null); // word index of the boundary under the razor
  const hover = hoverAt ?? (tool === "razor" ? ghost : null);
  const legal = legalCuts(cuts);
  const nearest = (clientX) => {
    const r = lane.current.getBoundingClientRect();
    const t = ((clientX - r.left) / r.width) * DURATION;
    let best = null;
    for (const i of legal) {
      const d = Math.abs(words[i].start - t);
      if (d < 600 && (!best || d < best.d)) best = { i, d };
    }
    return best?.i ?? null;
  };
  const timeAt = (clientX) => {
    const r = lane.current.getBoundingClientRect();
    return Math.max(0, Math.min(DURATION, ((clientX - r.left) / r.width) * DURATION));
  };
  const cutAt = (i) => {
    if (i == null) return;
    onManual?.();
    dispatch({ type: "split", at: i });
    setHover(null);
  };
  const key = (e) => {
    if (tool !== "razor" || !["ArrowLeft", "ArrowRight", "Home", "End", "Enter", " "].includes(e.key)) return;
    e.preventDefault();
    onManual?.();
    if (e.key === "Enter" || e.key === " ") return cutAt(hover);
    const cur = hover ?? legal[0];
    const next =
      e.key === "Home" ? legal[0] : e.key === "End" ? legal.at(-1)
        : e.key === "ArrowRight" ? legal.find((i) => i > cur) ?? legal.at(-1)
          : [...legal].reverse().find((i) => i < cur) ?? legal[0];
    setHover(next);
  };
  const ticks = Array.from({ length: DURATION / 500 + 1 }, (_, i) => i * 500);
  return (
    <div className={"tl tool-" + tool}>
      <div className="tl-ruler" onPointerDown={(e) => { onManual?.(); onSeek(timeAt(e.clientX)); }}>
        <span className="tl-label" />
        <div className="tl-ticks" ref={lane}>
          {ticks.map((ms) => (
            <i key={ms} className={ms % 2000 === 0 ? "major" : ""} style={{ left: pct(ms) }}>
              {ms % 2000 === 0 && <span className="mono">{timecode(ms).slice(3, 8)}</span>}
            </i>
          ))}
          <span className="tl-head-chip mono" style={{ left: pct(playhead) }}>{timecode(playhead).slice(3)}</span>
        </div>
      </div>
      <div className="tl-tracks">
        <div className="tl-track">
          <span className="tl-label"><i className="dot s0" />A <b>S00</b><span className="tl-icons"><Icon name="eye" size={13} /><Icon name="lock" size={13} /></span></span>
          <div
            className="tl-lane"
            tabIndex={0}
            role="group"
            aria-label={tool === "razor" ? t("字幕轨 A。左右键选择字词边界，回车切开") : t("字幕轨 A")}
            onKeyDown={key}
            onPointerMove={(e) => tool === "razor" && e.pointerType === "mouse" && setHover(nearest(e.clientX))}
            onPointerLeave={() => tool === "razor" && setHover(null)}
            onClick={(e) => {
              if (tool === "razor") cutAt(nearest(e.clientX));
              else {
                onManual?.();
                onSeek(timeAt(e.clientX));
              }
            }}
          >
            {cues.map((c, n) => (
              <button
                type="button"
                key={c.id}
                className={"clip s0" + (selectedId === c.id ? " is-sel" : "")}
                style={{ left: pct(c.start), width: pct(c.end - c.start) }}
                onClick={(e) => {
                  if (tool === "razor") return;
                  e.stopPropagation();
                  onManual?.();
                  onSelect(c.id, true);
                }}
                tabIndex={-1}
              >
                <span className="clip-text">{c.text}</span>
              </button>
            ))}
            {tool === "razor" &&
              words.slice(1).map((w) => (
                <i key={w.i} className={"word-tick" + (legal.includes(w.i) ? "" : " is-used")} style={{ left: pct(w.start) }} />
              ))}
            {tool === "razor" && hover != null && (
              <span className="razor-line" style={{ left: pct(words[hover].start) }}>
                <span className="razor-tip">
                  {t("在「{w}」后切开", { w: bare(words[hover - 1].text) })} · <span className="mono">{clock(words[hover].start)}</span>
                </span>
              </span>
            )}
          </div>
        </div>
        <div className="tl-track">
          <span className="tl-label"><i className="dot s1" />B <b>S01</b><span className="tl-icons"><Icon name="eye" size={13} /><Icon name="lock" size={13} /></span></span>
          <div className="tl-lane">
            <button
              type="button"
              className={"clip s1" + (selectedId === team.id ? " is-sel" : "")}
              style={{ left: pct(team.start), width: pct(team.end - team.start) }}
              onClick={() => {
                onManual?.();
                onSelect(team.id, true);
              }}
              tabIndex={-1}
            >
              <span className="clip-text">{team.text}</span>
            </button>
          </div>
        </div>
        <div className="tl-track">
          <span className="tl-label"><span className="tl-v">V1</span><small>{t("主画面 · 底层")}</small></span>
          <div className="tl-lane">
            <span className="clip video" style={{ left: 0, width: "100%", backgroundImage: `url(${thumbs})` }}>
              <span className="clip-text">{t("双人对话 · 示例画面.mp4")}</span>
            </span>
          </div>
        </div>
        <div className="tl-track short">
          <span className="tl-label">A1 <small>{t("波形")}</small><span className="tl-icons"><Icon name="volume" size={13} /></span></span>
          <div className="tl-lane">
            <Waveform team={team} />
          </div>
        </div>
        <div className="tl-playhead" style={{ "--x": playhead / DURATION }} />
      </div>
    </div>
  );
}
