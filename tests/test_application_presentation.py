import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication, QWidget, QHBoxLayout, QSplitter, QLineEdit
from twobyteasr.design.presentation import field_width
from twobyteasr.ui_motion import atomic_layout, motion_duration


@pytest.fixture
def app(tmp_path,monkeypatch):
    instance=QApplication.instance() or QApplication([])
    from twobyteasr import theme_manager
    monkeypatch.setattr(theme_manager,'_settings',lambda:QSettings(str(tmp_path/'theme.ini'),QSettings.Format.IniFormat))
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'local'))
    return instance


def test_atomic_first_frame_commits_hidden_splitter_children(app):
    root=QWidget();layout=QHBoxLayout(root);split=QSplitter(Qt.Orientation.Horizontal)
    layout.addWidget(split)
    children=[QWidget() for _ in range(3)]
    for child in children:split.addWidget(child)
    root.resize(1000,600);root.show();app.processEvents()
    with atomic_layout(root):
        children[0].hide();children[2].hide();split.setSizes([0,900,0])
    assert split.sizes()==[0,split.width(),0]
    first=split.sizes();app.processEvents();assert split.sizes()==first
    assert root.updatesEnabled()
    root.close()


def test_atomic_boundary_preserves_outer_update_suppression(app):
    root=QWidget();root.setUpdatesEnabled(False)
    with atomic_layout(root):
        with atomic_layout(root):pass
    assert not root.updatesEnabled()
    root.deleteLater()


def test_semantic_fields_let_path_grow_and_bound_short_values(app):
    root=QWidget();row=QHBoxLayout(root)
    short=field_width(QLineEdit('2'),'numeric')
    path=field_width(QLineEdit('D:/项目/录播'),'expanding')
    row.addWidget(short);row.addWidget(path,1)
    root.resize(1200,180);root.show();app.processEvents()
    assert short.width()<=144
    assert path.width()>800
    assert short.height()==path.height()
    root.close()


def test_accent_icon_uses_the_same_foreground_as_text_for_every_theme():
    from twobyteasr.themed_icons import icon_role_color
    from twobyteasr.ui_theme import THEMES
    for theme in THEMES.values():
        assert icon_role_color('on_accent',theme)==theme.text_on_accent


def test_settings_cancel_has_no_persistence_side_effect(app,monkeypatch):
    from twobyteasr import application_settings as settings
    from twobyteasr.application_settings_ui import ApplicationSettingsDialog
    from PySide6.QtWidgets import QDialog
    writes=[]
    monkeypatch.setattr(settings,'save_hub_preferences',lambda *a,**kw:writes.append(a))
    def reject(dialog):
        dialog.auto_save.setChecked(False)
        dialog.root_edit.setText('D:/not-saved')
        return QDialog.DialogCode.Rejected
    monkeypatch.setattr(ApplicationSettingsDialog,'exec',reject)
    parent=QWidget()
    assert settings.open_application_settings(parent) is False
    assert writes==[]


def test_settings_save_roundtrips_existing_preferences(app,monkeypatch):
    from twobyteasr import application_settings as settings
    from twobyteasr.application_settings_ui import ApplicationSettingsDialog
    from PySide6.QtWidgets import QDialog
    writes=[]
    monkeypatch.setattr(settings,'read_studio_preferences',lambda:{'recent_project_count':17,'recovery_policy':'official'})
    monkeypatch.setattr(settings,'save_hub_preferences',lambda *args:writes.append(args))
    monkeypatch.setattr(settings,'apply_theme',lambda *a:None)
    def accept(dialog):
        dialog.auto_save.setChecked(True)
        dialog.interval.setCurrentIndex(dialog.interval.findData(120))
        dialog.reduce_motion_box.setChecked(True)
        assert dialog.pages.count()==4
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(ApplicationSettingsDialog,'exec',accept)
    assert settings.open_application_settings(QWidget()) is True
    assert writes[0][1:4]==(True,120,17)
    assert writes[0][6:] == ('official',True)
    assert motion_duration(180)==0
    app.setProperty('reduceMotion',False)
