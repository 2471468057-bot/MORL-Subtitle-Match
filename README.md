<div align="center">

<img src="docs/assets/readme/icon.png" width="104" alt="兔白字幕">

# 2ByteASR · 兔白字幕

**准确识别字幕，轻松剪辑视频。**

面向游戏实况的免费字幕识别与视频编辑工具，支持本地部署。<br>
从识别、校对到特效字幕与视频输出，一站完成。

[下载与快速开始](#下载与快速开始) · [功能演示](#一份字幕三种分工) · [实际界面](#实际界面) · [模型](#模型目录)

**中文** · [English](README_EN.md) · [日本語](README_JA.md)

</div>

## 一份字幕，三种分工

转写先把话写出来，时间轴把每个字落到对应的时间，复核让同一句的不同结果放在一起比较。按素材和设备选择组合，再按需开启 AI 断句。

![一份字幕三种分工：MOSS 写出文字并分出说话人，FireRed 给每个字标上时间，Qwen3-ASR 再听一遍核对，最后按说话人放进各自的字幕轨](docs/assets/readme/roles.webp)

| 角色 | 帮你做什么 | 代表方案 |
| --- | --- | --- |
| 主力转写 | 写出文字；MOSS 还能分出不同的说话人，各放一条字幕轨 | MOSS、SenseVoice、Whisper |
| 字词时间轴 | 给每个字标上起止时间，断句和切分都沿着字的边界 | FireRedASR2-AED、Paraformer；已有文本可用 Qwen3-ForcedAligner |
| 文字复核 | 用另一个模型再听一遍，标出写法不同的字 | Qwen3-ASR 等本地／在线方案 |

## 切到字词边界，调整字幕节奏

每个字都有自己的起止时间。拖动剃刀，它只会停在字与字之间，预览卡同时显示前后两段；松开就切开，时间跟着字走。切错了，一键撤销。

![剃刀沿着字与字之间移动，预览前段和后段，松开后切成两条字幕，再撤销](docs/assets/readme/razor.webp)

## 同一句，对照候选再采用

“他”还是“它”？三个模型各自听一遍，写法不同的字会被标出来。在同一条字幕下看清差异和来源，点一下采用，当前字幕随之更新。

![三个模型的写法并排比较，点选 Qwen3-ASR 的“它”后字幕更新](docs/assets/readme/review.webp)

## 游戏术语库：整理一次，反复使用

角色名、别名和常见错词，按游戏归档。核对参考词与来源，确认后用于识别和校对；换一段素材，不必从头整理。

![术语库按游戏整理，字幕里写错的“阿米亚”“原石技艺”对照词库改成“阿米娅”“源石技艺”](docs/assets/readme/terms.webp)

## 直播切片与特效字幕

**先找到值得剪的片段。** 结合直播弹幕 XML 和字幕，找到“残血反杀”“翻车爆笑”“弹幕集中”等候选，每条写明理由和时间范围，选好后加入剪辑。

![弹幕热度曲线标出高能片段，选中“残血反杀”后加入剪辑，时间范围同步选中](docs/assets/readme/clips.webp)

**再让一句话有自己的表情。** 字体、材质、入场与退场一起构成字幕作品。已有样式可以复用，也可以配置 AI 设计服务生成并修改。字幕设计和直播切片可以分别使用。

![木刻压印与 CRT 计分屏完整入场、停留和退场](docs/assets/readme/caption-effects.gif)

*木刻压印：木板扣合、刻印显字、收拢退场。CRT 计分屏：通电、磷光显字、关屏退场。*

## 实际界面

<p align="center">
  <img src="docs/assets/readme/studio.png" width="49%" alt="字幕工作台：字幕列表、视频预览、样式面板与按说话人分轨的时间轴">
  <img src="docs/assets/readme/home.png" width="49%" alt="首页：素材、三种识别角色、AI 智能断句与内容术语">
</p>

左边是字幕工作台，右边是首页。更多截图见[界面一览](docs/product-demo.zh-CN.md)。

## 下载与快速开始

**当前正式版 0.7.1：Windows x64，以及 macOS Apple Silicon（实验性）。** 下载最新版请到 [Latest Release](https://github.com/NOTBAD314/2ByteASR/releases/latest)，各文件的 SHA-256 见 Release 中的 `SHA256SUMS.txt`。

- **Windows：** 只需下载 [`2ByteASR-Setup-0.7.1.exe`](https://github.com/NOTBAD314/2ByteASR/releases/download/v0.7.1/2ByteASR-Setup-0.7.1.exe)（约 1 GB）。0.6.5、0.7.0 用程序内“检查更新”，只下载变化的部分，沿用相容的模型与环境；0.6.0 及更早版本直接覆盖安装，不要先卸载。安装包没有 Windows 代码签名，可能出现“未知发布者”提示。
- **macOS（实验性，仅 Apple Silicon、macOS 15 及以上）：** [`2ByteASR-0.7.1-macos-arm64-Setup.dmg`](https://github.com/NOTBAD314/2ByteASR/releases/download/v0.7.1/2ByteASR-0.7.1-macos-arm64-Setup.dmg)（约 0.5 GB）。没有 Developer ID 签名与 Apple 公证，第一次打开要在 Finder 里按住 Control 点按 App →“打开”；不需要关闭系统安全设置。不支持 Intel Mac。只在 GitHub 虚拟 Mac 上验证过，详见[说明](docs/deployment/macos-experimental.zh-CN.md)。
- **没有 NVIDIA 显卡：** 可以只用云端识别（自备服务商账号与 API Key），不需要下载本地模型。

第一次本地识别还要在模型工坊下载所选的运行环境和模型。

1. **安装并启动。** 运行 Setup 安装包后启动。
2. **准备识别方案。** 在模型工坊准备本地模型，或配置自己的在线服务。
3. **导入并识别。** 选择素材、内容与词库，检查转写、字词时间和说话人结果。
4. **进入字幕工作台。** 校对、拆分或合并，调整字幕与画面，再导出字幕、文稿或压制成片。

默认采用**深葡萄紫**主题，也可以在外观设置中换成暖奶油、暖夜炭、薰衣草或岩灰。

### 必要条件

- **系统：** Windows 10 22H2（19045）及以上的 x64 系统；macOS 15 及以上的 Apple Silicon 设备（实验版，未作 Developer ID 签名与公证，见[说明](docs/deployment/macos-experimental.zh-CN.md)）。
- **本地识别：** 模型权重在模型工坊按需下载。SenseVoice 支持 CPU；Windows 上 MOSS、FireRedASR2-AED、Qwen3-ASR 等使用 NVIDIA CUDA；Apple 芯片 Mac 上 MOSS 与 FireRedASR2-AED 使用 Apple GPU（较慢，实验性）。
- **在线服务：** 使用自己的账号或 API 密钥，按服务提供方的规则计费。
- **输出：** SRT、ASS、TXT、JSON、说话人分轨，以及 MP4、MKV、MOV 视频。

### 从源码运行

```powershell
git clone https://github.com/NOTBAD314/2ByteASR.git
cd 2ByteASR
.\setup_environment.bat
.\.venv-main\Scripts\python.exe quick_start.py
```

`main` 是 0.6.5 起的程序源码；与 0.7.1 安装包逐字节对应的构建来源是 tag `v0.7.1`，完整构建输入在 Release 的 `2ByteASR-Source-0.7.1.zip`。自有代码为 GPL-3.0-only，另有针对 Remotion/GSAP 的附加许可，见 [PROJECT_LICENSE.md](PROJECT_LICENSE.md)。

## 模型目录

- **主力转写：** MOSS-Transcribe-Diarize（多人与说话人区分）、SenseVoice Small（可用 CPU）、FireRedASR2-AED、Qwen3-ASR 1.7B、Paraformer Large、Whisper large-v3-turbo、Fun-ASR Nano、FireRedASR2-LLM、GLM-ASR-Nano、Canary-Qwen-2.5B（英语）
- **字词时间轴：** FireRedASR2-AED、Qwen3-ForcedAligner 0.6B、Paraformer Large、Whisper large-v3-turbo
- **文字复核：** Qwen3-ASR 1.7B、SenseVoice Small、Whisper large-v3-turbo、FireRedASR2-LLM、Fun-ASR Nano
- **在线接口（自备账号）：** MOSS Pro 云端（MOSI，含说话人）、阿里云百炼 / Qwen Cloud 录音文件识别（Qwen3-ASR 字词时间、Qwen-Audio 3.1 含说话人）、Spark-ASR 2.0、Groq Whisper、OpenAI Transcribe、MAI 2.1（OpenRouter）、OpenAI 兼容接口

模型权重不随程序附带，在模型工坊按需下载，并遵守各自的许可。

## 更多文档与反馈

[界面一览](docs/product-demo.zh-CN.md) · [使用指南](docs/product-guide.zh-CN.md) · [源码提供说明](SOURCE_DELIVERY.md) · [反馈问题](https://github.com/NOTBAD314/2ByteASR/issues)

反馈时附上版本、模型、复现步骤和截图，方便定位问题。

项目自有代码采用 **GPL-3.0-only**（[标准英文全文](LICENSE) / [适用范围](PROJECT_LICENSE.md)）。官方版本免费提供；允许依 GPL 商用、修改和收费分发，分发时须履行对应源码等条件。私人修改无需公开，普通字幕、视频和图片不会仅因使用本软件生成而自动适用 GPL。第三方组件保留各自许可：高保真渲染用到的 Remotion 对个人和员工不超过 3 人的营利组织免费，更大的营利组织需另购其 Company License；GSAP 采用其标准条款。详见[第三方说明](THIRD_PARTY_NOTICES.md)与[模型许可表](licenses/MODELS.md)，完整安装包的分发材料仍在整理中（[分发状态](licenses/DISTRIBUTION-STATUS.md)）。
