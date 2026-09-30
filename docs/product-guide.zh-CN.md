# 兔白字幕：安装、模型与高级使用

## 安装与准备

1. 在[版本页](https://github.com/NOTBAD314/2ByteASR/releases)选择安装包，运行 Setup。
2. 打开模型工坊，下载所选模型的权重并准备运行环境。
3. 使用在线服务时，填写对应服务的账号或 API 密钥。
4. 导入视频或音频，选择识别方案，开始生成字幕。

默认采用深葡萄紫主题。进入外观设置，可以更换配色。

## 选择模型

主力转写、字词时间轴和文字复核各有用途，可以按语言、设备与接口条件自由组合。

| 角色 | 作用 | 常用方案 |
| --- | --- | --- |
| 主力转写 | 识别语音、生成文本，按模型提供说话人区分 | MOSS、SenseVoice、Whisper |
| 字词时间轴 | 定位字词边界，辅助断句和时间校准 | FireRedASR2-AED、Paraformer、独立对齐器 |
| 文字复核 | 对照文本候选，校对错词、专名和上下文 | Qwen3-ASR、本地或在线复核方案 |

在模型工坊查看各方案的运行要求。SenseVoice 支持 CPU；MOSS、FireRedASR2-AED、Qwen3-ASR 1.7B 和 Qwen3-ForcedAligner 使用 NVIDIA CUDA。模型下载完成后，本地识别可离线运行。

AI 断句、文本校对、术语搜索、字幕设计和片段分析按需启用。在线服务使用自己的账号或密钥，并按服务提供方的规则计费；相应素材或文本会发送到所选服务。

## 输入与输出

| 用途 | 格式 |
| --- | --- |
| 视频输入 | MP4、MOV、MKV、WebM、FLV、AVI |
| 音频输入 | MP3、WAV、M4A、FLAC、AAC |
| Studio 字幕导入 | SRT、ASS |
| 字幕与文稿输出 | SRT、ASS、TXT、JSON、说话人分轨 |
| 视频输出 | MP4、MKV、MOV |

在 Studio 中选择字幕和片段，调整文本、时间、样式与画面，再导出所需格式。工程保留编辑状态，方便下次接着制作。

## 从源码运行与构建

在 Windows 仓库目录中准备环境并启动：

```powershell
.\setup_environment.bat
.\.venv-main\Scripts\python.exe quick_start.py
```

开发与测试步骤见[贡献指南](../CONTRIBUTING.md)，安装包构建见[构建说明](../RELEASING.md)，配置选项见[配置文档](../CONFIGURATION.md)。

## 反馈问题

在[Issues](https://github.com/NOTBAD314/2ByteASR/issues)附上版本、模型、复现步骤和截图，便于定位问题。

[返回产品介绍](../README.md) · [界面与功能展示](product-demo.zh-CN.md) · [第三方组件](../THIRD_PARTY_NOTICES.md)
