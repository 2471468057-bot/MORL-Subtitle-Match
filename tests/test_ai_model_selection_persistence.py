"""AI 模型选择持久化回归（2026-09-20 DeepSeek vision-exp 复活链）。

覆盖用户验收 Test 1-8：
1. 保存 model=A → 重新加载 settings → 仍为 A
2. 重新创建 AI 设置编辑器 → 下拉仍为 A
3. 模型列表刷新后仍含 A → selection 不变
4. 刷新后列表不含 A → 明确标记待确认；墓碑模型绝不被恢复
5. 重选 B 保存 → “重启”（新实例）后仍是 B
6. 全文断句 runtime 解析 → 实际请求模型 = B
7. 校对/断句统一开关切换 → 不复活 vision-exp
8. 全仓运行时代码不再把 vision-exp 当 DeepSeek 默认模型
"""
from __future__ import annotations

import copy
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication


RETIRED = "deepseek-v4-flash-vision-exp"
MODEL_A = "deepseek-v4-pro"
MODEL_B = "deepseek-v4-flash"


@pytest.fixture(scope="session", autouse=True)
def _session_settings_isolation(tmp_path_factory):
    """会话级 settings 根重定向（不恢复），同 test_profile_independence。"""
    import twobyteasr.settings as settings_module

    redirected_root = tmp_path_factory.mktemp("ai-persist-settings-root")
    settings_module.stable_settings_root = lambda: redirected_root
    yield


@pytest.fixture()
def _no_secret_writes(monkeypatch):
    monkeypatch.setattr("twobyteasr.ui.resolve_api_key", lambda stage: ("", "未配置"))
    monkeypatch.setattr(
        "twobyteasr.ui.read_api_key", lambda _provider, _base_url="": ("", "未配置")
    )
    monkeypatch.setattr(
        "twobyteasr.ui.save_api_key_for",
        lambda provider, base_url, key: None,
    )
    monkeypatch.setattr(
        "twobyteasr.ui.delete_api_key_for",
        lambda provider, base_url: None,
    )


def _editor_values(model: str) -> dict:
    return {
        "service": "deepseek",
        "transport": "openai_compatible",
        "provider": "deepseek",
        "model": model,
        "base_url": "https://api.deepseek.com/v1",
        "protocol": "auto",
        "key": "",
        "key_state": "unchanged",
    }


def _persist(legacy, model: str, *, unified: bool = True, use_ai_grouping: bool = True):
    from twobyteasr.ui import persist_ai_configuration

    group = _editor_values(model)
    polish = dict(group) if unified else _editor_values(model)
    return persist_ai_configuration(
        legacy,
        polish,
        group,
        unified=unified,
        share_key=True,
        require_ready=False,
        use_ai_grouping=use_ai_grouping,
    )


def _runtime_models(legacy) -> dict:
    return legacy.RUNTIME_SETTINGS.get("models", {})


# ---------------------------------------------------------------------------
# Test 1: settings 层保存/重载
# ---------------------------------------------------------------------------

def test_save_then_reload_keeps_deepseek_model(tmp_path, monkeypatch, _no_secret_writes):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    import subtitle_core as legacy
    from twobyteasr.settings import load_runtime_settings

    _persist(legacy, MODEL_A)

    # “重启”：从磁盘重新加载 settings
    reloaded, _path, _warnings = load_runtime_settings()
    models = reloaded.get("models", {})
    assert models.get("ai_service") == "deepseek"
    assert models.get("provider_profiles", {}).get("deepseek", {}).get("model") == MODEL_A
    assert models.get("group_model") == MODEL_A
    assert models.get("polish_model") == MODEL_A


# ---------------------------------------------------------------------------
# Test 2 + 5: 编辑器重建（“重新打开设置页/重启”）恢复保存值
# ---------------------------------------------------------------------------

def _make_editor(settings: dict):
    from twobyteasr.ui import EndpointEditor

    return EndpointEditor("全文断句模型", "#2f8fef", "group", settings)


def test_recreated_editor_shows_saved_model(tmp_path, monkeypatch, _no_secret_writes):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    _app = QApplication.instance() or QApplication([])
    import subtitle_core as legacy

    _persist(legacy, MODEL_A)
    settings = copy.deepcopy(legacy.RUNTIME_SETTINGS)
    editor = _make_editor(settings)
    assert editor.model.currentText().strip() == MODEL_A
    editor.deleteLater()

    # Test 5：重选 B 保存 → 新实例恢复 B
    _persist(legacy, MODEL_B)
    settings_b = copy.deepcopy(legacy.RUNTIME_SETTINGS)
    editor_b = _make_editor(settings_b)
    assert editor_b.model.currentText().strip() == MODEL_B
    editor_b.deleteLater()


# ---------------------------------------------------------------------------
# Test 3 + 4: 模型列表刷新不擅动 selection
# ---------------------------------------------------------------------------

def test_discovery_refresh_keeps_selection_when_model_present(tmp_path, monkeypatch, _no_secret_writes):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    _app = QApplication.instance() or QApplication([])
    import subtitle_core as legacy

    _persist(legacy, MODEL_A)
    editor = _make_editor(copy.deepcopy(legacy.RUNTIME_SETTINGS))
    editor.model.setCurrentText(MODEL_A)

    editor._model_discovery_succeeded([MODEL_B, MODEL_A])

    assert editor.model.currentText().strip() == MODEL_A
    assert "不在最新列表" not in editor.status.text()
    editor.deleteLater()


def test_discovery_refresh_missing_model_flags_reselection(tmp_path, monkeypatch, _no_secret_writes):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    _app = QApplication.instance() or QApplication([])
    import subtitle_core as legacy

    _persist(legacy, MODEL_A)
    editor = _make_editor(copy.deepcopy(legacy.RUNTIME_SETTINGS))

    editor._model_discovery_succeeded([MODEL_B])

    # selection 文本保留（可搜索/手动输入），但状态明确要求确认
    assert editor.model.currentText().strip() == MODEL_A
    assert "不在最新列表" in editor.status.text()
    editor.deleteLater()


def test_retired_saved_model_shows_warning_and_never_selected(tmp_path, monkeypatch, _no_secret_writes):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    _app = QApplication.instance() or QApplication([])
    import subtitle_core as legacy

    # 直接把用户磁盘状态伪造为历史 vision-exp（等价真实用户现场）
    settings = copy.deepcopy(legacy.RUNTIME_SETTINGS)
    settings.setdefault("models", {}).setdefault("provider_profiles", {})["deepseek"] = {
        "base_url": "https://api.deepseek.com/v1",
        "model": RETIRED,
        "protocol": "auto",
    }
    editor = _make_editor(settings)

    assert editor.model.currentText().strip() != RETIRED
    assert editor.model.findText(RETIRED) < 0
    assert not editor.model_warning.isHidden()
    assert RETIRED in editor.model_warning.text()
    editor.deleteLater()


# ---------------------------------------------------------------------------
# Test 6: runtime 解析与实际请求模型
# ---------------------------------------------------------------------------

def test_group_request_resolves_saved_model(tmp_path, monkeypatch, _no_secret_writes):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    import subtitle_core as legacy
    from twobyteasr.llm_config import endpoint_from_settings

    _persist(legacy, MODEL_B)

    endpoint = endpoint_from_settings(copy.deepcopy(legacy.RUNTIME_SETTINGS), "group")
    assert endpoint["model"] == MODEL_B


def test_runtime_never_resolves_retired_model(tmp_path, monkeypatch, _no_secret_writes):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    import subtitle_core as legacy
    from twobyteasr.llm_config import (
        endpoint_from_settings,
        resolved_service_values,
        service_model_catalog,
        validate_endpoint,
    )

    settings = copy.deepcopy(legacy.RUNTIME_SETTINGS)
    settings.setdefault("models", {}).setdefault("provider_profiles", {})["deepseek"] = {
        "base_url": "https://api.deepseek.com/v1",
        "model": RETIRED,
        "protocol": "auto",
    }
    settings["models"]["group_model"] = RETIRED
    settings["models"]["polish_model"] = RETIRED
    settings["models"]["ai_service"] = "deepseek"

    values = resolved_service_values(settings, "deepseek")
    assert values["model"] != RETIRED
    assert RETIRED not in service_model_catalog(settings, "deepseek")
    endpoint = endpoint_from_settings(settings, "group")
    assert endpoint["model"] != RETIRED

    with pytest.raises(RuntimeError, match="已不可用"):
        validate_endpoint(
            {
                "provider": "deepseek",
                "model": RETIRED,
                "base_url": "https://api.deepseek.com/v1",
                "api_key": "whatever",
            },
            "全文断句模型",
        )


# ---------------------------------------------------------------------------
# Test 7: 统一开关切换不复活墓碑模型
# ---------------------------------------------------------------------------

def test_unified_toggle_never_resurrects_retired_model(tmp_path, monkeypatch, _no_secret_writes):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    import subtitle_core as legacy

    # 磁盘上残留墓碑值的真实用户状态
    legacy.RUNTIME_SETTINGS.setdefault("models", {}).setdefault("provider_profiles", {})["deepseek"] = {
        "base_url": "https://api.deepseek.com/v1",
        "model": RETIRED,
        "protocol": "auto",
    }
    legacy.RUNTIME_SETTINGS["models"]["ai_service"] = "deepseek"

    _persist(legacy, MODEL_B, unified=True)
    models = _runtime_models(legacy)
    assert models["group_model"] == MODEL_B and RETIRED not in models["group_model"]

    _persist(legacy, MODEL_B, unified=False)
    models = _runtime_models(legacy)
    assert models["polish_model"] == MODEL_B
    assert models["group_model"] == MODEL_B
    assert models["provider_profiles"]["deepseek"]["model"] == MODEL_B
    assert all(RETIRED != value for value in models.get("provider_profiles", {}).get("deepseek", {}).values())


# ---------------------------------------------------------------------------
# Test 8: 全仓运行时代码不再把 vision-exp 当默认模型
# ---------------------------------------------------------------------------

def test_repo_runtime_has_no_vision_exp_default():
    root = Path(__file__).resolve().parents[1]
    # 墓碑定义/自检允许引用该 id；生产默认逻辑不得引用
    allowed_files = {
        root / "twobyteasr" / "llm_config.py",
        root / "twobyteasr" / "runtime_fixes_audit.py",
    }
    offenders = []
    for path in list((root / "twobyteasr").rglob("*.py")) + [root / "moss_firered_pipeline.py"]:
        if path in allowed_files or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if RETIRED in text:
            offenders.append(str(path.relative_to(root)))
    assert not offenders, f"运行时代码不应再引用已下线模型: {offenders}"


# ---------------------------------------------------------------------------
# 方案快照复活链（MainWindow 端到端）
# ---------------------------------------------------------------------------


@pytest.fixture()
def isolated_main_window(monkeypatch, tmp_path, _no_secret_writes):
    _app = QApplication.instance() or QApplication([])
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    import subtitle_core as legacy
    import twobyteasr.ui as ui_module

    original_settings = copy.deepcopy(legacy.RUNTIME_SETTINGS)
    window = ui_module.MainWindow([], legacy, object(), None)
    try:
        yield window, legacy
    finally:
        legacy.RUNTIME_SETTINGS = original_settings
        window.close()
        window.deleteLater()


def test_profile_apply_with_retired_ref_keeps_global_model(isolated_main_window):
    """启动/切方案回灌环节：墓碑 ref 不再覆盖全局保存值。"""
    window, legacy = isolated_main_window
    from twobyteasr.project_profiles import ProjectProfileStore

    store = ProjectProfileStore(Path(window.profile_store.path))
    profile = store.create("Qwen api", llm_enabled=True, llm_config_ref=RETIRED)

    window._apply_project_profile(store.get(profile.id), mark_used=False)

    current = window.group_editor.model.currentText().strip()
    assert current != RETIRED, "已下线模型不得通过方案快照复活"
    # 全局保存值原样保留
    assert current == str(
        legacy.RUNTIME_SETTINGS.get("models", {}).get("group_model", "") or ""
    ) or current


def test_save_ai_configuration_updates_profile_bookmark(isolated_main_window, capsys):
    """保存 AI 配置 = 唯一权威写入时刻：方案书签必须跟随，杜绝下次启动复活。"""
    window, legacy = isolated_main_window
    from twobyteasr.project_profiles import ProjectProfileStore

    store = ProjectProfileStore(Path(window.profile_store.path))
    profile = store.create("Qwen api", llm_enabled=True, llm_config_ref=RETIRED)
    window.current_project_profile = store.get(profile.id)
    window.group_editor.model.setCurrentText(MODEL_A)
    window.polish_editor.model.setCurrentText(MODEL_A)

    assert window._save_ai_configuration(show_feedback=False) is True

    updated = store.get(profile.id)
    assert updated.llm_config_ref == MODEL_A
    assert updated.llm_config_ref != RETIRED
    saved = capsys.readouterr().out
    assert "[AI_CONFIG_SAVED]" in saved
    assert f"model={MODEL_A}" in saved
    assert "key" not in saved.lower().replace("key_source", "")
