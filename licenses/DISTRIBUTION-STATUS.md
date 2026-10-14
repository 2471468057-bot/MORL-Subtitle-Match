# 分发材料状态

## 2026-10-14：0.7.1 现状（本节优先）

0.7.1 是第一次同时发 Windows 安装包与 macOS DMG。结论与 0.7.0 相同，只多了 Mac 一项：

- **Windows 随包第三方组件与 0.7.0 相同**：构建环境的 Python 发行包清单逐项相同，程序目录顶层逐项相同；`licenses/`（除生成的 `licenses/python`）与 `renderer/` 的程序文件和公开 0.7.0（`e2c410ff`）逐字节相同，只有版本号不同。本版新增的是自有代码与自有素材（`assets/onboarding/` 的新手教学动画，由本项目的 HTML 设计逐帧渲染）。
- **Remotion/GSAP 附加许可**：作者 2026-10-11 授予并写在 [PROJECT_LICENSE.md](../PROJECT_LICENSE.md)，适用于之后包含相同代码的版本；renderer 受覆盖文件与 0.7.0 相同，本版 Release 另附一份写明 0.7.1 构建身份的记录文件。
- **gyan FFmpeg 9.0（`tools/ffmpeg`，仅 Windows）仍缺构建材料**：2026-10-14 复查，gyan.dev 与 `GyanD/codexffmpeg` 仍只公开 FFmpeg 源码提交与 README（原文在 `source-materials/gyan-ffmpeg-9.0-essentials/README.txt`），没有构建脚本、可能的补丁，13 个链接库与 openal-soft 也没有确切版本（见 [SOURCES.md](SOURCES.md)）。x265（compositor）“已满足”的结论只适用于 x265，不代表整个安装包。本版没有更换 FFmpeg：发布当天替换核心媒体程序需要完整回归。可行的解决路线是改用构建脚本与依赖提交全部公开的版本（例如 BtbN/FFmpeg-Builds 的固定 autobuild），列为后续工作。
- **macOS DMG（Apple Silicon arm64，第一次公开）**：FFmpeg 与 mpv 来自固定 Homebrew core 提交 `0211e9c2eeea26bc0f1b382446dc076321e9a871` 的官方 bottle（`ffmpeg-full` 9.0.2、`mpv` 0.41.0 及其依赖，见 `packaging/macos/native-dependencies.lock.json` 与 `MEDIA_INPUTS.md`）；构建配方（formula）、上游源码地址与 SHA-256 都在该公开提交里，本项目没有另附这些上游源码包，按 GPLv3 §6(d) 指向 Homebrew 配方与上游。Python 依赖来自 PyPI 官方 wheel（版本见 `packaging/macos/requirements-*.txt`）。DMG 内带 `licenses/`、`LICENSE`、`PROJECT_LICENSE.md`、`THIRD_PARTY_NOTICES.md`。[组件目录](COMPONENTS.md)只登记了 Windows 安装包；Mac 包里每个动态库的逐项登记还没有做。
- 待核：与 0.7.0 相同（`pytest` 被沿依赖链收入主程序、`pywin32` 子项目范围、CTC 模型的基础模型与训练数据条款）。

## 2026-10-13：0.7.0 现状（本节优先）

0.7.0 按与 0.6.5 相同的结论公开分发（[GPL3_ROUTE.md 的 2026-10-11 节](GPL3_ROUTE.md)）：

- 新增随包第三方组件是本机 MCP 服务的官方 SDK 依赖链（17 个发行包，另 8 个原离线 wheel 组件进入主程序），全部为宽松许可（MIT、BSD、Apache-2.0、PSF），已登记到[组件目录](COMPONENTS.md)第 605–621 条与[机器索引](component-index.json)，原许可文件在 `materials/frozen/`；新增可下载的日语 CTC 对齐模型登记在[模型表](MODELS.md)第 622 条。
- Remotion/GSAP 仍由作者对自有代码的附加许可覆盖；PR #2 贡献者（CODE-A-DUCK）于 2026-10-13 对其贡献的代码（`renderer/populate-fonts.mjs` 与 `renderer/service.mjs` 的字体复制段落）给予同样的附加许可。Remotion 4.0.513、GSAP 3.15.0 与随附的 257 个 npm 包与 0.6.5 完全相同。
- 对应源码：Release 附 `2ByteASR-Source-0.7.0.zip`，第三方固定源码沿用 0.6.5 的附件；仍缺的与 0.6.5 相同（gyan FFmpeg 9.0 的构建脚本、可能的补丁与部分链接库版本，见 [SOURCES.md](SOURCES.md)）。
- 待核：`pytest` 被沿依赖链收入主程序（应在打包规则里排除）、`pywin32` 子项目范围、CTC 模型的基础模型与训练数据条款。

## 2026-10-11：0.6.5 现状（本节优先）

0.6.5（r9，源码指纹 `88dd5077…66fbfb`，tag `v0.6.5`）的安装包和附件按 [GPL3_ROUTE.md 的 2026-10-11 节](GPL3_ROUTE.md) 的结论公开分发：

- compositor 的 FDK 实测为 fdk-aac-free，保留；
- Remotion/GSAP 由作者对自有代码的附加许可覆盖；
- 对应源码已附基础源码，其余按 §6(d) 指向上游；x265 已核对满足；仍缺一处：gyan FFmpeg 9.0 的构建脚本、可能的补丁与部分链接库版本（见 SOURCES.md 来源索引）。

安装包里随附的 `licenses/` 文件是构建当时的版本，仍写着“内部候选”；以本仓库和 Release 说明为准，下次程序内更新会一并带上新版。下面各段是更早的状态，保留作历史。

自有代码从 **0.2.6-test.3** 起已采用标准 GPL-3.0-only；不再有待选择的收费条款或禁售条件。范围见 [项目声明](../PROJECT_LICENSE.md)。

本版本为本地内部候选，组合的公开分发尚未放行。[GPL3_ROUTE.md](GPL3_ROUTE.md)区分旧理由撤销、实际解决、对应源码缺口与第三方组合/素材权利。改根LICENSE不代表第三方权利齐全。

[目录](COMPONENTS.md)及[机器索引](component-index.json)保留原品牌Setup版本取证，不自动升级证据等级。新候选保留运行依赖，四项Qt排除、正式许可和FireRed标记须核对真实安装回执。原品牌、旧test.2及i18n Setup保留原许可和独立身份。

[源码](SOURCES.md)明确已有与缺失部分，[模型表](MODELS.md)区分代码/权重/配置/词表。首次下载不免条件。原版权/许可/NOTICE/例外保留；商业许可占位不是授权证明。

本地附件及GPLv3 §6(d)交付方式见 [SOURCE_DELIVERY.md](../SOURCE_DELIVERY.md)，尚未上传，不作在线可取得或全部第三方可重编译的承诺。
