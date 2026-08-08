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
