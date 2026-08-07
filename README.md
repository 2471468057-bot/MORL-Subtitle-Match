<div align="center">

<img src="assets/2byteasr-icon-transparent.png" width="96" alt="2ByteASR logo" />

# 2ByteASR

**拖进视频，出字幕 —— 面向中文游戏实况的本地字幕流水线**

[中文](README.md) · [English](README_EN.md) · [日本語](README_JA.md)

![License](https://img.shields.io/badge/license-Apache--2.0-green)
![Platform](https://img.shields.io/badge/platform-Windows-blue)
![Python](https://img.shields.io/badge/python-3.10%20%7C%203.12-blue)
![GPU](https://img.shields.io/badge/GPU-NVIDIA%20CUDA-brightgreen)

</div>

---

## ✨ 特性

- 🎙️ **说话人分离**：自动识别多位主播，输出「主播分轨 SRT」，同时说话也不丢
- 🧬 **三路转写交叉校验**：MOSS 骨架 + FireRed 字级证据 + Qwen3-ASR 本地复核，多模型仲裁减少错字
- 🔒 **隐私优先**：模型全部本地运行；云端校对可选且只发送文本，密钥用 Windows DPAPI 加密保存
- 🖥️ **一键安装**：Release 安装包自动配置环境并下载模型，断点续传
- 📄 **多格式输出**：剪映文稿 TXT、总 SRT、主播分轨 SRT、任务报告（含每个错误修正的可追溯记录）
- ⚡ **断点续跑**：同一素材二次运行命中阶段缓存，通常快很多

## 🖼️ 界面一览

| 工作台 | 处理进度 | 完成结果 |
| --- | --- | --- |
| ![工作台](assets/screenshots/ui-settings.png) | ![进度](assets/screenshots/ui-progress.png) | ![结果](assets/screenshots/ui-result.png) |

## 🔄 处理流程

```mermaid
flowchart LR
  A[视频/音频] --> B[统一 16kHz 音频]
  B --> C[MOSS 转写 + 说话人分离]
  C --> D[FireRed 字级证据]
  C --> E[Qwen3-ASR 本地复核]
  D --> F[多模型仲裁]
  E --> F
  F --> G[云端受限校对 *]
  G --> H[断句 + 时间轴校准]
  H --> I[剪映文稿 / SRT / 主播分轨]
```

> \* 云端校对默认可用；开启后仅发送转写文本，原文保护与断句约束由内置只读提示词强制保证。

## 🚀 快速开始

### 方式一：下载安装包（推荐）

1. 从 [Releases](https://github.com/NOTBAD314/2ByteASR/releases) 下载 `2ByteASR-Setup-<版本>.exe` 并安装
2. 保持勾选「首次配置环境并下载模型」，等待约 11GB 模型下载完成（可断点续传）
3. 双击桌面「2ByteASR」，把视频或音频**拖进窗口**，点击开始

### 方式二：从源码运行

```bat
setup_environment.bat    :: 创建 Python 环境并获取固定版本依赖
download_models.bat      :: 下载模型（输入 YES 确认）
install_shortcut.bat     :: 安装桌面快捷方式
```

之后把媒体文件直接拖到 `2ByteASR.bat` 上即可。

### 系统要求

- Windows 10/11 x64
- NVIDIA 显卡（建议 8GB+ 显存；**显存更低或显卡稍弱也能运行，只是更慢**）
- 模型约 11GB，建议安装盘预留 15GB 以上

## 🗣️ 主播声纹（可选）

想让人名跟着声音走？每人放一段 5–14 秒的清晰独白 WAV 到 `%LOCALAPPDATA%\2ByteASR\host_voiceprints\samples\`，然后运行：

```bat
.venv-main\Scripts\python.exe register_host_voiceprint.py
```

不注册也可以分轨，只是跨视频时 `S01/S02` 标签不保证对应同一位主播。

## ☁️ 云端数据

本地模型不联网。开启云端校对与全文断句时，转写文本会发送到你选择的 OpenAI 兼容服务（默认阿里云百炼），并附带只读提示词；API 密钥仅保存在本机（DPAPI 加密），报告与日志不含密钥。

## 🛠️ 开发

```bat
run_tests.bat                                    :: 离线单元测试（无需 GPU/网络）
python scripts\check_release_hygiene.py          :: 发布前检查
```

详细文档：[架构](ARCHITECTURE.md) · [配置](CONFIGURATION.md) · [更新维护](UPDATING.md) · [安全](SECURITY.md)

## 📄 许可证

[Apache-2.0](LICENSE) · 第三方归属见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)
