# MORL 字幕匹配

<div align="center">

<img src="assets/morl-icon-256.png" width="96" alt="MORL 字幕匹配图标">

**文稿 + 时间轴，一次对齐；字幕直接进达芬奇。**

</div>

---

## 这是什么

MORL 字幕匹配是一个**桌面字幕工具**，核心工作流只有两件事：

1. **识别** —— 对素材做语音识别，得到字级时间轴；
2. **文稿匹配** —— 你已经有断好句的完整文稿，让软件把文稿的每一行对到时间轴上，
   有字幕就替换、没字幕就生成。

它和 **DaVinci Resolve** 深度协同：所有工程状态都依附于达芬奇时间线，改完立即同步回时间线，
不需要在字幕软件里另外保存工程。

## 主要特性

| 功能 | 说明 |
| --- | --- |
| **文稿匹配** | 粘贴已断句文稿，自动按字级时间对齐；有字幕替换、无字幕生成，Ctrl+Z 一步撤销 |
| **语音识别** | 支持 MOSS / FireRed / SenseVoice / Qwen3-ASR 等本地模型，也可接云端 API |
| **说话人区分** | 多人对话自动分轨，或保留模型原始标签 |
| **达芬奇实时同步** | 字幕改动直接写回达芬奇时间线，跟随播放头与时间线切换 |
| **竖屏 / 横屏** | 自动按时间线画幅比例渲染预览 |
| **样式编辑** | 字体、大小、描边、位置、动效，所见即所得 |

## 下载与安装

### 1. 获取源码

```bash
git clone https://github.com/2471468057-bot/MORL-Subtitle-Match.git
cd MORL-Subtitle-Match
```

> **本仓库不包含模型文件。** 模型体积很大（单个从几百 MB 到数 GB），
> 需要你在本机按需下载，见下一节。

### 2. 安装运行环境

```bat
setup_environment.bat
```

会创建独立 Python 运行环境并安装依赖。首次运行需要几分钟。

### 3. 下载模型

**模型不随仓库分发**，请按需下载：

```bat
download_models.bat
```

或在软件内打开「模型工坊」，按角色选择需要的模型下载：

| 用途 | 模型 | 大致体积 |
| --- | --- | --- |
| 主转写（中文/多人） | MOSS-Transcribe-Diarize | 约 1.7 GB |
| 字级时间轴 | FireRedASR2-AED | 约 4.4 GB |
| 时间轴对齐 | Qwen3-ForcedAligner-0.6B | 约 1.2 GB |
| CPU 轻量识别 | SenseVoiceSmall | 约 0.9 GB |
| 日语/英语时间轴 | Qwen3-ASR / Qwen3 对齐 | 视选择而定 |

云端 API 模式（阿里云百炼、OpenAI 兼容服务等）**不需要下载本地模型**，
在「设置 → 模型工坊 → 在线 API」里填自己的 Key 即可。

### 4. 启动

```bat
quick_start.py
```

或直接运行打包好的 `MORL-Subtitle-Match.exe`（如果使用安装版）。

## 与 DaVinci Resolve 协同

1. 在达芬奇里打开你的时间线；
2. 菜单「工作区 → 工作流集成 → MORL 字幕匹配」；
3. 软件启动后会自动读取当前时间线的画幅、帧率与已有字幕；
4. 在左侧「字幕列表」里编辑，或在无字幕时点「识别字幕 / 文稿匹配」；
5. 所有改动自动同步回达芬奇时间线。

> 需要达芬奇 Studio 版本（免费版不支持工作流集成插件）。

## 系统要求

| 项目 | 要求 |
| --- | --- |
| 操作系统 | Windows 10 22H2 或更新（64 位） |
| 内存 | 建议 16 GB 以上（本地大模型需 32 GB） |
| 显卡 | 本地识别建议 NVIDIA 显卡；纯 CPU 可用 SenseVoice |
| 达芬奇 | DaVinci Resolve Studio 18 或更新 |

## 许可证与来源声明

本项目是 **[2ByteASR（兔白字幕）](https://github.com/NOTBAD314/2ByteASR) 的修改版本**，
原作者为 **NOTBAD314**。

- 原始项目采用 **GNU General Public License v3.0 only（GPL-3.0-only）**；
- 本项目在此基础上修改并继续以 **GPL-3.0-only** 发布，完整许可证见 [LICENSE](LICENSE)；
- **保留原作者版权声明**，见 [PROJECT_LICENSE.md](PROJECT_LICENSE.md)；
- 本项目的修改内容见下方「相对原版的改动」；
- 第三方组件、字体、模型各有自己的许可，见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)
  与 [licenses/](licenses/)。

### 相对原版 2ByteASR 的改动

- 产品名称与图标改为 **MORL 字幕匹配**；
- 移除了首页 / 工程库 / 进度页 / 结果页，主窗口只保留编辑器，所有工程状态依附于达芬奇时间线；
- 新增「文稿匹配」双模式（替换已有字幕 / 现听写生成新工程）；
- 识别设置改为编辑器内弹窗（模型卡片 + 二次弹窗选择），不再跳转独立页面；
- 界面自适应重做：三栏按比例分配、窄窗口图标化、列表三档密度；
- 修复首帧双画面叠影、播放器画幅切换残影、窗口圆角在缩放时卡顿等问题。

原始代码版权归 NOTBAD314 及贡献者所有；本项目修改部分同样以 GPL-3.0-only 授权。

## 致谢

- 原始项目：[2ByteASR / 兔白字幕](https://github.com/NOTBAD314/2ByteASR) by NOTBAD314
- 模型与推理框架：MOSS、FireRedASR、SenseVoice、Qwen3-ASR、FunASR
- 播放与合成：mpv、libass、Qt / PySide6
