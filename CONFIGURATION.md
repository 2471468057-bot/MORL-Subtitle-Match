# 运行配置与任务报告

可编辑的非敏感设置在项目根目录的 `twobyteasr_settings.json`。程序每次启动都会重新读取它，因此修改后直接重新运行即可，不需要改 Python 文件。

该文件只放模型名称、OpenAI 兼容地址和功能开关，绝对不要填写大模型或 Hugging Face 密钥；密钥由运行界面写到本机用户目录，或按 [SECRETS_SETUP.md](SECRETS_SETUP.md) 配置环境变量。

## 模型

- `models.qwen_asr_model`：本地 Qwen3-ASR 复核模型。
- `models.polish_provider` / `models.group_provider`：界面服务商预设；支持百炼、OpenAI 兼容和自定义。
- `models.polish_model`：关闭统一模型开关后使用的独立字幕校对模型。
- `models.group_model`：统一校对与全文断句模型，默认 `qwen3.7-flash-2026-07-15`。
- `models.polish_base_url` / `models.group_base_url`：对应的 OpenAI 兼容 API 根地址。

这些项目都可以在“AI 模型与密钥”折叠区中修改；点击“保存 AI 配置”后会立即写入本机配置，关闭或重启程序后仍会保留，不需要先启动字幕任务。项目内置的校对、术语和断句提示词不会因切换服务商而丢失。

## 开关

- `enable_qwen_asr_reference`：是否启用本地 Qwen3-ASR 文字复核。
- `enable_firered_boundary_refinement`：是否用 FireRed-AED 调整句内边界。
- `show_speaker_labels_in_srt`：是否在总 SRT 每条字幕前写入 `S01` 等标签。
- `output_review_track`：是否默认生成疑似问题复核轨；当前默认值为 `false`，运行窗口中可按本批需求临时开启。
- `unified_glm_processing`：兼容旧配置保留的键名，默认 `true`。开启后字幕校对和全文断句共用统一模型栏的供应商、模型、API 地址与密钥；关闭后可分别选择两套 OpenAI 兼容模型。
- `force_refresh_polish` / `force_refresh_group`：默认绕过相应百炼缓存。仅在更换模型、词表或需要重新请求时打开；它会增加 API 调用。

云端校对默认最多 4 路并发，每批最多 16 条。HTTP 400/401/403/404 属于模型、地址或密钥配置问题，程序会立即停止本轮校对请求并安全保留 ASR 原文，不会对每个批次重复等待。

## 性能

- `moss_parallel_workers`：长音频 MOSS 分块的最大 GPU 进程数，默认 `2`，程序上限也是 2。只有至少两个未缓存分块且显存达到门槛时才启用；短片和缓存命中不会额外加载模型。
- `moss_parallel_min_vram_gb`：启用双路 MOSS 的总显存门槛，默认 `14`。双路异常时会自动停止并回到单路，已经完成的分块从断点继续。
- `qwen_asr_batch_size`：Qwen3-ASR 每轮并行处理的 VAD 短块数，默认 `8`。16GB 显卡实测比旧值 4 的纯转写快约一倍，额外显存约 0.5GB；程序限制最大为 12。
- `parallel_cpu_vad`：让 CPU FireRedVAD 与 GPU MOSS 同时运行。
- `parallel_gpu_asr` / `parallel_gpu_asr_min_vram_gb`：允许 FireRed-AED 与 Qwen3-ASR 同时运行及其显存门槛。
- `parallel_cloud_batches` / `cloud_batch_workers`：云端校对和断句的并发开关与最大路数。

16GB 显存机器建议保留默认值。8–12GB 显存或同时运行其他占显存程序时，可把 `moss_parallel_workers` 改为 `1`；不要靠缩短 MOSS 分块或关闭文字证据来换速度，这两项会直接影响长素材边界和识别稳定性。

一次选择多个素材时，Qwen3-ASR 模型会在队列内复用；任务完成、失败或取消后自动释放。这个行为不需要额外开关，也不会影响单文件显存占用。

## 任务报告

每个处理过的素材都会在项目根目录的 `reports` 文件夹生成两个文件，不再写到素材所在目录：

- `素材名_字幕任务报告.txt`：适合直接查看，列出模型、阶段耗时、缓存命中、输出文件和待复核数。
- `素材名_字幕任务报告.json`：结构化版本，便于以后排查或自动汇总。

报告不包含密钥或原始音频。更完整的队列级 JSONL 运行日志仍保存于 `%LOCALAPPDATA%\2ByteASR\logs`。
