import React, { useId, useLayoutEffect, useRef, useState } from "react";
import { Icon } from "./icons.jsx";
import { asset, BRAND, ROLES, shortName, sizeLabel } from "./data.js";
import { LANG, LANGS, t } from "./i18n/index.jsx";
import "./kit.css";

// A replica designed at a fixed width, scaled down to its column. Below
// `fluidBelow` it stops scaling and reflows (class is-fluid) so text stays legible.
export function AppFrame({ design = 1200, fluidBelow = 0.55, maxScale = 1, className = "", children }) {
  const outer = useRef(),
    inner = useRef();
  const [box, setBox] = useState({ scale: 1, h: 0, fluid: false });
  useLayoutEffect(() => {
    const read = () => {
      const w = outer.current?.clientWidth || design;
      const scale = Math.min(maxScale, w / design);
      const fluid = scale < fluidBelow;
      const h = inner.current?.offsetHeight || 0;
      setBox((o) => (o.scale === scale && o.h === h && o.fluid === fluid ? o : { scale, h, fluid }));
    };
    read();
    const ro = new ResizeObserver(read);
    ro.observe(outer.current);
    ro.observe(inner.current);
    return () => ro.disconnect();
  }, [design, fluidBelow, maxScale]);
  return (
    <div
      ref={outer}
      className={"app-frame " + (box.fluid ? "is-fluid " : "") + className}
      style={box.fluid ? undefined : { height: box.h * box.scale || undefined }}
      data-scale={box.fluid ? 1 : box.scale.toFixed(3)}
    >
      <div
        ref={inner}
        className="app-frame-inner"
        style={box.fluid ? undefined : { width: design, transform: `scale(${box.scale})` }}
      >
        {children}
      </div>
    </div>
  );
}

export const Mascot = ({ size = 40, alt = "" }) => (
  <img src={asset(BRAND)} width={size} height={size} alt={alt} style={{ objectFit: "contain" }} />
);

export function BrandBar({ tools = DEFAULT_TOOLS, title = "兔白字幕" }) {
  return (
    <header className="app-brandbar">
      <Mascot size={42} />
      <div className="wordmark">
        <span>2ByteASR</span>
        <span lang="zh-CN">{title}</span>
      </div>
      <div className="tools" aria-hidden="true">
        {tools.map(([icon, label]) => (
          <span className="app-btn" key={label}>
            <Icon name={icon} size={14} />
            {label}
          </span>
        ))}
        <span className="app-btn">
          {LANGS.find(([k]) => k === LANG)[1]} <Icon name="chevDown" size={13} />
        </span>
      </div>
    </header>
  );
}
const DEFAULT_TOOLS = [
  ["heart", t("支持我!")],
  ["refresh", t("检查更新")],
  ["cc", t("字幕工作台")],
  ["cube", t("模型工坊")],
  ["gear", t("设置")],
];

export const Chip = ({ tone = "", icon, children, className = "" }) => (
  <span className={`app-chip ${tone} ${className}`}>
    {icon && <Icon name={icon} size={12} />}
    {children}
  </span>
);
export const Spk = ({ id = "S00" }) => (
  <span className={"spk " + ({ S00: "s0", S01: "s1", S02: "s2" }[id] || "s0")}>{id}</span>
);
export const Toggle = ({ on, onChange, label }) => (
  <button type="button" role="switch" aria-checked={!!on} aria-label={label} className="app-toggle" onClick={() => onChange?.(!on)} />
);
export const Check = ({ on, onChange, label }) => (
  <button type="button" role="checkbox" aria-checked={!!on} aria-label={label} className="app-check" onClick={() => onChange?.(!on)}>
    {on && <Icon name="check" size={12} strokeWidth="2.6" />}
  </button>
);

// One recognition role card, as on the desktop home (2026-10-08 layout).
export function RoleCard({ role, model, onClick, active, compact = false, as = "button" }) {
  const r = ROLES[role];
  const Tag = as;
  const off = !model;
  return (
    <Tag
      type={as === "button" ? "button" : undefined}
      className={"role-card" + (active ? " is-active" : "") + (off ? " is-off" : "") + (compact ? " compact" : "")}
      style={{ "--role": r.color }}
      onClick={onClick}
      aria-label={as === "button" ? t("{role}：{model}，点击更换", { role: r.label, model: shortName(model) }) : undefined}
    >
      <span className="app-tile" style={{ "--tile": r.color }}>
        <Icon name={r.icon} size={compact ? 17 : 20} strokeWidth="2.1" />
      </span>
      <span className="role-label">{r.label}</span>
      <b className="role-model" key={model?.key || "off"}>
        {shortName(model)}
      </b>
      <span className="role-desc">{r.desc}</span>
      <span className="role-foot">
        {off ? (
          <span className="app-chip">{t("已关闭")}</span>
        ) : (
          <>
            <span className="app-chip">{model.online ? t("在线") : t("本地")}</span>
            <span className="t3 role-size">{sizeLabel(model)}</span>
          </>
        )}
      </span>
      <span className="role-more t3">
        <span>{t("点击更换")}</span>
        <span>
          {t("详情")} <Icon name="chevRight" size={12} />
        </span>
      </span>
    </Tag>
  );
}

// Neutral media placeholder: a muted broadcast test card ("no signal"), so the
// interface stays the subject. Sizes use container units (.signal is a size container).
const BARS = ["#8f8d93", "#9a9466", "#5f8f91", "#628c66", "#8a6586", "#8f6264", "#61689a"];
export function SignalArt({ className = "", label = t("示例素材"), tc = "00:00:07:12", children }) {
  const id = "scan" + useId().replace(/[^a-zA-Z0-9]/g, "");
  return (
    <div className={"signal " + className}>
      <svg viewBox="0 0 1600 900" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
        <defs>
          <pattern id={id} width="4" height="4" patternUnits="userSpaceOnUse">
            <rect width="4" height="1" fill="#000" opacity=".22" />
          </pattern>
        </defs>
        <rect width="1600" height="900" fill="#141217" />
        {BARS.map((c, i) => (
          <rect key={c} x={(i * 1600) / 7} width={1600 / 7 + 1} height="590" fill={c} opacity=".42" />
        ))}
        {[...BARS].reverse().map((c, i) => (
          <rect key={"r" + c} x={(i * 1600) / 7} y="590" width={1600 / 7 + 1} height="70" fill={c} opacity=".26" />
        ))}
        {["#2a3550", "#c9c9cc", "#3b2c52", "#121014"].map((c, i) => (
          <rect key={"b" + c} x={i * 286} y="660" width="287" height="240" fill={c} opacity={i === 1 ? 0.28 : 0.9} />
        ))}
        <rect x="1144" y="660" width="456" height="240" fill="#16141a" />
        {[0, 1, 2].map((i) => (
          <rect key={"p" + i} x={1190 + i * 60} y="700" width="40" height="160" fill="#fff" opacity={0.04 + i * 0.05} />
        ))}
        <rect width="1600" height="900" fill="#0d0b10" opacity=".38" />
        <circle cx="800" cy="420" r="250" fill="none" stroke="#fff" strokeOpacity=".16" strokeWidth="3" />
        <path d="M800 140v560M520 420h560" stroke="#fff" strokeOpacity=".12" strokeWidth="2" />
        <rect width="1600" height="900" fill={`url(#${id})`} />
      </svg>
      <span className="signal-ch mono">CH 02 · {label}</span>
      <span className="signal-tc mono">{tc}</span>
      <span className="signal-badge">
        <b className="mono">NO SIGNAL</b>
        <span>{t("无信号 · 字幕演示")}</span>
      </span>
      {children}
    </div>
  );
}
