import React, { useRef, useState } from "react";
import { Icon } from "./icons.jsx";
import { Chip, RoleCard } from "./kit.jsx";
import { A, PLANS, ROLES, ROLE_KEYS, asset, catalog, matchPlan, modelFor, planSelection, shortName, sizeLabel } from "./data.js";
import { COPY, t } from "./i18n/index.jsx";
import "./plans.css";

const RECOMMENDED = { primary: "moss", timeline: "firered", review: "qwen_local" };

export function ModelLogo({ model, size = 30 }) {
  if (model?.logo_asset)
    return <img className="model-logo" src={asset(A + "model-logos/" + model.logo_asset)} width={size} height={size} alt="" />;
  const letters = (model?.name || "API").replace(/[^A-Za-z0-9]/g, "").slice(0, 2).toUpperCase();
  return (
    <span className="model-logo mono-logo" style={{ width: size, height: size }} aria-hidden="true">
      {letters}
    </span>
  );
}

export function ModelPicker({ role, selected, onPick, onClose }) {
  const [q, setQ] = useState("");
  const list = catalog.models
    .filter((m) => m.roles.includes(role))
    .filter((m) => `${m.name} ${t(m.name)} ${m.key} ${m.summary} ${t(m.summary)}`.toLowerCase().includes(q.toLowerCase()))
    .sort(
      (a, b) =>
        (b.key === selected) - (a.key === selected) ||
        (b.key === RECOMMENDED[role]) - (a.key === RECOMMENDED[role]) ||
        a.online - b.online,
    );
  return (
    <div className="model-picker" role="dialog" aria-label={t("选择{role}", { role: ROLES[role].label })}>
      <header className="app-row">
        <span className="app-tile" style={{ "--tile": ROLES[role].color, width: 30, height: 30 }}>
          <Icon name={ROLES[role].icon} size={16} strokeWidth="2.1" />
        </span>
        <b className="grow">{t("选择{role}", { role: ROLES[role].label })}</b>
        <button className="app-btn quiet icon-only" onClick={onClose} aria-label={t("关闭")}>
          <Icon name="x" size={16} />
        </button>
      </header>
      <label className="app-field picker-search">
        <Icon name="search" size={15} />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("搜索名称、用途或模型 ID")} aria-label={t("搜索模型")} />
      </label>
      <div className="picker-list">
        {list.map((m) => (
          <div className={"picker-row" + (m.key === selected ? " is-selected" : "")} key={m.key}>
            <ModelLogo model={m} />
            <div className="grow">
              <div className="app-row">
                <b className="picker-name">{t(m.name)}</b>
                {m.key === RECOMMENDED[role] && <Chip tone="info">{t("★ 推荐")}</Chip>}
              </div>
              <div className="t3 picker-meta">
                {t(m.copy?.summary || m.summary)}
              </div>
              <div className="t3 picker-meta">{t(m.mode)} · {sizeLabel(m)}</div>
            </div>
            <button className={"app-btn" + (m.key === selected ? " on" : "")} onClick={() => onPick(m.key)} disabled={m.key === selected}>
              {m.key === selected ? t("已选") : t("选用")}
            </button>
          </div>
        ))}
        {!list.length && <p className="t3">{t("没有匹配的模型，换个关键词试试。")}</p>}
      </div>
      {role !== "primary" && (
        <button className="app-btn quiet picker-off" onClick={() => onPick(null)}>
          {t("关闭{role}", { role: ROLES[role].label })}
        </button>
      )}
    </div>
  );
}

// “先选目标” state shared by the goal list and the role cards.
export function usePlan() {
  const [plan, setPlan] = useState("quality");
  const [sel, setSel] = useState(() => planSelection(PLANS[0]));
  const [picker, setPicker] = useState(null);
  return {
    plan, sel, picker, setPicker,
    current: PLANS.find((p) => p.key === plan),
    choose: (p) => {
      setPlan(p.key);
      setPicker(null);
      if (p.key !== "custom") setSel(planSelection(p, sel));
    },
    pick: (role, key) => {
      const next = { ...sel, [role]: key };
      setSel(next);
      setPlan(matchPlan(next));
      setPicker(null);
    },
  };
}

export function GoalList({ state }) {
  return (
    <div className="goal-list" role="radiogroup" aria-label={t("先选目标")}>
      {PLANS.map((p) => (
        <button key={p.key} role="radio" aria-checked={state.plan === p.key} className="goal" onClick={() => state.choose(p)}>
          <span className="goal-dot" aria-hidden="true" />
          <span className="goal-name">{t(p.label)}</span>
          <span className="goal-vram mono">
            {p.key === "custom" ? COPY.models.customVram : p.estimated_vram_gb ? t(COPY.models.vram, { n: p.estimated_vram_gb }) : COPY.models.noVram}
          </span>
          <span className="goal-desc">{p.key === "custom" ? COPY.models.customDesc : t(p.description)}</span>
        </button>
      ))}
    </div>
  );
}

export function PlanApp({ state }) {
  const { sel, picker, setPicker, current } = state;
  const summary = ROLE_KEYS.map((r) => modelFor(sel[r])).filter(Boolean).map(shortName).join(" + ");
  return (
    <div className="app plan-app">
      <div className="plan-app-head">
        <b className="plan-app-title">{t("识别方案")}</b>
        <span className="t3">{t("先选目标")}</span>
        <span className="app-field plan-goal">
          {t(current.label)}
          <span className="grow" />
          <Icon name="chevDown" size={14} />
        </span>
      </div>
      <div className="plan-roles">
        {ROLE_KEYS.map((r) => (
          <RoleCard key={r} role={r} model={modelFor(sel[r])} active={picker === r} onClick={() => setPicker(picker === r ? null : r)} />
        ))}
      </div>
      <div className="plan-foot">
        <Icon name="info" size={15} />
        <span>
          {t("当前组合：")}<b>{summary || t("未选择")}</b>
        </span>
        <span className="grow" />
        <span className="t3">{t("点卡片可以换模型")}</span>
      </div>
      {picker && <ModelPicker role={picker} selected={sel[picker]} onPick={(k) => state.pick(picker, k)} onClose={() => setPicker(null)} />}
    </div>
  );
}
