# 2ByteASR 代码结构

## 运行入口

```text
2ByteASR.bat
  → quick_start.py
  → twobyteasr.ui.MainWindow
  → twobyteasr.service.run_media_queue
  → moss_firered_pipeline.process_media
```

`service.py` 是 UI 与字幕核心之间的唯一队列接口。未来更换界面时应继续调用服务层，不要从 UI 直接调用模型或字幕规则。

## 模块职责

| 模块 | 只负责 |
|---|---|
| `twobyteasr/ui.py` | 设置、拖放、进度和结果展示 |
| `twobyteasr/service.py` | 队列、取消、失败隔离、覆盖策略和结构化事件 |
| `twobyteasr/runtime.py` | 每批任务唯一的 `RuntimeContext`、作用域与旧变量兼容镜像 |
| `moss_firered_pipeline.py` | MOSS/FireRed/声纹组合及 11 阶段媒体流程 |
| `twobyteasr/pipeline_runtime.py` | 通用并行调度、最终阶段调用顺序、事务输出与报告收尾 |
| `twobyteasr/asr.py` | FireRed-AED 与 Qwen3-ASR 本地文字证据 |
| `twobyteasr/correction.py` | 校对兼容门面、批次与 JSON/相似度基础工具 |
| `twobyteasr/domain_terms.py` | 游戏术语发现、来源校验与安全映射 |
| `twobyteasr/correction_safety.py` | 多 ASR 共识、数字保护与校对编辑裁决 |
| `twobyteasr/polishing.py` | 云端校对请求、缓存及校对流程编排 |
| `twobyteasr/segmentation.py` | 本地语义边界规则及断句兼容门面 |
| `twobyteasr/segmentation_alignment.py` | FireRed/VAD 字符锚点、停顿与时间轴对齐 |
| `twobyteasr/grouping.py` | 云端模型断句请求、回退和分组编排 |
| `twobyteasr/cue_cleanup.py` | 孤字、两字条、悬挂词和重复短句清理 |
| `twobyteasr/text_rules.py` | 繁简/数字规范、重复检测与编辑安全规则 |
| `twobyteasr/text_similarity.py` | 无循环依赖的拼音文本与编辑距离工具 |
| `twobyteasr/term_constants.py` | 校对安全与术语发现共享的只读阈值 |
| `twobyteasr/timing.py` | 时间轴量化、VAD 起音、尾帧和显示间隙 |
| `twobyteasr/output.py` | 最终校验、SRT/TXT/分轨与复核轨 |
| `twobyteasr/cache.py` | 媒体身份、阶段缓存、事件观察器和日志 |
| `twobyteasr/reporting.py` | 每个素材的 TXT/JSON 任务报告 |
| `subtitle_core.py` | 兼容门面、共享配置和旧公开 API；不再放新的大段算法 |

## 性能依赖图

```text
统一 16k 音频
  ├─ MOSS（GPU，长素材最多双路分块） ─┐
  ├─ FireRedVAD（CPU，与 MOSS 并行） ─┼─ 主播主稿
  └─ FireRed-AED（GPU） ───────────────┘
          └─ Qwen3-ASR（与 FireRed 并行，VAD 短块 batch=8）

主播主稿 → 云端模型受限校对 → 云端模型全文断句 → 本地时间轴保护 → 事务输出
```

MOSS 与 FireRed/Qwen 不全部重叠运行。实测四个 GPU 工作负载同时运行虽未超过 14GB，但因计算资源争用，墙钟时间比当前两组顺序执行更长。

同一队列包含多个素材时，服务层会开启本地 ASR 模型会话：Qwen3-ASR 在第一个实际需要它的素材中加载，后续素材复用，队列完成、失败或取消后统一释放。单素材不保留会话。

## 修改边界

- UI 只消费 `PipelineEvent`，不得解析控制台文字判断状态。
- 模型阶段只返回证据，不直接写最终字幕文件。
- 云端模型不得改动说话人、时间戳或原文字序；本地保护失败时回退到 ASR 原文。
- 新的性能开关放入 `twobyteasr_settings.json`，并写入任务报告快照。
- 会改变模型输出的参数必须进入对应缓存签名。
- 新增并行必须有串行回退，并验证真实墙钟时间，而不只看单阶段速度。

## 运行状态

`service.run_media_queue` 会为每个队列创建独立的 `RuntimeContext`，并显式传给媒体流水线。游戏名、术语开关、缓存刷新、预计主播数、取消令牌、事件日志和复核项都以该对象为准；并行阶段共享同一个对象，不再依赖 `import *` 时复制出的可变全局值。队列成功、失败或取消后都会恢复此前上下文。

`subtitle_core.py` 中同名的 `RUNTIME_*` 属性目前仍会同步更新，用于旧入口和第三方调用兼容；新的阶段代码不得再从兼容门面复制这些可变值。

## 当前仍需逐步偿还的技术债

`subtitle_core.py` 仍是兼容门面，阶段模块暂时通过它共享只读常量和旧公开函数。本轮已引入显式 `RuntimeContext` 并迁移高频可变状态；后续可把模型常量和纯文本工具改为按模块显式导入，最终移除剩余的 `import *`。

`twobyteasr/ui.py` 的 `MainWindow` 仍较长。后续可按设置页、进度页、结果页拆成三个 QWidget，但应保持 `service.run_media_queue` 接口不变。
