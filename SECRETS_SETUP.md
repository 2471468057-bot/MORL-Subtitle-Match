# 密钥配置说明

默认模型组合只需要阿里云百炼的 `DASHSCOPE_API_KEY`：

- `qwen3.7-flash-2026-07-15`：受限字幕校对、全文断句与断句校验

默认配置不使用智谱独立 Key，也不使用 `qwen-plus`。如在界面中选择其他 OpenAI 兼容服务，可分别填写校对和断句密钥。

## 推荐：在运行界面填写

展开“AI 模型与密钥”，填写本次使用的 API Key，再点击“保存 AI 配置”。新填写的值会通过 Windows DPAPI（当前用户作用域）加密并保存在 `%LOCALAPPDATA%\2ByteASR\secrets.dat`，不会写入项目配置、任务报告或 Git，也不需要先生成字幕。可选择两个阶段共用同一密钥，也可以分别填写。

## 推荐：用户环境变量

```powershell
[System.Environment]::SetEnvironmentVariable("DASHSCOPE_API_KEY", "<your-dashscope-key>", "User")
[System.Environment]::SetEnvironmentVariable("HF_TOKEN", "<your-hugging-face-token>", "User")
```

重开终端、Codex 或 bat 窗口后生效。仅在当前会话临时设置：

```powershell
$env:DASHSCOPE_API_KEY = "<your-dashscope-key>"
$env:HF_TOKEN = "<your-hugging-face-token>"
```

本地模型均已下载时，通常只需要 `DASHSCOPE_API_KEY`。

程序不再要求或建议手工编辑明文密钥文件。旧版 `%LOCALAPPDATA%\2ByteASR\secrets.json` 会在用户下一次点击“保存 AI 配置”后迁移到 DPAPI 密文并删除。

优先级为：阶段专用环境变量 > `DASHSCOPE_API_KEY` 环境变量 > DPAPI 中的阶段专用值 > DPAPI 中的 `DASHSCOPE_API_KEY`。

不要把历史密钥、明文备份或含密钥的截图同步到 Git、网盘或公开视频素材目录。
