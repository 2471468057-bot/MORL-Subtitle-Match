# 2ByteASR / 兔白字幕 产品介绍页

纵向滚动的产品介绍页，有中文、English、日本語三个版本。2026-10-09 按新版桌面界面整体重做（旧版见 `deliverables/2ByteASR-product-page-*.zip`，9 月 30 日），同日加上英文页和日文页。全部演示只在浏览器内存里运行：不运行模型、不调用在线服务、不读取访客的文件。

## 打开

- 单文件，脚本、样式、字体、图片都已内嵌，可离线打开：`product-build/打开产品介绍.html`（= `portable.html`，中文，或 `preview.cmd`）、`portable-en.html`、`portable-ja.html`。三个文件放在同一文件夹里，页面右上角可以互相切换。
- 静态网站入口：`product-build/index.html`（中文）、`en.html`、`ja.html`，需要通过本地服务打开（`npm run preview`，端口 4175）。
- `review-20261009/`：三种语言的截图（文件名前缀 zh- / en- / ja-）、浏览器检查结果 `verify.json`、检查范围 `VALIDATION.md`、设计计划 `plan.html`。
- `deliverables/2ByteASR-product-page-v3-20261009-*.zip`：三语版成品包与源码包（v2 是只有中文的上一轮）。

## 部署（Cloudflare Pages）

2026-10-11 起，官网由 Cloudflare Pages 从 GitHub `main` 构建：根目录 `website`，构建命令 `npm run build`，输出目录 `product-build`，Node 22（`.node-version`）。`main` 上改动 `website/` 的提交会自动重新部署；提交信息带 `[skip ci]` 的不会触发 Cloudflare 构建，只想跳过 GitHub Actions 时用 `[skip actions]`。

下载按钮走 Pages Functions（`functions/`，逻辑在 `server/latest-release.js`）：`/download/windows` 每次查 GitHub 最新一次正式发布（`releases/latest`，草稿和预发布不算），302 到其中的 `2ByteASR-Setup-<版本>.exe`；`/download/macos` 同理指向 `2ByteASR-<版本>-macos-arm64-Setup.dmg`（实验版，只支持 Apple 芯片）；`/api/release` 给页面按钮显示版本和大小。发新版只要在 GitHub Publish，网站不用改。还没有正式发布时按钮显示“安装包即将发布”；最新版本没附 Mac 安装包时页面不显示 Mac 按钮，`/download/macos` 说明这一版没有 Mac 版。GitHub API 限流时退回网页的 `releases/latest` 跳转找版本号，Mac 安装包再用一次 HEAD 确认确实存在。可在 Cloudflare 项目里加机密 `GITHUB_TOKEN`（只读）提高限额；仓库若改回私有，没有它就下载不了。

GitHub 上只放构建需要的源码、脚本和测试；`review*/`、`product-review/`、`deliverables/`、`build/`、`src/`（旧版交互演示）这些审核材料和旧件只留在本地工作区。

## 页面结构

产品宣传页，不是操作教学。先建立价值，再逐个展示核心能力；每区只讲一件事，演示用软件里对应的真实界面局部（HTML 复刻）。

| 区块 | 让人记住的一件事 | 演示（进入画面自动播放，鼠标停住暂停，点一下交给访客） |
| --- | --- | --- |
| 首屏 | 录播拖进来，字幕自动整理好 | 主页 + 字幕工作台 3D 叠层，随鼠标倾斜 |
| 效果对比 | 同一段录音，差别一眼就看得出 | 一般自动字幕 vs 兔白字幕，4 个颜色图例 |
| 候选字幕 · 优先审核 | 有分歧的句子排在最前面，挑一个采用 | Studio 审核模式：字幕列表 + 三个候选卡 |
| AI 词库校对 | 专名按词库改对，勾选了才写回 | 原文 → 建议 → 套用后 |
| 术语库 | 整理一次，之后每次识别都受益 | 添加错词、确认参考词条 |
| 字级时间轴 · 分轨 | 每人一条轨，每个字都有时间 | 放大的时间轴：字词块、双说话人轨、剃刀切句 |
| 导出字幕 · 压制成片 | 做完拿到能直接发的成片 | 导出字幕对话框 + 压制完成 |
| 免费开源 · 本地运行 | 素材不必离机；先选目标，模型自动配好 | 六种目标切换角色卡，可展开 18 项模型目录 |
| 下载 | 版本、三步上手、系统与格式 | — |

所有区块与首屏同一版心（最宽 1520px）。每节：大标题 + 说明在左、3 个要点在右，下面是全宽演示；五个演示同一尺寸（1280 × 700 设计，等比缩放）。媒体画面统一用“无信号”测试卡占位。设计依据见 DESIGN.md。减少动态效果时各演示停在完成状态，仍可手动操作。

## 修改和构建

```powershell
cd website
npm install           # 也可以复用 ../renderer/node_modules 里的 esbuild 与 React
npm run build         # 输出 product-build/；每次先清空
node scripts/build-readme-scenes.mjs
npm test              # 34 项
npm run preview       # 另开一个终端
npm run verify        # Chrome / Edge 无头浏览器的真实点击检查，结果写到 ../tmp/product-page-verify
```

- 源码在 `product/`：`page.jsx` 组装各段；`hero.jsx` 首屏与能力总览（叠层用 `home-window.jsx` 与 `studio.jsx` 的窗口）；`features.jsx` 优先审核、词库校对、术语库、字级分轨、导出五个区块；`models.jsx` + `plans.jsx` 本地运行与模型；`chapter.jsx` 是区块框架；`kit.jsx` + `kit.css` 是桌面界面的复刻组件（颜色全是 `--a-*` 变量，可换主题）；`tokens.css` 是页面设计令牌；`icons.jsx` 是统一线性图标。
- 切分规则在 `edit-model.js`（与桌面手动切分约定一致），测试覆盖。
- 目录、识别方案、主题色、参考指数由 `python -X utf8 -I scripts/extract_catalog.py` 从桌面源码抽取（只读 AST，不导入桌面程序），写入 `public/data/catalog.json`。
- 改了页面文字后，用装有 `fontTools` 与 `brotli` 的 Python 运行 `scripts/subset-fonts.py` 重新生成字体子集；`npm test` 会检查是否有字不在子集里。

## 三种语言

- 语言在构建时确定：`scripts/build-product.mjs` 为每种语言打一个包（`product.js` / `product-en.js` / `product-ja.js`），样式共用 `product.css`。`scripts/lang-plugin.mjs` 把 `@lang/copy`、`@lang/dict` 换成该语言的文件，别的语言的文字不进包。
- **页面文案**（标题、说明、要点、下载与页脚）：`product/i18n/copy.zh.js`、`copy.en.js`、`copy.ja.js`，三份结构必须一致。标记：`*关键短语*` 用本节颜色，`**加粗**`，`` `中文示例` `` 用中文字体，`\n` 换行。
- **界面文字**（软件界面复刻、模型目录）：代码里写 `t("中文原文")`，和桌面程序 `twobyteasr/i18n.py` 同样以中文为键。英文、日文优先用桌面程序自己的译文：`npm run i18n`（`scripts/extract_i18n.py`，需完整仓库）把页面用到的每个键在桌面词表里查一遍，写入 `product/i18n/app-strings.json`；桌面没有的，或放不下、语境不同的，写在 `product/i18n/ui.js`（优先于前者，注释写明原因）。`npm test` 会检查每个键都有英日两种译文、占位符一致。
- **示例字幕和词条**也按语言换：`product/i18n/sample.{zh,en,ja}.js`。英日两份各有 26 个字词，分句位置和每个字词的时间与中文示例（`edit-model.js`）一致，所以切句、剃刀、播放在三种语言里表现相同；`product/sample.js` 负责把它们换进各演示。三份的对比区、候选写法、词库校对建议、术语库词条也都各写一份。页脚注明“示例字幕以本语言显示，软件识别的是中文语音”。
- **字体**：中文页、英文页用嵌入的 “2B Sans”（英文字母来自同一套思源黑体）；日文页的日文用系统日文字体（Hiragino / Yu Gothic UI / Meiryo / Noto Sans JP），只有拉丁字母、数字和引号用页面字体。原因见 DESIGN.md。
- 加一条新的界面文字：在组件里写 `t("中文")`，运行 `npm run i18n`，再把 `ui.js` 里列出的缺口补上，然后 `npm run fonts`、`npm run build`、`npm test`。

## 已知范围

- `docs/assets/readme/` 的 README 动图仍是 9 月 30 日旧版本，README 场景入口已改用新组件，但没有重新录制。
- `scripts/record-product.mjs`、`capture-readme*.mjs` 等录制脚本需要 Playwright，本轮没有重新运行。
- `product-review/` 是 9 月 30 日那一轮的证据，保留不动。
