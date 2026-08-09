"""UI language overlay (zh / en / ja).

The application's built-in strings are Chinese. This module overlays English
or Japanese translations at runtime by walking the widget tree, so the UI
can switch languages without touching every call site. Strings without a
translation entry are left untouched. The choice persists in
2byteasr_settings.json under the "ui" section.
"""

from __future__ import annotations

from twobyteasr.settings import load_runtime_settings, save_runtime_settings


# Keys are the normalized Chinese source strings; values are translations.
# Keep keys byte-identical to the widget text (after the "●  " decoration
# and surrounding whitespace are stripped).
_TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        # Header / window
        "智能游戏字幕工作台": "Smart Subtitle Workbench",
        "悬停查看字幕生成流程": "Hover to see the subtitle pipeline",
        # Settings page
        "本批字幕内容设置": "Subtitle settings for this batch",
        "本地素材": "Local media",
        "可把视频 / 音频拖到窗口，或点击右侧选择":
            "Drag video / audio into the window, or click to choose",
        "选择素材": "Choose media",
        "游戏 / 内容名称": "Game / Content Name",
        "选择历史记录或内置游戏，也可以直接输入；留空为通用模式":
            "Pick history or a built-in game, or type a new one; empty = generic mode",
        "点击右侧箭头选择历史记录或内置游戏；输入新名称也会自动保存":
            "Click the arrow for history / built-in games; a new name is saved automatically",
        "游戏术语增强": "Game term boost",
        "本地图鉴候选 + 联网复核；PVP 内容建议开启":
            "Local lexicon candidates + online review; recommended for PvP",
        "启用术语增强（本地图鉴候选 + 联网复核，PVP 时勾选）":
            "Enable term boost (local lexicon + online review; tick for PvP)",
        "添加专名（角色名 / 技能名 / 物品名），回车确认":
            "Add a proper noun (character / skill / item), Enter to confirm",
        "手动确认的专名会作为强参考参与本地校对，也会进入联网复核候选":
            "Manually confirmed terms act as strong references in local proofreading and online review",
        "添加术语": "Add term",
        "内置词表（角色 / 技能名）可在“管理已学习术语”中查看":
            "Built-in lexicon (characters / skills) is listed under “Manage learned terms”",
        "输出疑似吞字幕复核轨": "Output review track for suspected missing subtitles",
        "默认关闭，不影响主播分轨；复核轨保存到项目 review_tracks/":
            "Off by default; does not affect speaker tracks; saved to review_tracks/",
        "预计主播人数": "Expected speakers",
        "自动": "Auto",
        "管理已学习术语": "Manage learned terms",
        "AI 模型与密钥": "AI Models & Keys",
        "修改配置": "Edit",
        "同一云端模型负责字幕校对与全文断句（推荐）":
            "One cloud model handles proofreading and punctuation (recommended)",
        "字幕校对模型": "Subtitle proofreading model",
        "全文断句模型": "Sentence segmentation model",
        "两阶段共用新填写的校对密钥":
            "Both stages share the newly entered proofreading key",
        "查看项目内置提示词": "View built-in prompts",
        "保存 AI 配置": "Save AI config",
        "供应商、模型、地址和新填写的密钥可在这里单独保存":
            "Provider, model, URL and a newly entered key can be saved here",
        "服务商预设": "Provider preset",
        "模型名称": "Model name",
        "API 地址": "API URL",
        "API 密钥": "API Key",
        "已配置：": "Configured: ",
        "请输入 API Key": "Enter API Key",
        "测试连接": "Test connection",
        "已配置": "Configured",
        "未配置密钥": "No key configured",
        "密钥已保存": "Key saved",
        "尚未配置密钥": "No key configured yet",
        "阿里云百炼": "Alibaba Bailian",
        "OpenAI 兼容": "OpenAI Compatible",
        "高级设置（缓存与覆盖）": "Advanced (cache & overwrite)",
        "刷新字幕校对缓存": "Refresh proofreading cache",
        "刷新全文断句缓存": "Refresh segmentation cache",
        "覆盖已有结果": "Overwrite existing",
        "跳过已有结果": "Skip existing",
        "已有结果则报错": "Error if exists",
        "已有字幕：": "Existing subtitles: ",
        "开始生成字幕": "Start subtitles",
        "取消": "Cancel",
        # Progress page
        "2ByteASR 正在制作字幕": "2ByteASR is generating subtitles",
        "正在准备任务…": "Preparing task…",
        "本地识别": "Local recognition",
        "转写与主播": "Transcription & speakers",
        "字幕校对": "Subtitle proofreading",
        "模型安全纠错": "Model-safe correction",
        "全文断句": "Sentence segmentation",
        "语义与时间轴": "Semantics & timeline",
        "字幕导出": "Subtitle export",
        "文稿与报告": "Drafts & reports",
        "当前步骤": "Current step",
        "等待启动": "Waiting to start",
        "准备检查运行环境": "Preparing to check the runtime",
        "尚无运行中的子任务": "No running subtask",
        "任务动态": "Task feed",
        "结构化进度": "Structured progress",
        "完整运行日志": "Full run log",
        "已接入原 CMD 输出": "Streaming the original CMD output",
        "运行日志会同步保存在项目报告中":
            "The run log is also saved in the project report",
        "安全取消": "Cancel safely",
        # Result page
        "任务完成": "Task finished",
        "任务与输出": "Tasks & outputs",
        "本次完整运行日志": "Full run log",
        "成功与失败均保留": "Successes and failures are both kept",
        "打开报告目录": "Open report folder",
        "完成": "Done",
        # Workflow strip
        "字幕生成流程": "Subtitle pipeline",
        "语音转写": "Speech transcription",
        "识别错误修正": "Recognition error fixing",
        "添加标点与分句": "Add punctuation & breaks",
        "导出": "Export",
        "生成字幕文件": "Generate subtitle files",
        # Additional static strings (badges, dialogs, status)
        "关闭": "Close",
        "知道了": "Got it",
        "重试": "Retry",
        "准备": "Ready",
        "等待": "Waiting",
        "开始": "Start",
        "回退": "Rollback",
        "跳过": "Skip",
        "失败": "Failed",
        "成功": "Succeeded",
        "警告": "Warning",
        "致命": "Fatal",
        "缓存": "Cache",
        "素材": "Media",
        "运行中": "Running",
        "任务运行中": "Task in progress",
        "当前任务正在处理，请结束后再拖入新素材。": "A task is running; drop new media after it finishes.",
        "并行运行中": "Running in parallel",
        "进行中": "In progress",
        "已完成": "Completed",
        "已确认": "Confirmed",
        "批次": "Batch",
        "等待素材": "Waiting for media",
        "还没有素材": "No media yet",
        "并行": "Parallel",
        "自愈": "Self-heal",
        "已停止写入": "Stopped writing",
        "缓存命中": "Cache hit",
        "缓存写入": "Cache write",
        "联网核验": "Online check",
        "任务提醒": "Task notice",
        "需要处理": "Needs attention",
        "需处理": "Needs attention",
        "处理完成": "Processed",
        "已学习术语": "Learned terms",
        "已学习 / 手动添加的术语": "Learned / manually added terms",
        "展开历史记录与内置游戏": "Expand history and built-in games",
        "当前模型": "Current model",
        "统一校对与断句模型": "Unified proofreading & segmentation model",
        "项目内置提示词": "Built-in prompts",
        "关闭提示": "Dismiss",
        "删除所选": "Delete selected",
        "该术语已存在或内容为空。": "This term already exists or is empty.",
        "请先输入或选择游戏 / 内容名称。": "Choose or type a game / content name first.",
        "要安全取消当前任务并关闭窗口吗？": "Cancel the current task safely and close the window?",
        "请先拖入或选择视频 / 音频文件。": "Drop or choose a video / audio file first.",
        "任务仍在运行": "Task still running",
        "任务已取消": "Task cancelled",
        "任务未能启动": "Task failed to start",
        "字幕生成失败": "Subtitle generation failed",
        "字幕生成完成": "Subtitle generation finished",
        "字幕生成部分失败": "Some subtitle tasks failed",
        "字幕任务已取消": "Subtitle task cancelled",
        "字幕任务异常中止": "Subtitle task aborted",
        "任务结果已同步到工作台": "Results synced to the workbench",
        "有未保存的 AI 配置修改": "Unsaved AI configuration changes",
        "AI 配置与密钥已保存，重启后仍会保留": "AI config and keys saved; they persist after restart",
        "AI 配置未保存": "AI configuration not saved",
        "连接成功": "Connection successful",
        "正在测试…": "Testing…",
        "正在安全取消…": "Cancelling safely…",
        "把视频或音频拖到这里": "Drop video or audio here",
        "把文件放入这里": "Drop files here",
        "支持多选；也可以点击右侧“选择素材”": "Multi-select supported; or click “Choose media” on the right",
        "请选择一个或多个原视频 / 音频文件": "Select one or more source videos / audio files",
        "可继续拖入另一批素材，或点击右侧重新选择": "Drop another batch or click to re-choose",
        "当前没有并行子任务，正在进行阶段切换": "No parallel subtasks; switching stages",
        "将在当前可安全停止的阶段边界退出": "Will exit at the next safe stage boundary",
        "已发出安全取消请求，正在等待当前阶段收尾": "Safe-cancel requested; waiting for the current stage to finish",
        "正在衔接下一阶段": "Preparing the next stage",
        "阶段衔接": "Stage transition",
        # First-run wizard / retry / single instance
        "首次使用引导": "First-run guide",
        "欢迎使用 2ByteASR": "Welcome to 2ByteASR",
        "拖入视频或音频即可生成字幕，下面三步一分钟搞定。":
            "Drop a video or audio file to generate subtitles; three quick steps below.",
        "界面语言：": "Interface language: ",
        "硬件检测：": "Hardware check: ",
        "已检测到 NVIDIA GPU：": "NVIDIA GPU detected: ",
        "未检测到 NVIDIA GPU：将使用 CPU 模式（较慢，可正常出字幕）":
            "No NVIDIA GPU detected: CPU mode will be used (slower but works).",
        "使用方式：\n1. 双击 2ByteASR.exe（或把视频/音频直接拖到它上面）\n2. 可继续拖入更多素材，选择游戏名称后点击「开始生成字幕」\n3. 字幕与剪映文稿生成在素材同目录（xxx_剪映文稿.srt）":
            "How to use:\n1. Double-click 2ByteASR.exe (or drop video/audio onto it)\n2. Drop more media, pick a game name, click “Start subtitles”\n3. Subtitles are saved next to the source media (xxx_剪映文稿.srt)",
        "开始使用": "Get started",
        "重试失败项": "Retry failed",
        "打开字幕目录": "Open subtitle folder",
        "2ByteASR 已在运行": "2ByteASR is already running",
        "检测到另一个 2ByteASR 实例正在运行，请先关闭它再启动。":
            "Another 2ByteASR instance is running; close it before starting again.",
    },
    "ja": {
        # Header / window
        "智能游戏字幕工作台": "スマート字幕ワークベンチ",
        "悬停查看字幕生成流程": "ホバーで字幕生成フローを表示",
        # Settings page
        "本批字幕内容设置": "このバッチの字幕設定",
        "本地素材": "ローカル素材",
        "可把视频 / 音频拖到窗口，或点击右侧选择":
            "動画・音声をウィンドウにドラッグするか、右側をクリックして選択",
        "选择素材": "素材を選択",
        "游戏 / 内容名称": "ゲーム・コンテンツ名",
        "选择历史记录或内置游戏，也可以直接输入；留空为通用模式":
            "履歴または内蔵ゲームを選択、直接入力も可。空欄は汎用モード",
        "点击右侧箭头选择历史记录或内置游戏；输入新名称也会自动保存":
            "右の矢印で履歴・内蔵ゲームを選択。新規入力は自動保存されます",
        "游戏术语增强": "ゲーム用語強化",
        "本地图鉴候选 + 联网复核；PVP 内容建议开启":
            "ローカル図鑑候補＋オンライン再確認。PVP では推奨",
        "启用术语增强（本地图鉴候选 + 联网复核，PVP 时勾选）":
            "用語強化を有効化（ローカル図鑑＋オンライン再確認。PVP 時はオン）",
        "添加专名（角色名 / 技能名 / 物品名），回车确认":
            "固有名詞を追加（キャラ・スキル・アイテム名）、Enter で確定",
        "手动确认的专名会作为强参考参与本地校对，也会进入联网复核候选":
            "手動確定した用語はローカル校閲の強参照になり、オンライン再確認の候補にも入ります",
        "添加术语": "用語を追加",
        "内置词表（角色 / 技能名）可在“管理已学习术语”中查看":
            "内蔵用語表（キャラ・スキル名）は「学習済み用語の管理」で確認できます",
        "输出疑似吞字幕复核轨":
            "字幕欠落が疑われる箇所の確認トラックを出力",
        "默认关闭，不影响主播分轨；复核轨保存到项目 review_tracks/":
            "デフォルトオフ。話者別トラックには影響しません。review_tracks/ に保存",
        "预计主播人数": "予想話者数",
        "自动": "自動",
        "管理已学习术语": "学習済み用語を管理",
        "AI 模型与密钥": "AIモデルとキー",
        "修改配置": "設定変更",
        "同一云端模型负责字幕校对与全文断句（推荐）":
            "1つのクラウドモデルで校閲と全文句読点を担当（推奨）",
        "字幕校对模型": "字幕校閲モデル",
        "全文断句模型": "全文句読点モデル",
        "两阶段共用新填写的校对密钥":
            "両段階で新しい校閲キーを共有",
        "查看项目内置提示词": "内蔵プロンプトを表示",
        "保存 AI 配置": "AI設定を保存",
        "供应商、模型、地址和新填写的密钥可在这里单独保存":
            "プロバイダ・モデル・URL・新規キーをここで個別に保存できます",
        "服务商预设": "プロバイダプリセット",
        "模型名称": "モデル名",
        "API 地址": "API URL",
        "API 密钥": "APIキー",
        "已配置：": "設定済み：",
        "请输入 API Key": "APIキーを入力",
        "测试连接": "接続テスト",
        "已配置": "設定済み",
        "未配置密钥": "キー未設定",
        "密钥已保存": "キー保存済み",
        "尚未配置密钥": "キー未設定",
        "阿里云百炼": "アリババ百炼",
        "OpenAI 兼容": "OpenAI 互換",
        "高级设置（缓存与覆盖）": "詳細設定（キャッシュと上書き）",
        "刷新字幕校对缓存": "校閲キャッシュを更新",
        "刷新全文断句缓存": "句読点キャッシュを更新",
        "覆盖已有结果": "既存結果を上書き",
        "跳过已有结果": "既存結果をスキップ",
        "已有结果则报错": "既存結果ならエラー",
        "已有字幕：": "既存字幕：",
        "开始生成字幕": "字幕生成を開始",
        "取消": "キャンセル",
        # Progress page
        "2ByteASR 正在制作字幕": "2ByteASR は字幕を生成中",
        "正在准备任务…": "タスクを準備中…",
        "本地识别": "ローカル認識",
        "转写与主播": "転写と話者",
        "字幕校对": "字幕校閲",
        "模型安全纠错": "モデル安全訂正",
        "全文断句": "全文句読点",
        "语义与时间轴": "意味とタイムライン",
        "字幕导出": "字幕エクスポート",
        "文稿与报告": "文稿とレポート",
        "当前步骤": "現在のステップ",
        "等待启动": "起動待ち",
        "准备检查运行环境": "実行環境を確認中",
        "尚无运行中的子任务": "実行中のサブタスクはありません",
        "任务动态": "タスク状況",
        "结构化进度": "構造化進捗",
        "完整运行日志": "完全な実行ログ",
        "已接入原 CMD 输出": "元の CMD 出力を表示",
        "运行日志会同步保存在项目报告中":
            "実行ログはプロジェクトレポートにも保存されます",
        "安全取消": "安全にキャンセル",
        # Result page
        "任务完成": "タスク完了",
        "任务与输出": "タスクと出力",
        "本次完整运行日志": "今回の完全な実行ログ",
        "成功与失败均保留": "成功も失敗も保持",
        "打开报告目录": "レポートフォルダを開く",
        "完成": "完了",
        # Workflow strip
        "字幕生成流程": "字幕生成フロー",
        "语音转写": "音声転写",
        "识别错误修正": "認識エラー修正",
        "添加标点与分句": "句読点と分句を追加",
        "导出": "エクスポート",
        "生成字幕文件": "字幕ファイルを生成",
        # Additional static strings (badges, dialogs, status)
        "关闭": "閉じる",
        "知道了": "了解",
        "重试": "再試行",
        "准备": "準備",
        "等待": "待機",
        "开始": "開始",
        "回退": "ロールバック",
        "跳过": "スキップ",
        "失败": "失敗",
        "成功": "成功",
        "警告": "警告",
        "致命": "致命的",
        "缓存": "キャッシュ",
        "素材": "素材",
        "运行中": "実行中",
        "任务运行中": "タスク実行中",
        "当前任务正在处理，请结束后再拖入新素材。": "タスク実行中です。終了後に素材をドロップしてください。",
        "并行运行中": "並列実行中",
        "进行中": "進行中",
        "已完成": "完了",
        "已确认": "確認済み",
        "批次": "バッチ",
        "等待素材": "素材待ち",
        "还没有素材": "素材がまだありません",
        "并行": "並列",
        "自愈": "自己修復",
        "已停止写入": "書き込み停止",
        "缓存命中": "キャッシュヒット",
        "缓存写入": "キャッシュ書き込み",
        "联网核验": "オンライン確認",
        "任务提醒": "タスク通知",
        "需要处理": "処理が必要",
        "需处理": "処理が必要",
        "处理完成": "処理完了",
        "已学习术语": "学習済み用語",
        "已学习 / 手动添加的术语": "学習済み・手動追加の用語",
        "展开历史记录与内置游戏": "履歴と内蔵ゲームを展開",
        "当前模型": "現在のモデル",
        "统一校对与断句模型": "統一校閲・句読点モデル",
        "项目内置提示词": "内蔵プロンプト",
        "关闭提示": "閉じる",
        "删除所选": "選択を削除",
        "该术语已存在或内容为空。": "この用語は既に存在するか、空です。",
        "请先输入或选择游戏 / 内容名称。": "先にゲーム・コンテンツ名を入力または選択してください。",
        "要安全取消当前任务并关闭窗口吗？": "現在のタスクを安全にキャンセルしてウィンドウを閉じますか？",
        "请先拖入或选择视频 / 音频文件。": "先に動画・音声ファイルをドロップまたは選択してください。",
        "任务仍在运行": "タスクは実行中です",
        "任务已取消": "タスクはキャンセルされました",
        "任务未能启动": "タスクを開始できませんでした",
        "字幕生成失败": "字幕生成に失敗しました",
        "字幕生成完成": "字幕生成が完了しました",
        "字幕生成部分失败": "一部の字幕タスクが失敗しました",
        "字幕任务已取消": "字幕タスクはキャンセルされました",
        "字幕任务异常中止": "字幕タスクが異常終了しました",
        "任务结果已同步到工作台": "結果はワークベンチに同期されました",
        "有未保存的 AI 配置修改": "未保存の AI 設定変更があります",
        "AI 配置与密钥已保存，重启后仍会保留": "AI 設定とキーを保存しました。再起動後も保持されます",
        "AI 配置未保存": "AI 設定は未保存です",
        "连接成功": "接続成功",
        "正在测试…": "テスト中…",
        "正在安全取消…": "安全にキャンセル中…",
        "把视频或音频拖到这里": "動画・音声をここにドロップ",
        "把文件放入这里": "ファイルをここにドロップ",
        "支持多选；也可以点击右侧“选择素材”": "複数選択可。右側の「素材を選択」も利用できます",
        "请选择一个或多个原视频 / 音频文件": "元の動画・音声ファイルを1つ以上選択してください",
        "可继续拖入另一批素材，或点击右侧重新选择": "別の素材をドロップするか、右側から選び直せます",
        "当前没有并行子任务，正在进行阶段切换": "並列サブタスクはなく、段階を切り替え中です",
        "将在当前可安全停止的阶段边界退出": "安全に停止できる段階境界で終了します",
        "已发出安全取消请求，正在等待当前阶段收尾": "安全キャンセルを要求しました。現在の段階の完了を待っています",
        "正在衔接下一阶段": "次の段階を準備中",
        "阶段衔接": "段階遷移",
        # First-run wizard / retry / single instance
        "首次使用引导": "初回セットアップ",
        "欢迎使用 2ByteASR": "2ByteASR へようこそ",
        "拖入视频或音频即可生成字幕，下面三步一分钟搞定。":
            "動画・音声をドロップすると字幕を生成できます。次の3ステップで完了します。",
        "界面语言：": "表示言語：",
        "硬件检测：": "ハードウェア確認：",
        "已检测到 NVIDIA GPU：": "NVIDIA GPU を検出：",
        "未检测到 NVIDIA GPU：将使用 CPU 模式（较慢，可正常出字幕）":
            "NVIDIA GPU を検出できません：CPU モードで動作します（遅いですが正常に動作）",
        "使用方式：\n1. 双击 2ByteASR.exe（或把视频/音频直接拖到它上面）\n2. 可继续拖入更多素材，选择游戏名称后点击「开始生成字幕」\n3. 字幕与剪映文稿生成在素材同目录（xxx_剪映文稿.srt）":
            "使い方：\n1. 2ByteASR.exe をダブルクリック（動画・音声をドロップも可）\n2. 素材を追加し、ゲーム名を選んで「字幕生成を開始」\n3. 字幕は素材と同じフォルダに保存（xxx_剪映文稿.srt）",
        "开始使用": "はじめる",
        "重试失败项": "失敗項目を再試行",
        "打开字幕目录": "字幕フォルダを開く",
        "2ByteASR 已在运行": "2ByteASR は実行中です",
        "检测到另一个 2ByteASR 实例正在运行，请先关闭它再启动。":
            "別の 2ByteASR が実行中です。先に閉じてから起動してください。",
    },
}

# Every known Chinese source string, for capture decisions.
_KNOWN_KEYS = frozenset().union(*(table.keys() for table in _TRANSLATIONS.values()))

# Captured originals per widget id: {id(widget): (head, body, tail)}
_originals: dict[int, tuple[str, str, str]] = {}
_original_tips: dict[int, tuple[str, str, str]] = {}
_original_placeholders: dict[int, tuple[str, str, str]] = {}
_original_items: dict[int, list[str]] = {}


def current_language() -> str:
    settings, _path, _warnings = load_runtime_settings()
    return str(settings.get("ui", {}).get("language", "zh"))


def save_language(language: str) -> None:
    settings, _path, _warnings = load_runtime_settings()
    settings.setdefault("ui", {})["language"] = language
    save_runtime_settings(settings)


def translate(text: str, language: str) -> str:
    if language == "zh":
        return text
    return _TRANSLATIONS.get(language, {}).get(text, text)


def _split_decor(text: str) -> tuple[str, str, str]:
    """Split a label into (leading decoration, body, trailing decoration).

    Handles labels such as "●  游戏 / 内容名称" and "  字幕生成流程  ".
    """
    head = ""
    body = text
    while body.startswith("●"):
        head += "●"
        body = body[1:]
    leading = len(body) - len(body.lstrip())
    head += body[:leading]
    body = body[leading:]
    trailing = len(body) - len(body.rstrip())
    tail = body[len(body) - trailing:] if trailing else ""
    body = body.rstrip()
    return head, body, tail


def _compose(head: str, body: str, tail: str) -> str:
    return head + body + tail


def apply_ui_language(root, language: str | None = None) -> None:
    """Walk the widget tree under `root` and overlay the target language."""
    if language is None:
        language = current_language()
    table = _TRANSLATIONS.get(language, {})
    if language == "zh":
        table = {key: key for key in _KNOWN_KEYS}

    from PySide6.QtWidgets import (
        QAbstractButton,
        QComboBox,
        QLabel,
        QLineEdit,
        QWidget,
    )

    def apply_text(widget, text: str, originals: dict, setter):
        if text == "":
            return
        head, body, tail = _split_decor(text)
        key = id(widget)
        if body in _KNOWN_KEYS or key in originals:
            if key not in originals:
                originals[key] = (head, body, tail)
            _head, _body, _tail = originals[key]
            setter(_compose(_head, table.get(_body, _body), _tail))

    for widget in root.findChildren(QWidget):
        if isinstance(widget, QLabel):
            apply_text(widget, widget.text(), _originals, widget.setText)
        elif isinstance(widget, QAbstractButton):
            apply_text(widget, widget.text(), _originals, widget.setText)
        if isinstance(widget, QLineEdit):
            apply_text(
                widget, widget.placeholderText(), _original_placeholders,
                widget.setPlaceholderText)
        if isinstance(widget, QComboBox):
            placeholder = widget.placeholderText()
            if placeholder:
                apply_text(
                    widget, placeholder, _original_placeholders,
                    widget.setPlaceholderText)
            key = id(widget)
            count = widget.count()
            if count and key not in _original_items:
                items = [widget.itemText(i) for i in range(count)]
                if any(item in _KNOWN_KEYS for item in items):
                    _original_items[key] = items
            if key in _original_items:
                for index, item in enumerate(_original_items[key]):
                    if item in _KNOWN_KEYS:
                        widget.setItemText(index, table.get(item, item))
        tip = widget.toolTip()
        if tip:
            apply_text(widget, tip, _original_tips, widget.setToolTip)
