"""Studio command groups with stable hit areas and ordered narrow rows."""
from __future__ import annotations

import hashlib

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtWidgets import QHBoxLayout, QLayout, QSizePolicy, QWidget


class CommandBar(QWidget):
    """Publish the wrapped row minimum to the containing layout/splitter."""

    def minimumSizeHint(self):
        minimum = super().minimumSizeHint()
        layout = self.layout()
        if layout is not None and self.width() > 0:
            minimum.setHeight(max(minimum.height(), layout.heightForWidth(self.width())))
        return minimum

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if event.size().width() != event.oldSize().width():
            # QSplitter caches its child's layout minimum. A width change can
            # add/remove a complete row, so invalidate it through Qt's normal
            # layout request rather than changing a height or scheduling work.
            self.updateGeometry()


class CommandFlowLayout(QLayout):
    """Wrap complete groups; extra space separates editing and transport."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items = []
        self.stretch_after = {0, 1}
        # Item index centred on the bar when its row has room (transport).
        self.center_index = None
        self.setContentsMargins(12, 6, 10, 6)
        self.setSpacing(16)

    def addItem(self, item):
        self.items.append(item)

    def count(self):
        return len(self.items)

    def itemAt(self, index):
        return self.items[index] if 0 <= index < len(self.items) else None

    def takeAt(self, index):
        return self.items.pop(index) if 0 <= index < len(self.items) else None

    def expandingDirections(self):
        return Qt.Orientation.Horizontal

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._arrange(QRect(0, 0, width, 0), False)

    def minimumSize(self):
        # Claiming less than one complete group clips playback/timecode.
        size = QSize()
        for item in self.items:
            size = size.expandedTo(item.minimumSize())
        left, top, right, bottom = self.getContentsMargins()
        return size + QSize(left + right, top + bottom)

    def sizeHint(self):
        left, top, right, bottom = self.getContentsMargins()
        sizes = [item.sizeHint() for item in self.items if not item.isEmpty()]
        width = sum(size.width() for size in sizes) + max(0, len(sizes) - 1) * self.spacing()
        return QSize(width + left + right, max((size.height() for size in sizes), default=0) + top + bottom)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._arrange(rect, True)

    def _arrange(self, rect, apply):
        left, top, right, bottom = self.getContentsMargins()
        area = rect.adjusted(left, top, -right, -bottom)
        rows, row, used = [], [], 0
        for index, item in enumerate(self.items):
            if item.isEmpty():
                continue
            size = item.sizeHint().expandedTo(item.minimumSize())
            if row and used + self.spacing() + size.width() > area.width():
                rows.append(row)
                row, used = [], 0
            if row:
                used += self.spacing()
            row.append((index, item, size))
            used += size.width()
        if row:
            rows.append(row)
        y = area.y()
        for row_number, row in enumerate(rows):
            height = max(size.height() for _, _, size in row)
            if self._arrange_centered(row, area, y, height, apply):
                y += height
                if row_number < len(rows) - 1:
                    y += 6
                continue
            gaps = [index for index, _, _ in row[:-1] if index in self.stretch_after]
            extra = max(0, area.width() - sum(size.width() for _, _, size in row)
                        - self.spacing() * (len(row) - 1))
            x = area.x()
            for index, item, size in row:
                if apply:
                    item.setGeometry(QRect(x, y + (height - size.height()) // 2,
                                           size.width(), size.height()))
                x += size.width() + self.spacing()
                if index in gaps:
                    share, remainder = divmod(extra, len(gaps))
                    x += share + (1 if gaps.index(index) < remainder else 0)
            y += height
            if row_number < len(rows) - 1:
                y += 6
        return y + bottom - rect.y()


def _place(item, x, y, height, size, apply):
    if apply:
        item.setGeometry(QRect(x, y + (height - size.height()) // 2, size.width(), size.height()))


def _centered_row(layout, row, area, y, height, apply):
    """Left groups packed left, the centre group on the bar's centre line,
    right groups packed right: balanced weight instead of a drifting middle."""
    indices = [index for index, _, _ in row]
    center = layout.center_index
    if center not in indices or indices[0] == center or indices[-1] == center:
        return False
    position = indices.index(center)
    left, (_, middle, middle_size), right = row[:position], row[position], row[position + 1:]
    spacing = layout.spacing()
    left_width = sum(size.width() for _, _, size in left) + spacing * (len(left) - 1)
    right_width = sum(size.width() for _, _, size in right) + spacing * (len(right) - 1)
    x = area.x() + (area.width() - middle_size.width()) // 2
    x = max(x, area.x() + left_width + spacing)
    x = min(x, area.x() + area.width() - right_width - spacing - middle_size.width())
    if x < area.x() + left_width + spacing:
        return False
    cursor = area.x()
    for _, item, size in left:
        _place(item, cursor, y, height, size, apply)
        cursor += size.width() + spacing
    _place(middle, x, y, height, middle_size, apply)
    cursor = area.x() + area.width() - right_width
    for _, item, size in right:
        _place(item, cursor, y, height, size, apply)
        cursor += size.width() + spacing
    return True


CommandFlowLayout._arrange_centered = lambda self, row, area, y, height, apply: _centered_row(
    self, row, area, y, height, apply)


def install_command_groups(page, parent_layout, old_layout, transport_start, view_start,
                           *, diagnostics_start=None, toggles_start=None, refine_start=None, output_start=None):
    """Keep functional groups intact, with the project range in its own row."""
    bar = CommandBar()
    bar.setObjectName("studioTimelineCommandBar")
    policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    policy.setHeightForWidth(True)
    bar.setSizePolicy(policy)
    flow = CommandFlowLayout(bar)
    boundaries = {transport_start: "transport", view_start: "view"}
    if diagnostics_start is not None:
        boundaries = {transport_start: "transport", diagnostics_start: "view"}
    if toggles_start is not None:
        boundaries[toggles_start] = "display"
    if refine_start is not None:
        boundaries[refine_start] = "refine"
    if output_start is not None:
        # Save frame / cover / timeline options (2026-10-09, M16).
        boundaries[output_start] = "output"
    groups, group_items, names = [], [], []
    current, name = [], "editing"
    while old_layout.count():
        item = old_layout.takeAt(0)
        widget = item.widget()
        if widget in boundaries and current:
            group_items.append(current)
            names.append(name)
            current, name = [], boundaries[widget]
        if widget is not None:
            if not widget.isHidden():
                current.append(item)
        elif item.spacerItem() is not None:
            # Keep fixed label spacing. Original expanding spacers separate
            # groups rather than taking space away from their controls.
            if not item.expandingDirections() & Qt.Orientation.Horizontal:
                current.append(item)
    if current:
        group_items.append(current)
        names.append(name)
    group_widgets = []
    for index, items in enumerate(group_items):
        group = QWidget(bar)
        group.setObjectName("timelineCommandGroup" + str(index))
        group.setProperty("commandGroup", names[index])
        inner = QHBoxLayout(group)
        # Same vertical inset for every group keeps one shared top edge.
        inner.setContentsMargins(0, 3, 0, 3)
        inner.setSpacing(12 if names[index] == "display" else 6)
        if names[index] == "transport":
            # The transport reads as one centred pill (2026-10-08).
            group.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            # 6 px above and below the 32 px play circle (was 3 around 34):
            # the controls no longer touch the pill's edge (2026-10-14).
            inner.setContentsMargins(12, 6, 12, 6)
            flow.center_index = index
        widgets = []
        for item in items:
            widget = item.widget()
            if widget is not None:
                inner.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)
                widgets.append(widget)
            else:
                inner.addItem(item)
        groups.append(widgets)
        group_widgets.append(group)
        flow.addWidget(group)
    parent_layout.removeItem(old_layout)
    old_layout.deleteLater()
    parent_layout.insertWidget(0, bar)
    # The timeline host has an older explicit minimum. DefaultConstraint keeps
    # that value even when wrapped commands require another row. Let Qt derive
    # the host minimum from its actual children and propagate it to QSplitter.
    parent_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
    page._timeline_command_bar = bar
    page._timeline_command_groups = groups
    page._timeline_group_widgets = group_widgets
    page._timeline_command_layout = flow


def toolbar_geometry_snapshot(page):
    """Read actual geometry and style identity for normal-entry UI audits."""
    bar = page._timeline_command_bar

    def record(widget):
        origin = widget.mapTo(bar, widget.rect().topLeft())
        font = widget.font()
        return dict(name=widget.objectName(), text=widget.text() if hasattr(widget, "text") else "",
                    tooltip=widget.toolTip(), visible=widget.isVisible(),
                    rect=[origin.x(), origin.y(), widget.width(), widget.height()],
                    hint=[widget.sizeHint().width(), widget.sizeHint().height()],
                    minimum=[widget.minimumSizeHint().width(), widget.minimumSizeHint().height()],
                    font=dict(family=font.family(), pixels=font.pixelSize(), points=font.pointSizeF(), weight=font.weight()),
                    local_style_sha256=hashlib.sha256(widget.styleSheet().encode()).hexdigest())

    groups = getattr(page, "_timeline_group_widgets", [])
    result = dict(width=bar.width(), height=bar.height(), dpr=bar.devicePixelRatioF(),
                  page_style_sha256=hashlib.sha256(page.styleSheet().encode()).hexdigest(),
                  groups=[dict(role=group.property("commandGroup"), **record(group),
                               controls=[record(widget) for widget in widgets])
                          for group, widgets in zip(groups, page._timeline_command_groups)])
    range_bar = getattr(page, "project_range_bar", None)
    if range_bar is not None:
        result["range_bar"] = record(range_bar)
        result["range_controls"] = [record(widget) for widget in range_bar.findChildren(QWidget)
                                    if widget.isVisible() and widget.parentWidget() is range_bar]
    return result
