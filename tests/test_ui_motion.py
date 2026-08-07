import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from twobyteasr.service import MediaResult, QueueResult
from twobyteasr.ui import (
    AMBER,
    CORAL,
    GREEN,
    SURFACE,
    CompletionDialog,
    ProgressPhaseCard,
    _completion_notification_spec,
    persist_ai_configuration,
)


def test_active_phase_color_animation_is_a_closed_loop():
    app = QApplication.instance() or QApplication([])
    card = ProgressPhaseCard("fa5s.wave-square", "本地识别", "转写与主播", AMBER)
    card.set_state("active")

    values = [(position, value.name()) for position, value in card._pulse.keyValues()]

    assert values[0][0] == 0.0
    assert values[-1][0] == 1.0
    assert values[0][1] == values[-1][1]
    assert values[0][1] != values[1][1]
    assert card._pulse.state().name == "Running"
    card.deleteLater()
    app.processEvents()


def test_elapsed_timer_uses_precise_short_heartbeat(monkeypatch):
    # The concrete timer is built in MainWindow; its contract is intentionally
    # source-level here so the test does not require loading models or settings UI.
    from pathlib import Path

    source = (Path(__file__).parents[1] / "twobyteasr" / "ui.py").read_text(encoding="utf-8")
    assert "setTimerType(Qt.TimerType.PreciseTimer)" in source
    assert "self._progress_timer.setInterval(200)" in source


def test_ai_form_can_be_saved_without_starting_a_subtitle_run(monkeypatch):
    calls = []

    class FakeLegacy:
        def configure_runtime_llms(self, models, **kwargs):
            calls.append((models, kwargs))

    monkeypatch.setattr("twobyteasr.ui.resolve_api_key", lambda stage: ("", "未配置"))
    polish = {
        "provider": "custom",
        "model": "custom-polish",
        "base_url": "https://polish.example/v1",
        "key": "",
    }
    group = {
        "provider": "bailian",
        "model": "qwen3.7-flash-2026-07-15",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "key": "new-local-key",
    }

    result = persist_ai_configuration(
        FakeLegacy(),
        polish,
        group,
        unified=True,
        share_key=True,
        require_ready=False,
    )

    assert not result["missing_keys"]
    assert calls[0][0]["polish_provider"] == "bailian"
    assert calls[0][0]["polish_model"] == "qwen3.7-flash-2026-07-15"
    assert calls[0][0]["group_model"] == "qwen3.7-flash-2026-07-15"
    assert calls[0][1]["group_key"] == "new-local-key"
    assert calls[0][1]["unified_glm_processing"] is True


def test_ui_has_explicit_ai_save_action_independent_of_start():
    from pathlib import Path

    source = (Path(__file__).parents[1] / "twobyteasr" / "ui.py").read_text(encoding="utf-8")
    assert 'AnimatedButton("保存 AI 配置")' in source
    assert "self.save_ai_button.clicked.connect" in source
    assert "require_ready=True" in source


def test_completion_notification_distinguishes_success_and_failure():
    success = QueueResult(
        (MediaResult("ok.mp4", "success", srt_path="ok.srt"),),
        elapsed_seconds=1.0,
    )
    title, message, _icon, details = _completion_notification_spec(success)
    assert title == "字幕生成完成"
    assert "成功生成 1 个素材" in message
    assert "结果页" in details

    failed = QueueResult(
        (MediaResult("bad.mp4", "failed", error="synthetic failure"),),
        elapsed_seconds=1.0,
    )
    title, message, _icon, details = _completion_notification_spec(failed)
    assert title == "字幕生成失败"
    assert "失败 1 个" in message
    assert "bad.mp4：synthetic failure" in details


def test_completion_dialog_requests_attention_when_window_is_in_background():
    from pathlib import Path

    source = (Path(__file__).parents[1] / "twobyteasr" / "ui.py").read_text(encoding="utf-8")
    assert "QApplication.beep()" in source
    assert "QApplication.alert(self, 0)" in source
    assert "WindowStaysOnTopHint" in source
    assert source.count("self._show_task_notification(") >= 2


def test_completion_dialog_has_theme_stable_light_surface_and_status_colors():
    app = QApplication.instance() or QApplication([])
    success = CompletionDialog(
        "字幕生成完成",
        "已成功生成 1 个素材的字幕。",
        QMessageBox.Icon.Information,
        "可以在结果页查看字幕。",
    )
    failed = CompletionDialog(
        "字幕生成失败",
        "本批任务已结束。",
        QMessageBox.Icon.Critical,
        "sample.mp4：测试错误",
    )

    assert success.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert success.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    assert success.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert SURFACE in success.card.styleSheet()
    assert success.card.graphicsEffect() is None
    assert success.accent == GREEN
    assert success.status_badge.text() == "处理完成"
    assert success.title_label.text() == "字幕生成完成"
    assert success.confirm_button.text() == "知道了"
    assert failed.accent == CORAL
    assert failed.status_badge.text() == "需要处理"
    assert "测试错误" in failed.details_label.text()

    success.deleteLater()
    failed.deleteLater()
    app.processEvents()
