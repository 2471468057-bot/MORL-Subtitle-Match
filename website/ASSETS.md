# 素材与数据来源

| 内容 | 来源与边界 |
| --- | --- |
| 品牌 | 原角色透明 PNG 缩成 256 px（`public/assets/brand-256.png`）；文字统一为 2ByteASR / 兔白字幕。 |
| 界面 | 按 `tmp/visual-refresh-20261007/m11–m16` 的新版桌面截图与当前源码，用 HTML 复刻；不是桌面截图。 |
| 主题色 | `twobyteasr/ui_theme.py` 五套主题、角色色卡与区块色，构建时抽取。 |
| 识别方案 | `twobyteasr/recognition_plans.py` 的六种“先选目标”。 |
| 模型目录 | `twobyteasr/model_workshop.py` 等 18 项；参考指数来自 `model_benchmarks.py`，只用于比较，不是识别正确率。 |
| 示例画面 | “无信号”测试卡占位（`kit.jsx` 的 `SignalArt`）；Studio 时间轴缩略图用 `dialogue-frame.webp`。 |
| 字幕与时间 | `edit-model.js` 的 26 个非均匀字词时间，人工预置，没有真人音频；S00 / S01 是示例说话人标签。英文、日文示例（`product/i18n/sample.en.js`、`sample.ja.js`）沿用同样的字词时间与分句，文字为本页撰写。 |
| 英日示例词条 | 明日方舟、绝区零的角色用游戏的官方英文 / 日文名；洛克王国：世界没有官方英日名，词条名为意译。 |
| 审核候选 | 同一句“人物 / 任务 / 战术”的人工差异，来源标签不代表模型排名。 |
| 术语库 | 项目内置三款游戏清单各 10 项；新增“银辉 → 银灰”为演示用。 |
| 导出与压制 | 文件名、大小、码率为示例数值，网页不编码视频。 |
| 未上页面 | `public/assets/themes` 的木刻 / CRT 作品保留在源码，本版不展示、不打包。 |
| 词库校对 | 两条明日方舟词条建议（阿兰那 → 阿兰娜、十二F → 12F）是人工示例。 |
| 字体 | 思源黑体 Medium / Heavy 与 Noto Sans SC Regular（同一设计）的子集，SIL OFL 1.1，改名 “2B Sans”。子集只含中文页、英文页和中文示例用到的字；日文页的日文用访客系统字体，不随页面分发。 |
| 英文、日文界面文字 | 优先取自桌面程序 `twobyteasr/i18n.py` 合并后的词表（`product/i18n/app-strings.json`，由 `scripts/extract_i18n.py` 生成，当前 264 条）；`product/i18n/ui.js` 的 152 条为本页手写：桌面词表没有的 136 条，加上 16 条语境覆盖（含 12 条桌面英文与中文原意不符的模型说明）。 |
| 英文、日文页面文案 | `product/i18n/copy.en.js`、`copy.ja.js`，为本页撰写，不是逐字翻译；游戏名用官方英文 / 日文名（Arknights / アークナイツ 等）。 |

第三方说明见 `public/THIRD_PARTY.md` 与 `public/licenses/`。
