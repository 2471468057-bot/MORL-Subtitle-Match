# 2ByteASR

面向中文游戏实况的 Windows 本地字幕流水线。它以 MOSS 的说话人分段和外层时间轴为骨架，结合 FireRed 与 Qwen 的文字证据，输出剪映文稿、总 SRT、主播分轨 SRT、可选复核轨和可追溯任务报告。

提供三种入口：`2ByteASR.exe` 是带独立 Logo、可固定到 Windows 任务栏的推荐入口；`sdewa.bat` 保留“先选文件再进入工作台”的原流程；`2ByteASR.bat` 是兼容入口。工作台可把一个或多个视频/音频拖入窗口后开始。文件选择器第一次默认打开桌面，以后自动记住上一次素材所在文件夹。设置、结构化进度、可安全取消和结果汇总共用 `twobyteasr.service`；原控制台诊断输出也会实时显示在运行页的“完整运行日志”分框中。

## 处理流程

```text
媒体文件
  → 统一 16 kHz 音频
  → MOSS 转写与说话人分离
  → FireRedVAD + FireRedASR2-AED
  → Qwen3-ASR-1.7B 本地复核
  → 百炼 qwen3.7-flash-2026-07-15 受限校对（可切换 OpenAI 兼容模型）
  → 百炼 qwen3.7-flash-2026-07-15 全文断句
  → 时间轴校准与事务式导出
```

MOSS 的说话人段和外层时间是主骨架；FireRed 与本地 Qwen3-ASR 只提供交叉证据，不会自行接管说话人边界。默认由百炼 `qwen3.7-flash-2026-07-15` 同时承担受限校对与全文断句，不使用智谱独立接口，也不使用 `qwen-plus`；关闭“同一云端模型”开关后，界面仍允许为两个阶段分别选择其他 OpenAI 兼容服务与模型。

## 系统要求

- Windows 10/11 x64；
- NVIDIA CUDA GPU，建议 16 GB 显存；
- 模型约占 11 GB，下载前建议安装盘至少有 15 GB 可用空间；
- NVIDIA 驱动已安装；安装器可通过 Windows Package Manager 自动补齐 `uv`、Git 和 FFmpeg/FFprobe。

源码安装脚本只检查系统组件；Release 安装器的首次配置脚本会明确调用 `winget` 安装缺少的公开依赖。

## 安装

### 推荐：下载 Windows 安装包

从 GitHub Releases 下载 `2ByteASR-Setup-<版本>.exe`，双击安装。安装器默认放到当前用户的 `%LOCALAPPDATA%\Programs\2ByteASR`，不要求管理员权限，并创建开始菜单和桌面快捷方式。

安装结束时保持“首次配置环境并下载约 11 GB 模型”勾选。随后出现的窗口会自动补齐 `uv`、Git、FFmpeg，创建两套固定 Python 环境并下载模型；下载中断后再次运行桌面的 2ByteASR，选择继续配置即可断点续传。NVIDIA 驱动需要用户自行安装。

GitHub 的单个 Release 安装包不内置约 11 GB 模型，因此第一次配置需要联网；程序代码与模型版本仍由 [`dependencies.lock.json`](dependencies.lock.json) 固定。

### 更新已有安装

下载新版安装包后直接覆盖安装，不要先卸载。程序会保留现有模型、Python 环境、设置和词表；固定版本未变化的模型会校验后跳过，不会重新下载 11 GB。只有某个模型 revision 确实升级时，才下载该模型。完整维护规则见 [UPDATING.md](UPDATING.md)。

### 开发者：从源码安装

#### 1. 配置大模型密钥

首次运行时可以展开“AI 模型与密钥”，选择服务商、填写模型名称、API 地址和密钥，再点击“保存 AI 配置”。保存会立即生效并在重启后保留，不需要先生成一次字幕。默认百炼配置也可以继续按照 [SECRETS_SETUP.md](SECRETS_SETUP.md) 设置 `DASHSCOPE_API_KEY`。所有本地模型仓库均公开，无需登录；只有遇到 Hugging Face 限流时才需要可选的 `HF_TOKEN`。

#### 2. 安装程序环境

双击：

```bat
setup_environment.bat
```

它会：

- 创建 `.venv-main`（Python 3.10）和 `.venv-moss`（Python 3.12）；
- 按 [`dependencies.lock.json`](dependencies.lock.json) 获取固定提交的 MOSS 与 FireRedASR2S 源码；
- 安装主流程及 MOSS 的 CUDA 依赖；
- 不下载模型权重。

旧入口 `setup_moss_firered.bat` 仍可使用，但现在只作为环境安装兼容入口。

#### 3. 下载模型

双击：

```bat
download_models.bat
```

脚本显示磁盘空间和下载量，输入 `YES` 后下载五个必需模型。每个模型固定到版本清单中的提交；中断后重新运行会继续并复用已经完成的文件。

只检查模型是否完整：

```bat
download_models.bat -VerifyOnly
```

#### 4. 启动

安装桌面快捷方式（同时构建带 Logo 的轻量启动器）：

```bat
install_shortcut.bat
```

随后右键桌面的“2ByteASR”快捷方式，选择“固定到任务栏”。以后点击任务栏图标即可打开工作台并拖入素材。也可以直接双击项目根目录的：

```bat
2ByteASR.exe
```

兼容入口：

```bat
2ByteASR.bat
```

也可以把媒体文件直接拖到 `2ByteASR.bat` 上。这个入口省去启动前的预检子进程和文件选择步骤；完整护栏自测会在首次点击“开始生成字幕”后于后台执行。

保留原来的“先选择素材”入口：

```bat
sdewa.bat
```

正常启动使用 `pythonw.exe`；MOSS、FFmpeg/FFprobe 和可选复核工作进程也使用 Windows 无窗口模式，运行日志统一显示在 2ByteASR 界面内。需要排查启动问题时可以保留传统控制台：

```bat
sdewa.bat --console
```

启动器不会回退系统 Python。缺少环境、第三方源码、FFmpeg、NVIDIA 驱动或任一模型时，它会停止并明确提示应运行哪个脚本。

## 输出位置

| 内容 | 位置 |
| --- | --- |
| 剪映 TXT、总 SRT、主播分轨 SRT | 与原媒体相同的目录 |
| 疑似吞字幕复核轨 | 项目内 `review_tracks/` |
| 每个媒体的 TXT/JSON 任务报告 | 项目内 `reports/` |
| 缓存、事件日志、学习术语、声纹 | `%LOCALAPPDATA%\2ByteASR` |

总 SRT 按单条剪辑轨输出，不保留跨主播显示重叠；每一位检测到的主播都会生成独立分轨 SRT，并保留真实同时说话和抢话时间。

报告不包含 API 密钥或原始音频，但包含媒体绝对路径和识别过程元数据；分享前仍应检查隐私内容。

## 本批内容设置

- 游戏/内容名称留空时使用通用模式，不读取上一次游戏的背景和词表；
- 输入名称后可启用本地候选与联网官方词汇复核；
- 复核轨默认关闭，不影响总字幕和主播分轨；
- 预计主播人数支持自动或手动指定 1–6 人；自动模式最多保留 4 位持续出现的主播，三主播直播建议明确选择“3”；
- 强制刷新缓存只应在模型、提示词或词表变更后使用。
- AI 配置默认折叠；缺少密钥时会自动展开。模型、服务商和地址写入项目配置，密钥使用 Windows DPAPI 加密后写入 `%LOCALAPPDATA%\2ByteASR\secrets.dat`；
- 默认开启“同一云端模型负责字幕校对与全文断句”，只需维护一套可用的模型地址与密钥；HTTP 403 等配置错误会立即熔断并保留 ASR 原文，不会继续逐批重试；
- 校对和断句始终附带项目内置的只读提示词，切换模型不会绕过原文保护和断句约束。

模型名称、开关和性能参数集中在 [`twobyteasr_settings.json`](twobyteasr_settings.json)，说明见 [CONFIGURATION.md](CONFIGURATION.md)。

### 性能建议

- RTX 5070 Ti 16GB 等显卡保持默认配置即可：长素材的 MOSS 分块会自动双路运行；短片、低显存或只有一个未缓存分块时自动保持单路。
- Qwen3-ASR 默认每批处理 8 个 VAD 短块；实测相比旧值 4，纯转写约快一倍，FireRed 与 Qwen 同时运行峰值约 7.1GB。
- 第一次处理素材需要运行本地模型；同一素材再次运行会命中阶段缓存，通常快很多。只有模型、规则、音频或强制刷新发生变化时才应重算。
- 双路 MOSS 如果遇到显存不足或子进程异常，会自动回到单路并继续已有分块断点，不需要手动重跑。
- 关闭本地 Qwen/FireRed 或减少 MOSS 重叠虽然还能更快，但会削弱文字交叉证据或长音频边界稳定性，因此不是默认性能方案。

## 主播声纹

默认显示名称为 `S01=主播A`、`S02=主播B`。每人准备一段 5–14 秒、只有本人清晰说话且尽量没有 BGM 的 WAV：

```text
%LOCALAPPDATA%\2ByteASR\host_voiceprints\samples\主播A.wav
%LOCALAPPDATA%\2ByteASR\host_voiceprints\samples\主播B.wav
```

然后运行：

```bat
.venv-main\Scripts\python.exe register_host_voiceprint.py
```

未注册时仍可分轨，但 MOSS 的 `S01/S02` 不保证跨视频恒定对应同一位主播。

## 云端数据

字幕校对和全文断句会向界面中选择的 OpenAI 兼容服务发送转写文本、项目内置提示词及必要上下文。默认服务为阿里云百炼。如果配置可选的 `FIRERED_LLM_ENDPOINT`，争议音频片段还会发送到该端点。模型、缓存和声纹均默认留在本机。

FireRedASR2-LLM 的可选本地复核模式需要手动把模型放到 `models/FireRedASR2-LLM/`（该模型不在 `dependencies.lock.json` 与下载脚本中），且要求 24 GB 以上显存；模型或显存条件不足时会自动跳过，争议片段仍会保留给云端受限校对并列入复核清单。

## 常见问题

### `sdewa.bat` 提示缺少 `.venv-main`

运行 `setup_environment.bat`，不要改成系统 Python。主流程固定使用 Python 3.10。

### 提示缺少模型关键文件

运行 `download_models.bat`。它会跳过已完成内容并继续未完成的下载。

### 提示 `No module named 'kaldiio'` 或 `kaldi_native_fbank`

这是 FireRed VAD/AED 的主环境依赖缺失。重新运行 `setup_environment.bat` 即可补齐；新版启动预检也会在选择素材前直接指出缺少的包。

### 找不到 FFmpeg 或 FFprobe

安装完整 FFmpeg，并确认新打开的命令行中 `ffmpeg -version` 与 `ffprobe -version` 都能执行。

### 处理失败后已有字幕会不会损坏

不会。输出使用临时文件和备份统一替换；失败时会恢复本批写入前的文件。

### 最终校验提示漏字、重复或调序

程序会先删除同一说话人的高重叠 MOSS 副本，再严格核对每位主播的源文和最终字幕。若云端断句或超限修复仍造成调序，会自动放弃该断句结果，从已经校对的本地源段重建字幕并重新校验；不会靠关闭校验来强行写出。报告中的 `final_text_conservation_recovery` 事件表示自动自愈曾被启用。

## 开发与测试

```bat
run_tests.bat
```

单元测试不下载模型、不访问网络、不要求 GPU。发布检查：

```bat
python scripts\check_release_hygiene.py
```

构建 Windows 安装包需要 Inno Setup 6：

```powershell
.\scripts\build_installer.ps1 -Version 0.1.0
```

推送 `v0.1.0` 这类标签后，[GitHub Actions](.github/workflows/release.yml) 会在 Windows 上重新运行测试、构建安装包，并把 `.exe` 附加到 GitHub Release。

第三方归属见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)，贡献说明见 [CONTRIBUTING.md](CONTRIBUTING.md)。
代码模块、性能依赖图与修改边界见 [ARCHITECTURE.md](ARCHITECTURE.md)。
