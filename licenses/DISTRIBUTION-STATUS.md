# 分发材料状态

## 2026-10-11：0.6.5 现状（本节优先）

0.6.5（r9，源码指纹 `88dd5077…66fbfb`，tag `v0.6.5`）的安装包和附件按 [GPL3_ROUTE.md 的 2026-10-11 节](GPL3_ROUTE.md) 的结论公开分发：

- compositor 的 FDK 实测为 fdk-aac-free，保留；
- Remotion/GSAP 由作者对自有代码的附加许可覆盖；
- 对应源码已附基础源码，其余按 §6(d) 指向上游；仍缺两处确切构建材料（gyan FFmpeg 9.0 的静态外部库与构建脚本、Remotion 预编译 `libx265.a` 的编译命令），已列明。

安装包里随附的 `licenses/` 文件是构建当时的版本，仍写着“内部候选”；以本仓库和 Release 说明为准，下次程序内更新会一并带上新版。下面各段是更早的状态，保留作历史。

自有代码从 **0.2.6-test.3** 起已采用标准 GPL-3.0-only；不再有待选择的收费条款或禁售条件。范围见 [项目声明](../PROJECT_LICENSE.md)。

本版本为本地内部候选，组合的公开分发尚未放行。[GPL3_ROUTE.md](GPL3_ROUTE.md)区分旧理由撤销、实际解决、对应源码缺口与第三方组合/素材权利。改根LICENSE不代表第三方权利齐全。

[目录](COMPONENTS.md)及[机器索引](component-index.json)保留原品牌Setup版本取证，不自动升级证据等级。新候选保留运行依赖，四项Qt排除、正式许可和FireRed标记须核对真实安装回执。原品牌、旧test.2及i18n Setup保留原许可和独立身份。

[源码](SOURCES.md)明确已有与缺失部分，[模型表](MODELS.md)区分代码/权重/配置/词表。首次下载不免条件。原版权/许可/NOTICE/例外保留；商业许可占位不是授权证明。

本地附件及GPLv3 §6(d)交付方式见 [SOURCE_DELIVERY.md](../SOURCE_DELIVERY.md)，尚未上传，不作在线可取得或全部第三方可重编译的承诺。
