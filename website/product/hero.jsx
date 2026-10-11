import React, { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Icon } from "./icons.jsx";
import { Spk } from "./kit.jsx";
import { HomeWindow } from "./home-window.jsx";
import { StudioWindow } from "./studio.jsx";
import { VERSION } from "./data.js";
import { RECOGNIZED_CUTS } from "./demo.js";
import { useReveal } from "./motion.js";
import { COPY, rich } from "./i18n/index.jsx";
import { SAMPLE } from "./sample.js";
import "./hero.css";

const NOOP = () => {};
const STILL = { cuts: RECOGNIZED_CUTS, history: [] };
const STUDIO = { w: 1360, h: 812 };
const HOME = { w: 1180, h: 836 };

// Two real screens of the app in one 3D group. The group leans toward the pointer;
// the home window sits nearer the viewer, so the two layers part slightly (parallax).
function ProductStage({ reduced }) {
  const box = useRef(),
    group = useRef();
  const [w, setW] = useState(1200);
  const [hh, setHh] = useState({ studio: STUDIO.h, home: HOME.h });
  const studioRef = useRef(),
    homeRef = useRef();
  useLayoutEffect(() => {
    const read = () => {
      setW(box.current?.clientWidth || 1200);
      setHh({ studio: studioRef.current?.offsetHeight || STUDIO.h, home: homeRef.current?.offsetHeight || HOME.h });
    };
    read();
    const ro = new ResizeObserver(read);
    ro.observe(box.current);
    return () => ro.disconnect();
  }, []);
  useEffect(() => {
    const el = group.current;
    if (reduced || !matchMedia("(hover: hover) and (pointer: fine)").matches) {
      el.style.setProperty("--rx", "0deg");
      el.style.setProperty("--ry", "0deg");
      return;
    }
    let tx = 0, ty = 0, x = 0, y = 0, raf = 0;
    const move = (e) => {
      tx = (e.clientX / innerWidth) * 2 - 1;
      ty = (e.clientY / innerHeight) * 2 - 1;
      if (!raf) raf = requestAnimationFrame(tick);
    };
    const tick = () => {
      x += (tx - x) * 0.08;
      y += (ty - y) * 0.08;
      el.style.setProperty("--ry", (x * 7).toFixed(3) + "deg");
      el.style.setProperty("--rx", (-y * 4.5).toFixed(3) + "deg");
      raf = Math.abs(tx - x) + Math.abs(ty - y) > 0.001 ? requestAnimationFrame(tick) : 0;
    };
    addEventListener("pointermove", move, { passive: true });
    return () => (removeEventListener("pointermove", move), cancelAnimationFrame(raf));
  }, [reduced]);
  const narrow = w < 640;
  const sw = w * (narrow ? 1 : 0.8),
    ss = sw / STUDIO.w,
    hw = w * (narrow ? 0.62 : 0.47),
    hs = hw / HOME.w,
    drop = w * (narrow ? 0.4 : 0.2);
  const height = Math.max(hh.studio * ss, drop + hh.home * hs) + 56;
  return (
    <figure className="stage" ref={box} style={{ height }} aria-label={COPY.hero.stage}>
      <div className="stage-3d" ref={group}>
        <div className="layer back" style={{ left: w - sw, width: sw, height: hh.studio * ss }} inert="">
          <div style={{ width: STUDIO.w, transform: `scale(${ss})` }} className="layer-scale" ref={studioRef}>
            <StudioWindow editState={STILL} dispatch={NOOP} manual setManual={NOOP} initialSelected="a9" initialPlayhead={6100} />
          </div>
        </div>
        <div className="layer front" style={{ left: 0, top: drop, width: hw, height: hh.home * hs }} inert="">
          <div style={{ width: HOME.w, transform: `scale(${hs})` }} className="layer-scale" ref={homeRef}>
            <HomeWindow time={6100} />
          </div>
        </div>
      </div>
      <figcaption className="stage-labels">
        <span style={{ left: w - sw + 24, top: -40 }}>
          <b>{COPY.hero.studio[0]}</b>{COPY.hero.studio[1]}
        </span>
        <span style={{ left: 0, top: drop + hh.home * hs + 26 }}>
          <b>{COPY.hero.home[0]}</b>{COPY.hero.home[1]}
        </span>
      </figcaption>
    </figure>
  );
}

export function Hero({ reduced }) {
  return (
    <section className="hero" id="top">
      <div className="wrap">
        <div className="hero-head">
          <div>
            <h1 style={{ "--ch": "var(--berry-tx)" }}>{rich(COPY.hero.title)}</h1>
          </div>
          <div className="hero-side">
            <p className="hero-lede">{rich(COPY.hero.lede)}</p>
            <div className="hero-actions">
              <a className="btn primary" href="#download">
                <Icon name="download" size={18} />
                {COPY.hero.download}
              </a>
              <a className="btn" href="#compare">
                {COPY.hero.see}
                <Icon name="arrowDown" size={17} />
              </a>
            </div>
            <p className="hero-meta">
              {COPY.hero.meta.map((m) => (
                <span key={m}>{m}</span>
              ))}
              <span>{VERSION}</span>
            </p>
          </div>
        </div>
        <ProductStage reduced={reduced} />
      </div>
    </section>
  );
}

/* ── the difference, shown on one short clip ───────────────────────── */
const RAW = SAMPLE.raw;
const ROWS = [
  { t: "00:00.420", spk: "S00" },
  { t: "00:05.450", spk: "S01" },
  { t: "00:07.290", spk: "S00" },
  { t: "00:09.100", spk: "S01" },
  { t: "00:10.060", spk: "S00" },
].map((r, i) => ({ ...r, text: SAMPLE.rows[i] }));
const KEYS = ["spk", "time", "fix", "review"];

export function Compare({ reduced }) {
  const C = COPY.compare;
  const root = useRef();
  useReveal(root, reduced);
  return (
    <section id="compare" className="sec compare" ref={root} style={{ "--ch": "var(--berry-tx)" }} aria-labelledby="compare-title">
      <div className="wrap">
        <header className="sec-head solo" data-reveal>
          <div className="sec-main">
            <h2 className="sec-title" id="compare-title">
              {rich(C.title)}
            </h2>
            <p className="sec-lede">{rich(C.lede)}</p>
          </div>
        </header>
        <div className="cmp" data-reveal style={{ "--i": 1 }}>
          <div className="cmp-col raw">
            <div className="cmp-label">
              <b>{C.raw}</b>
              <span className="mono">{C.rawMeta}</span>
            </div>
            <p className="cmp-raw">
              {RAW.map((r, i) => (typeof r === "string" ? <span key={i}>{r}</span> : <u key={i}>{r.bad}</u>))}
            </p>
            <ul className="cmp-cons">
              {C.cons.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          </div>
          <div className="cmp-arrow" aria-hidden="true">
            <Icon name="arrowRight" size={22} />
          </div>
          <div className="cmp-col good">
            <div className="cmp-label">
              <b>{C.good}</b>
              <span className="mono">{C.goodMeta}</span>
            </div>
            <ol className="cmp-rows">
              {ROWS.map((r, i) => (
                <li key={r.t} className={"row-" + r.spk} style={{ "--i": i }}>
                  <span className="mono k-time">{r.t}</span>
                  <Spk id={r.spk} />
                  <span className="cmp-text">
                    {r.text.map((p, j) =>
                      typeof p === "string" ? (
                        <span key={j}>{p}</span>
                      ) : p.fix ? (
                        <mark key={j} className="k-fix">{p.fix}</mark>
                      ) : (
                        <mark key={j} className="k-review">{p.review}</mark>
                      ),
                    )}
                  </span>
                </li>
              ))}
            </ol>
          </div>
        </div>
        <ul className="cmp-keys" data-reveal style={{ "--i": 2 }}>
          {KEYS.map((k, i) => (
            <li key={k} className={"key-" + k}>
              <i aria-hidden="true" />
              <b>{C.keys[i][0]}</b>
              <span>{rich(C.keys[i][1])}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
