import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest


@pytest.fixture(autouse=True)
def close_test_owned_qt_windows():
    """Even failed assertions must release Studio workers and GDI resources."""
    qt=sys.modules.get('PySide6.QtWidgets')
    app=qt.QApplication.instance() if qt else None
    before={id(w) for w in app.allWidgets()} if app else set()
    yield
    qt=sys.modules.get('PySide6.QtWidgets')
    app=qt.QApplication.instance() if qt else None
    if app is None:return
    from PySide6.QtCore import QCoreApplication,QEvent
    from shiboken6 import isValid
    studio=sys.modules.get('twobyteasr.studio_ui')
    page_type=getattr(studio,'SubtitleStudioPage',())
    owned=[]
    for widget in app.allWidgets():
        if id(widget) not in before and isValid(widget) and isinstance(widget,page_type):
            widget.close_page()
            owned.append(widget)
    # Drain queued GUI work while its controls still exist, then delete.
    app.processEvents()
    for widget in owned:
        if isValid(widget):widget.hide();widget.deleteLater()
    for widget in app.topLevelWidgets():
        if id(widget) not in before and isValid(widget):
            widget.hide();widget.deleteLater()
    QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
