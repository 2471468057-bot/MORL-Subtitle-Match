"""2026-10-15: review card 1 carries click-to-fix marks; P flips 他/她.

The card hit-tests the marks through a text layout mirrored from its label;
the pixel check below makes sure the mirror lands on the painted marks."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from twobyteasr.studio_project import StudioCue
from twobyteasr import studio_review_ui
from twobyteasr.studio_cards import ReviewCandidateCard
from twobyteasr.review_suggestions import review_suggestions
from twobyteasr.studio_qc import QCCandidate
from tests.test_review_replay_and_window_bounds import _page


def _app():
    return QApplication.instance() or QApplication([])


def _card(text, others=()):
    _app()
    rows = review_suggestions(text, others)
    card = ReviewCandidateCard(0, QCCandidate(text, ("Current",)), is_current=True, current_text=text,
                               suggestions=rows)
    card.resize(520, 110)
    card.show()
    for _ in range(3):
        _app().processEvents()
    return card, rows


def _accent_points(card):
    """Card points where the label painted the accent colour (the marks)."""
    from twobyteasr.theme_manager import theme_key
    from twobyteasr.ui_theme import theme_definition
    accent = QColor(theme_definition(theme_key()).accent)
    image = card.text_label.grab().toImage()
    ratio = image.devicePixelRatio() or 1
    points = []
    for y in range(0, image.height(), 2):
        for x in range(0, image.width(), 2):
            pixel = image.pixelColor(x, y)
            if (abs(pixel.red() - accent.red()) + abs(pixel.green() - accent.green())
                    + abs(pixel.blue() - accent.blue())) < 40:
                points.append(card.text_label.mapTo(card, QPoint(int(x / ratio), int(y / ratio))))
    return points


def test_marks_are_hit_where_they_are_painted():
    card, rows = _card("然后他来到了那维来特的家", [("然后他来到了那维莱特的家", ("FireRed",))])
    try:
        assert [row.kind for row in rows] == ["pronoun", "model"]
        points = _accent_points(card)
        assert points, "the marks paint in the accent colour"
        hits = [card._mark_at(point) for point in points]
        assert sum(index >= 0 for index in hits) >= 0.8 * len(hits), hits
        assert {0, 1} <= set(hits)
        # Left edge of the text, before the first mark: plain caption text.
        assert card._mark_at(card.text_label.mapTo(card, QPoint(2, card.text_label.height() // 2))) == -1
    finally:
        card.close()


def test_click_on_a_mark_fixes_it_and_elsewhere_adopts_the_card():
    card, rows = _card("然后他来到了那维来特的家", [("然后他来到了那维莱特的家", ("FireRed",))])
    activated, adopted = [], []
    card.suggestion_activated.connect(lambda mark, option: activated.append((mark, option)))
    card.clicked.connect(adopted.append)
    try:
        point = next(point for point in _accent_points(card) if card._mark_at(point) == 1)
        QTest.mouseClick(card, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)
        assert activated == [(1, 0)] and adopted == []
        QTest.mouseClick(card, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                         QPoint(card.width() - 4, card.height() - 4))
        assert adopted == [0] and activated == [(1, 0)]
    finally:
        card.close()


def _fake_candidates(table):
    def candidates(project, cue):
        return tuple(QCCandidate(text, sources) for text, sources in table.get(cue.id, ((cue.text, ("Current",)),)))
    return candidates


def test_review_page_applies_one_mark_and_stays_on_the_caption(tmp_path, monkeypatch):
    cues = [StudioCue("a", 0, 2000, "然后他来到了那维来特的家"), StudioCue("b", 3000, 5000, "下一句")]
    app, page = _page(tmp_path, monkeypatch, cues)
    monkeypatch.setattr(studio_review_ui, "review_candidates", _fake_candidates({"a": (
        ("然后他来到了那维来特的家", ("Current",)), ("然后她来到了那维莱特的家", ("FireRed", "Qwen3-ASR")))}))
    try:
        page._set_review_mode(True)
        page.select_cue("a")
        page._refresh_review_summary_strip()
        app.processEvents()
        assert [row.original for row in page._review_suggestions] == ["他", "来"]
        card = page.review_dock_candidate_layout.itemAt(0).widget()
        assert isinstance(card, ReviewCandidateCard) and card._suggestions
        second = page.review_dock_candidate_layout.itemAt(1).widget()
        assert isinstance(second, ReviewCandidateCard) and not second._suggestions  # only card 1 is marked
        assert page._apply_review_suggestion(1)
        assert page._cue_lookup["a"].text == "然后他来到了那维莱特的家"
        assert page.selected_cue_id == "a"
        assert [row.original for row in page._review_suggestions] == ["他"]
        page.undo_stack.undo()
        assert page._cue_lookup["a"].text == "然后他来到了那维来特的家"
    finally:
        page.close_page()
        page.deleteLater()


def test_p_flips_the_caption_and_a_consistent_caption_still_gets_card_one(tmp_path, monkeypatch):
    cues = [StudioCue("a", 0, 2000, "他说他们马上到"), StudioCue("b", 3000, 5000, "下一句")]
    app, page = _page(tmp_path, monkeypatch, cues)
    monkeypatch.setattr(studio_review_ui, "review_candidates", _fake_candidates({}))
    try:
        assert page._review_shortcut_lookup.get("P") == "review_flip_pronoun"
        page._set_review_mode(True)
        page.select_cue("a")
        page._refresh_review_summary_strip()
        app.processEvents()
        layout = page.review_dock_candidate_layout
        widgets = [layout.itemAt(index).widget() for index in range(layout.count())]
        cards = [widget for widget in widgets if isinstance(widget, ReviewCandidateCard)]
        assert len(cards) == 1 and [row.original for row in cards[0]._suggestions] == ["他", "他"]
        assert page._flip_review_pronouns()
        assert page._cue_lookup["a"].text == "她说她们马上到"
        assert page._apply_review_suggestion(0)            # one click: 她 → 他 for that one place
        assert page._cue_lookup["a"].text == "他说她们马上到"
        page.select_cue("b")
        page._refresh_review_summary_strip()
        app.processEvents()
        widgets = [layout.itemAt(index).widget() for index in range(layout.count())]
        assert not any(isinstance(widget, ReviewCandidateCard) for widget in widgets)  # nothing to fix
    finally:
        page.close_page()
        page.deleteLater()
