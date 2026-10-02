"""Responsive profile regressions for the three home recognition cards."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QFontMetrics  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from twobyteasr.ui import APP_QSS  # noqa: E402
from twobyteasr.ui_recognition import RecognitionPlanWidget  # noqa: E402


def _app():
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(APP_QSS)
    return app


def test_recognition_cards_use_bounded_height_profiles_without_repolish_storm():
    app = _app()
    plan = RecognitionPlanWidget()
    plan.show()

    expected = (
        (240, "compact", 44, 16, 22),
        (330, "normal", 56, 20, 28),
        (410, "large", 68, 23, 36),
        (520, "extra_large", 68, 26, 40),
    )
    for height, profile, icon_size, role_size, model_size in expected:
        plan.resize(1200, height)
        app.processEvents()
        plan._update_responsive_profile()
        assert plan._responsive_profile == profile
        for card in plan.cards.values():
            assert card.property("density") == profile
            assert card.icon_label.width() == icon_size
            assert card.icon_label.height() == icon_size
            assert card.role_label.font().pixelSize() == role_size
            assert card.model_label.font().pixelSize() == model_size
            assert card.description_label.isVisible() == (profile != "compact")

    apply_counts = {
        role: card._responsive_apply_count for role, card in plan.cards.items()
    }
    for _ in range(20):
        plan.resize(1200, 520)
        plan._update_responsive_profile()
    assert {
        role: card._responsive_apply_count for role, card in plan.cards.items()
    } == apply_counts

    plan.close()
    plan.deleteLater()


def test_recognition_cards_use_actual_card_width_even_when_window_is_tall():
    app = _app()
    plan = RecognitionPlanWidget()
    plan.show()

    plan.resize(720, 520)
    app.processEvents()
    plan._update_responsive_profile()

    assert plan._responsive_profile == "normal"
    assert {card.property("density") for card in plan.cards.values()} == {"normal"}
    assert all(card._identity_centered for card in plan.cards.values())
    for card in plan.cards.values():
        layout = card.layout()
        assert layout.stretch(card._leading_space_index) == 1
        assert layout.stretch(card._body_stretch_index) == 1

    plan.close()
    plan.deleteLater()


def test_recognition_cards_keep_shared_identity_and_bottom_row_tracks():
    app = _app()
    plan = RecognitionPlanWidget()
    plan.cards["primary"].set_state("MOSS-Transcribe-Diarize", "本地", "已就绪", "good")
    plan.cards["timeline"].set_state("FireRedASR2-AED", "本地", "已就绪", "good")
    plan.cards["review"].set_state("Qwen3-ASR 1.7B", "本地", "已就绪", "good")
    plan.show()
    for width, height in ((980, 360), (980, 520), (1500, 520)):
        plan.resize(width, height)
        app.processEvents()
        plan._update_responsive_profile()
        app.processEvents()

        cards = tuple(plan.cards.values())
        assert len({card.model_label.height() for card in cards}) == 1
        for card in cards:
            label = card.model_label
            metrics = QFontMetrics(label.font())
            required = metrics.boundingRect(0, 0, label.width(), 2000,
                                             Qt.TextFlag.TextWordWrap, label.text()).height()
            assert label.height() >= max(required, metrics.lineSpacing()*2)
        for attr in ("icon_label", "role_label", "model_label", "status_badge", "change_hint"):
            assert len({getattr(card, attr).mapTo(plan, getattr(card, attr).rect().topLeft()).y() for card in cards}) == 1

    plan.close()
    plan.deleteLater()
