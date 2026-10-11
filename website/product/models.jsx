import React, { useRef, useState } from "react";
import { Icon } from "./icons.jsx";
import { Mascot } from "./kit.jsx";
import { ModelLogo, GoalList, PlanApp, usePlan } from "./plans.jsx";
import { useReveal } from "./motion.js";
import { ISSUES, MEDIA_FORMATS, RELEASES, ROLES, VERSION, catalog, sizeLabel } from "./data.js";
import { COPY, rich, t } from "./i18n/index.jsx";
import "./models.css";

const RECOMMENDED = { moss: "primary", firered: "timeline", qwen_local: "review" };
const M = COPY.models;
const FILTERS = [
  ["all", M.all, () => true],
  ["primary", ROLES.primary.label, (m) => m.roles.includes("primary")],
  ["timeline", ROLES.timeline.label, (m) => m.roles.includes("timeline")],
  ["review", ROLES.review.label, (m) => m.roles.includes("review")],
  ["online", t("在线 API"), (m) => m.online],
  ["local", M.local, (m) => !m.online],
];

function Bar({ label, entry }) {
  if (!entry)
    return (
      <div className="ref-bar is-empty">
        <span className="ref-label">{label}</span>
        <span className="ref-value">{M.noScore}</span>
      </div>
    );
  return (
    <div className="ref-bar" title={t("{label}：{reason}", { label: t(entry.label), reason: t(entry.reason) })}>
      <span className="ref-label">{label}</span>
      <span className="ref-value mono">{entry.approx ? t(M.approx, { n: entry.score }) : entry.score}</span>
      <span className="ref-track"><i style={{ width: `${entry.score}%` }} /></span>
    </div>
  );
}

function ModelCard({ m }) {
  const [open, setOpen] = useState(false);
  const tech = m.technical || {};
  const rec = RECOMMENDED[m.key];
  return (
    <article className={"mcard" + (open ? " is-open" : "")}>
      <header className="mcard-head">
        <ModelLogo model={m} size={40} />
        <div className="mcard-name">
          <h3>{t(m.name)}</h3>
          <span>{t(m.mode)}</span>
        </div>
      </header>
      <p className="mcard-sum">{t(m.copy?.summary || m.summary)}</p>
      <div className="mcard-tags">
        {rec && <span className="tag rec"><Icon name="star" size={11} />{t(M.recommended, { role: ROLES[rec].label })}</span>}
        {m.roles.map((r) => (
          <span key={r} className={"tag role-" + r}>{ROLES[r].label}</span>
        ))}
        {!m.roles.length && <span className="tag">{M.weightsOnly}</span>}
        <span className="tag plain">{sizeLabel(m)}</span>
      </div>
      <div className="mcard-ref">
        <Bar label={t(m.reference?.caption || "转写准确度")} entry={m.reference?.accuracy} />
        <Bar label={t("速度指数")} entry={m.reference?.speed} />
      </div>
      <button className="mcard-more" aria-expanded={open} onClick={() => setOpen(!open)}>
        {open ? M.less : M.more}
        <Icon name="chevDown" size={14} />
      </button>
      {open && (
        <div className="mcard-detail">
          {tech.purpose && <p>{t(tech.purpose)}</p>}
          {(m.copy?.limitations || tech.limits) && <p className="muted">{t(M.limits, { text: t(m.copy?.limitations || tech.limits) })}</p>}
          <p className="muted">{t(m.verification)}</p>
          {tech.url && (
            <a href={tech.url} target="_blank" rel="noreferrer">
              {M.source} <Icon name="external" size={13} />
            </a>
          )}
        </div>
      )}
    </article>
  );
}

export function ModelsChapter({ reduced }) {
  const root = useRef();
  useReveal(root, reduced);
  const plan = usePlan();
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState("all");
  const [q, setQ] = useState("");
  const test = FILTERS.find((f) => f[0] === filter)[2];
  const list = catalog.models
    .filter(test)
    .filter((m) => `${m.name} ${t(m.name)} ${m.key} ${m.summary} ${m.copy?.summary || ""} ${t(m.copy?.summary || m.summary)}`.toLowerCase().includes(q.toLowerCase()))
    .sort((a, b) => !!RECOMMENDED[b.key] - !!RECOMMENDED[a.key] || a.online - b.online);
  return (
    <section id="models" ref={root} className="sec" style={{ "--ch": "#93bbe4" }} aria-labelledby="models-title">
      <div className="wrap">
        <header className="sec-head solo" data-reveal>
          <div className="sec-main">
            <h2 className="sec-title" id="models-title">
              {rich(M.title)}
            </h2>
            <p className="sec-lede">{rich(M.lede)}</p>
          </div>
        </header>
        <div className="models-split" data-reveal style={{ "--i": 1 }}>
          <GoalList state={plan} />
          <div className="models-visual">
            <PlanApp state={plan} />
            <button className="btn models-all" aria-expanded={open} onClick={() => setOpen(!open)}>
              {open ? M.hide : t(M.showAll, { n: catalog.models.length })}
              <Icon name="chevDown" size={16} />
            </button>
          </div>
        </div>
      </div>
      {open && (
        <div className="wrap models-catalog">
          <div className="models-bar">
            <div className="models-filters" role="tablist" aria-label={M.filters}>
              {FILTERS.map(([k, label, fn]) => (
                <button key={k} role="tab" aria-selected={filter === k} onClick={() => setFilter(k)}>
                  {label}
                  <span className="mono">{catalog.models.filter(fn).length}</span>
                </button>
              ))}
            </div>
            <label className="models-search">
              <Icon name="search" size={16} />
              <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={M.search} aria-label={t("搜索模型")} />
            </label>
          </div>
          <div className="models-grid">
            {list.map((m) => (
              <ModelCard key={m.key} m={m} />
            ))}
            {!list.length && <p className="models-empty">{M.empty}</p>}
          </div>
          <p className="note">
            {t(M.note, { note: t(catalog.reference_note), version: catalog.version })}
          </p>
        </div>
      )}
    </section>
  );
}

export function Download() {
  const D = COPY.download;
  return (
    <section id="download" className="download" aria-labelledby="download-title">
      <div className="wrap">
        <div className="dl-head">
          <Mascot size={96} />
          <div>
            <h2 id="download-title">{rich(D.title)}</h2>
            <p>{t(D.sub, { version: VERSION })}</p>
          </div>
          <div className="dl-actions">
            <a className="btn primary" href={RELEASES} target="_blank" rel="noreferrer">
              <Icon name="download" size={18} />
              {D.releases}
            </a>
            <a className="btn" href={ISSUES} target="_blank" rel="noreferrer">
              {D.issues}
              <Icon name="external" size={15} />
            </a>
          </div>
        </div>
        <ol className="dl-steps">
          {D.steps.map(([h, p], i) => (
            <li key={h} style={{ "--n": ["var(--violet)", "var(--apricot)", "var(--mauve)"][i] }}>
              <span className="dl-num" aria-hidden="true" />
              <h3>{h}</h3>
              <p>{p}</p>
            </li>
          ))}
        </ol>
        <dl className="dl-specs">
          {D.specs.map(([k, v]) => (
            <div key={k}>
              <dt>{k}</dt>
              <dd>{t(v, { formats: MEDIA_FORMATS.join(" · ") })}</dd>
            </div>
          ))}
        </dl>
        <p className="note">{D.note}</p>
      </div>
    </section>
  );
}
