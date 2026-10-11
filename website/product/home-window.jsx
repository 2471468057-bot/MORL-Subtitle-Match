import React, { memo } from "react";
import { Icon } from "./icons.jsx";
import { BrandBar, Chip, RoleCard, SignalArt, Toggle } from "./kit.jsx";
import { MEDIA_FORMATS, ROLE_KEYS, modelFor, themeStyle } from "./data.js";
import { TEAM_CUE, fragments } from "./sample.js";
import { RECOGNIZED_CUTS } from "./demo.js";
import { t } from "./i18n/index.jsx";
import "./home-window.css";

const HOME_SELECTION = { primary: "moss", timeline: "firered", review: "qwen_local" };
const SAMPLE_CUES = [...fragments(RECOGNIZED_CUTS).map((f) => ({ ...f, speaker: "S00" })), TEAM_CUE].sort((a, b) => a.start - b.start);
const cueAt = (ms) => SAMPLE_CUES.find((c) => ms >= c.start && ms < c.end);

// The desktop home page (m11 layout), rebuilt in HTML.
export const HomeWindow = memo(function HomeWindow({ theme = "grape", time = 7300 }) {
  const cue = cueAt(time);
  return (
    <div className="app home-win" style={themeStyle(theme)}>
      <BrandBar />
      <div className="hw-body">
        <div className="hw-head">
          <b className="hw-title">{t("本批字幕")}</b>
          <span className="t3">{t("依次确认素材、当前内容、启用词库和识别方案")}</span>
          <span className="grow" />
          <b>{t("识别方案")}</b>
          <span className="t3">{t("先选目标")}</span>
          <span className="app-field hw-select">
            {t("质量优先（推荐）")}<span className="grow" />
            <Icon name="chevDown" size={14} />
          </span>
          <span className="app-btn icon-only"><Icon name="more" size={16} /></span>
          <span className="app-btn"><Icon name="gear" size={14} />{t("高级设置")}</span>
        </div>
        <div className="hw-drop">
          <span className="app-tile soft" style={{ "--tile": "var(--a-accent-tx)" }}>
            <Icon name="fileIn" size={20} />
          </span>
          <div>
            <b className="hw-drop-title">{t("把视频或音频拖到这里")}</b>
            <div className="t2">{t("支持多选；也可以点击右侧“选择素材”")}</div>
            <div className="t3 hw-formats">{MEDIA_FORMATS.join(" · ")}</div>
          </div>
          <span className="app-btn primary hw-pick"><Icon name="folder" size={15} />{t("选择素材")}</span>
        </div>
        <div className="hw-grid">
          <div className="app-card hw-studio">
            <div className="app-row">
              <span className="app-tile soft" style={{ "--tile": "var(--a-zone-studio)" }}><Icon name="cc" size={18} /></span>
              <div>
                <b className="hw-card-title">{t("字幕工作台")}</b>
                <div className="t3">{t("校对字幕、剪辑片段、调整样式并压制成片")}</div>
              </div>
            </div>
            <SignalArt className="hw-cover">
              <span className="burned-caption" style={{ fontSize: 15 }}>{cue?.text || ""}</span>
              <span className="hw-cover-meta">
                <small>{t("继续编辑 →")}</small>
                <b>{t("双人对话")}</b>
                <small>{t("{n} 条字幕", { n: 6 })} · 10-09 16:00</small>
              </span>
            </SignalArt>
            <div className="t3 hw-recent-title">{t("最近工程")}</div>
            {[[t("直播回放 · 第 12 期"), 48, "10-08 21:30"], [t("攻略解说 · 草稿"), 21, "10-07 15:00"]].map(([n, c, d]) => (
              <div className="hw-recent" key={d}><span>{n}</span><span className="t3">{t("{n} 条字幕", { n: c })} · {d}</span></div>
            ))}
            <span className="app-btn soft hw-enter"><Icon name="cc" size={15} />{t("进入字幕工作台")}</span>
          </div>
          <div className="hw-right">
            <div className="hw-roles">
              {ROLE_KEYS.map((r) => (
                <RoleCard key={r} role={r} model={modelFor(HOME_SELECTION[r])} as="div" />
              ))}
            </div>
            <div className="app-card hw-ai">
              <span className="app-tile soft" style={{ "--tile": "var(--a-zone-ai)" }}><Icon name="sparkle" size={18} /></span>
              <div className="grow">
                <b className="hw-card-title">{t("AI 智能断句")}</b>
                <div className="t3">{t("已保存：在线服务 · 示例配置")}</div>
                <div className="app-row hw-chips">
                  <Chip tone="accent">{t("字幕校对：开启")}</Chip>
                  <Chip tone="accent">{t("全文断句：开启")}</Chip>
                  <Chip>{t("数字规范化：开启")}</Chip>
                </div>
              </div>
              <span className="app-btn"><Icon name="sliders" size={14} />{t("设置 AI")}</span>
            </div>
            <div className="app-card hw-terms">
              <div className="app-row">
                <span className="app-tile soft" style={{ "--tile": "var(--a-zone-content)" }}><Icon name="tag" size={18} /></span>
                <b className="hw-card-title grow">{t("内容与术语")}</b>
                <span className="app-btn"><Icon name="book" size={14} />{t("管理术语库")}</span>
              </div>
              <div className="hw-terms-grid">
                <div>
                  <div className="t3 hw-label">{t("游戏 / 内容名称")}</div>
                  <span className="app-field">{t("明日方舟")}<span className="grow" /><Icon name="chevDown" size={14} /></span>
                  <div className="app-row hw-recent-games">
                    <span className="t3">{t("最近")}</span>
                    {[t("明日方舟"), t("绝区零"), t("洛克王国：世界")].map((g) => <Chip key={g}>{g}</Chip>)}
                  </div>
                </div>
                <div className="hw-switches">
                  <div className="app-row"><Toggle on label={t("术语库校对")} /><b>{t("术语库校对")}</b></div>
                  <div className="t3">{t("启用后用于专名、角色名与错词修正")}</div>
                  <div className="app-row"><Toggle label={t("联网补充核验（可选）")} /><b>{t("联网补充核验（可选）")}</b></div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div className="hw-bottom">
          <span className="hw-ready"><Icon name="checkCircle" size={16} />{t("识别方案与示例词库已就绪")}</span>
          <span className="grow" />
          <span className="app-btn primary hw-start"><Icon name="play" size={14} />{t("开始生成字幕")}</span>
        </div>
      </div>
    </div>
  );
});

