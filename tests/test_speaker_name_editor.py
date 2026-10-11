"""Name edit boundaries use one identity while batch checks remain independent."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QInputMethodEvent, QUndoStack
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from twobyteasr.studio_project import StudioCue, StudioMedia, StudioSpeaker, SubtitleProject, save_project, load_project
from twobyteasr.studio_speaker_manager import SpeakerManagerDialog

APP = QApplication.instance() or QApplication([])


@pytest.fixture
def manager(monkeypatch):
    page = QWidget()
    page.project = SubtitleProject(media=StudioMedia('fixture.mp4', duration_ms=2000), speakers=[StudioSpeaker('S00', '原名'), StudioSpeaker('S01', '第二人'), StudioSpeaker('S02', '第三人')],
        cues=[StudioCue('a', 0, 1000, '第一句', speaker_id='S00'), StudioCue('b', 500, 1500, '第二句', speaker_id='S01')])
    page.undo_stack = QUndoStack(page)
    page._speaker_roles_pending = False
    page._populate_speakers = lambda: None
    page._speaker_structure_changed = lambda: None
    monkeypatch.setattr(SpeakerManagerDialog, '_build_candidates', lambda self: None)
    dialog = SpeakerManagerDialog(page)
    dialog.show()
    APP.processEvents()
    yield dialog
    dialog._name_preedit = False
    dialog.name_edit.setText('有效名称')
    dialog.close()
    page.deleteLater()
    APP.processEvents()


def names(manager):
    return {speaker.id: speaker.name for speaker in manager.page.project.speakers}


def test_enter_commits_one_identity_and_one_undo_without_resetting_checks(manager, tmp_path):
    manager._select_visible('all')
    original_ids = [speaker.id for speaker in manager.page.project.speakers]
    manager.name_edit.setFocus()
    QTest.keyClick(manager.name_edit, Qt.Key_A, Qt.ControlModifier)
    QTest.keyClicks(manager.name_edit, 'Renamed')
    assert manager._selected_ids() == set(original_ids)
    assert manager.page.undo_stack.count() == 0
    QTest.keyClick(manager.name_edit, Qt.Key_Return)
    assert names(manager) == {'S00': 'Renamed', 'S01': '第二人', 'S02': '第三人'}
    assert manager.page.undo_stack.count() == 1
    assert manager._selected_ids() == set(original_ids)
    assert manager._selected_speaker_id() == 'S00'
    assert manager.table.item(0, 1).text() == 'S00'
    assert manager.table.item(0, 2).text() == 'Renamed'
    manager.refresh()
    assert manager._selected_ids() == set(original_ids)
    assert manager._selected_speaker_id() == 'S00'
    path = save_project(manager.page.project, tmp_path/'renamed.2byteproj')
    assert load_project(path).speakers[0].name == 'Renamed'
    manager.page.undo_stack.undo()
    assert names(manager)['S00'] == '原名'
    assert manager.name_edit.text() == '原名'
    assert manager.table.item(0, 2).text() == '原名'
    assert manager._selected_ids() == set(original_ids)


def test_switching_row_submits_previous_name_and_does_not_change_batch_checks(manager):
    manager.table.item(0, 0).setCheckState(Qt.Checked)
    manager.table.item(2, 0).setCheckState(Qt.Checked)
    manager.name_edit.setText('中文名字')
    manager.table.setCurrentCell(1, 2)
    assert names(manager)['S00'] == '中文名字'
    assert manager.name_edit.text() == '第二人'
    assert manager._selected_ids() == {'S00', 'S02'}
    assert manager.page.undo_stack.count() == 1
    manager.name_edit.setText('中文名字')
    manager.done(1)
    assert names(manager)['S01'] == '中文名字'
    assert [speaker.id for speaker in manager.page.project.speakers] == ['S00', 'S01', 'S02']
    assert manager.page.undo_stack.count() == 2


def test_focus_out_commits_valid_text_and_empty_name_keeps_draft_and_previous_value(manager):
    manager.name_edit.setFocus()
    manager.name_edit.setText('失焦保存')
    manager.color_button.setFocus()
    APP.processEvents()
    assert names(manager)['S00'] == '失焦保存'
    manager.name_edit.setText('  ')
    manager.table.setCurrentCell(1, 1)
    assert names(manager)['S00'] == '失焦保存'
    assert manager._selected_speaker_id() == 'S00'
    assert manager.name_edit.text() == '  '
    assert manager.name_error.isVisible()
    manager.done(1)
    assert manager.isVisible()
    assert manager.page.undo_stack.count() == 1


def test_ime_preedit_never_becomes_name_and_committed_chinese_is_saved(manager):
    manager.name_edit.setFocus()
    manager.name_edit.setText('')
    preedit = QInputMethodEvent('zhang', [])
    QApplication.sendEvent(manager.name_edit, preedit)
    assert manager._name_preedit
    assert not manager._commit_name()
    assert names(manager)['S00'] == '原名'
    assert manager.page.undo_stack.count() == 0
    commit = QInputMethodEvent('', [])
    commit.setCommitString('张三')
    QApplication.sendEvent(manager.name_edit, commit)
    assert not manager._name_preedit
    manager.done(1)
    assert names(manager)['S00'] == '张三'
    assert manager.page.undo_stack.count() == 1


def test_filter_refresh_and_same_row_changes_preserve_checks_and_active_draft(manager):
    manager._select_visible('all')
    manager.name_edit.setText('保留草稿')
    manager.table.setCurrentCell(0, 3)
    assert manager.name_edit.text() == '保留草稿'
    manager.speaker_filter.setText('第二人')
    assert manager._selected_ids() == {'S00', 'S01', 'S02'}
    manager.refresh()
    assert names(manager)['S00'] == '保留草稿'
    assert manager._selected_ids() == {'S00', 'S01', 'S02'}
    manager._apply_changes()
    assert manager.page.undo_stack.count() == 1
