"""Tests for the review-pass features: instance lock, first-run wizard,
media append/retry merging, i18n parity and model-integrity hints."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication


def test_instance_lock_is_exclusive():
    from twobyteasr.ui import _acquire_instance_lock

    app = QApplication.instance() or QApplication([])
    first = _acquire_instance_lock()
    assert first is not None, "first instance should acquire the lock"
    try:
        second = _acquire_instance_lock()
        assert second is None, "second instance must not acquire the lock"
    finally:
        first.unlock()
    third = _acquire_instance_lock()
    assert third is not None, "lock is released after unlock"
    third.unlock()


def test_first_run_guide_dialog_constructs_and_detects_hardware():
    from twobyteasr.ui import GuidedSetupDialog

    app = QApplication.instance() or QApplication([])
    dialog = GuidedSetupDialog()
    assert dialog.lang_combo.count() == 3
    # _detect_gpu must not raise even without nvidia-smi (CI)
    assert dialog.gpu_info.text()
    dialog.close()


def test_merge_media_paths_appends_and_dedupes(tmp_path):
    from twobyteasr.ui import _merge_media_paths

    first = tmp_path / "a.mp4"
    second = tmp_path / "b.mp4"
    first.touch()
    second.touch()
    merged = _merge_media_paths([str(first)], [str(second), str(first)])
    assert len(merged) == 2
    assert str(first) in merged and str(second) in merged
    # order preserved: existing first, then new items
    assert merged[0] == str(first)


def test_i18n_tables_have_identical_keys():
    import twobyteasr.i18n as i18n_mod

    en_keys = set(i18n_mod._TRANSLATIONS["en"])
    ja_keys = set(i18n_mod._TRANSLATIONS["ja"])
    assert en_keys == ja_keys
    # Review-pass entries must exist in both languages
    for key in ("重试失败项", "首次使用引导", "2ByteASR 已在运行"):
        assert key in en_keys


def test_model_integrity_missing_file_hint(tmp_path, monkeypatch):
    from twobyteasr import model_integrity as mi

    fake_lock = {
        "models": {
            "fake-model": {
                "path": "models/fake-model",
                "sha256": {"model.ckpt": "0" * 64},
            }
        }
    }
    monkeypatch.setattr(mi, "load_dependency_lock", lambda root=None: fake_lock)
    (tmp_path / "models" / "fake-model").mkdir(parents=True)
    with pytest.raises(mi.ModelIntegrityError) as excinfo:
        mi.verify_model_files("fake-model", root=tmp_path)
    message = str(excinfo.value)
    assert "模型关键文件缺失" in message
    assert "download_models.bat" in message
