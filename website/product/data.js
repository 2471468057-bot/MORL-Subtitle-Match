// Shared data for the page. Catalog, plans and themes are extracted from the
// desktop source by scripts/extract_catalog.py; sample content is hand-made.
import catalog from "../public/data/catalog.json";
import { COPY, t } from "./i18n/index.jsx";

export { catalog };
export const A = "./assets/";
export const asset = (p) => globalThis.window?.__PRODUCT_ASSETS?.[p] || p;
export const BRAND = A + "brand-256.png";
export const RELEASES = "https://github.com/NOTBAD314/2ByteASR/releases";
export const ISSUES = "https://github.com/NOTBAD314/2ByteASR/issues";
// The download routes are Pages Functions (website/functions); the offline
// single-file pages use the deployed site.
export const SITE = "https://2byteasr.pages.dev";
const ONLINE = /^https?:$/.test(globalThis.location?.protocol || "");
export const DOWNLOAD = (ONLINE ? "" : SITE) + "/download/windows";
export const RELEASE_API = ONLINE ? "/api/release" : null;
export const VERSION =
  catalog.version + (catalog.channel === "testing" ? COPY.testing : "");

export const ROLES = {
  primary: { label: t("主力转写"), desc: t("中文多人转写与说话人区分"), icon: "wave", color: "var(--a-role-p)" },
  timeline: { label: t("字幕时间轴"), desc: t("断句、时间轴与字幕节奏校准"), icon: "clock", color: "var(--a-role-t)" },
  review: { label: t("文字复核"), desc: t("错词复核、专名与上下文纠正"), icon: "checkCircle", color: "var(--a-role-r)" },
};
export const ROLE_KEYS = Object.keys(ROLES);
export const byKey = (k) => catalog.models.find((m) => m.key === k);
const SHORT = {
  moss: "MOSS",
  firered: "FireRed",
  qwen_local: "Qwen3-ASR",
  qwen_aligner: t("Qwen3 对齐"),
  firered_llm: "FireRed-LLM",
  sensevoice: "SenseVoice",
  paraformer: "Paraformer",
  whisper: "Whisper",
  funasr_nano: "Fun-ASR Nano",
  glm_asr_nano: "GLM-ASR",
  canary_qwen: "Canary-Qwen",
  groq_api: "Groq API",
  openai_api: "OpenAI API",
  custom_asr_api: t("兼容 ASR"),
};
export const shortName = (m) => (m ? SHORT[m.key] || t(m.name) : t("已关闭"));
export const isLocal = (m) => !!m && !m.online;
// "约 1.7 GB" / "预计下载 17.57 GiB" → "约 {size}" in the page language.
export const sizeLabel = (m) =>
  !m ? "" : m.online ? t("在线 · 免下载") : t("约 {size}", { size: m.size.replace(/^(预计下载|约)\s*/, "") });

// The desktop plan values (recognition_plans.py) mapped to catalog models.
const SLOT = {
  primary: { moss: "moss", sensevoice: "sensevoice", api: "api" },
  timeline: { local: "firered", api: "api", off: null },
  review: { local: "qwen_local", api: "api", off: null },
};
export const PLANS = catalog.plans;
export function planSelection(plan, current) {
  if (plan.key === "custom") return current;
  const out = {};
  for (const r of ROLE_KEYS) out[r] = SLOT[r][plan[r]] ?? null;
  return out;
}
export function matchPlan(sel) {
  for (const p of PLANS)
    if (p.key !== "custom" && ROLE_KEYS.every((r) => (SLOT[r][p[r]] ?? null) === (sel[r] ?? null)))
      return p.key;
  return "custom";
}
export const API_MODEL = {
  key: "api",
  name: t("在线 API"),
  online: true,
  size: t("不占本地空间"),
  mode: t("在线 · 需自己的 API Key"),
};
export const modelFor = (key) => (key === "api" ? API_MODEL : key ? byKey(key) : null);

// Five desktop themes → CSS variables of the replica.
export const THEME_ORDER = ["grape", "warm", "plum", "lavender", "slate"];
export function themeStyle(key) {
  const t = catalog.themes[key];
  if (!t) return undefined;
  const onAccent = key === "grape" ? "#fff6f9" : key === "warm" ? "#ffffff" : t.app_background;
  return {
    "--a-bg": t.app_background,
    "--a-surface": t.surface,
    "--a-elev": t.surface_elevated,
    "--a-panel": t.panel,
    "--a-input": t.input_surface,
    "--a-sel": t.selected,
    "--a-timeline": t.timeline,
    "--a-media": t.media,
    "--a-line": t.border,
    "--a-line2": t.border_strong,
    "--a-tx": t.text,
    "--a-tx2": t.text_secondary,
    "--a-tx3": t.text_muted,
    "--a-accent": t.accent,
    "--a-accent-hi": t.accent_hover,
    "--a-accent-soft": t.accent_soft,
    "--a-accent-tx": t.accent_text,
    "--a-ok": t.success,
    "--a-warn": t.warning,
    "--a-warn-soft": t.warning_soft,
    "--a-bad": t.danger,
    "--a-bad-soft": t.danger_soft,
    "--a-info": t.focus,
    "--a-shell": t.shell,
    "--a-disabled": t.disabled,
    "--a-on-accent": onAccent,
    "--a-on-vivid": key === "warm" ? "#ffffff" : t.app_background,
    "--a-role-p": t.roles.primary,
    "--a-role-t": t.roles.timeline,
    "--a-role-r": t.roles.review,
    "--a-zone-studio": t.zones.studio,
    "--a-zone-ai": t.zones.ai,
    "--a-zone-content": t.zones.content,
  };
}
export const themeName = (key) => catalog.themes[key]?.name || key;

// Sample project: two speakers, hand-made timings (see edit-model.js).
export const DURATION = 16000;
export const TEAM_CUE = { id: "b", speaker: "S01", start: 5450, end: 7250, text: "我拿到了，你们先走。" };
export const SPK = { S00: { lane: "A", cls: "s0" }, S01: { lane: "B", cls: "s1" }, S02: { lane: "C", cls: "s2" } };
export const MEDIA_FORMATS = ["AAC", "AVI", "FLAC", "FLV", "M4A", "MKV", "MOV", "MP3", "MP4", "WAV", "WEBM"];
export const clockShort = (ms) => {
  const s = Math.max(0, ms) / 1000;
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${(s % 60).toFixed(1).padStart(4, "0")}`;
};
export const timecode = (ms) => {
  const s = Math.max(0, ms) / 1000;
  return `00:${String(Math.floor(s / 60)).padStart(2, "0")}:${(s % 60).toFixed(3).padStart(6, "0")}`;
};
