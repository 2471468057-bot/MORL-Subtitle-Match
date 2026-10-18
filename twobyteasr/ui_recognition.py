"""识别方案区：三张角色模型卡（UI IMPLEMENTATION 批准图 #1/#2）。

角色卡是首页第一视觉焦点：
- role 小字 + 大号模型名（视觉主体）+ [本地/在线] + 状态 + 底部「点击更换 ↻」
- 整卡可点击（鼠标 / Enter / Space）→ 发出 role_requested，由 MainWindow
  打开模型工坊并 focus 对应角色
- 缺模型 / API 未配置 → 卡内状态提示 + 唯一恢复动作
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QFrame,
    QBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from twobyteasr.ui_theme import (
    AMBER,
    AMBER_SOFT as WARM,
    BORDER_STRONG as WARM_BORDER,
    CORAL,
    GREEN,
    GREEN_SOFT,
    GREEN_SUBTLE,
    INK,
    MUTED,
)
from twobyteasr.i18n import current_language, translate
from twobyteasr.theme_manager import theme_key
from twobyteasr.ui_theme import theme_definition

from .i18n import bind_text

from .i18n import tr

# role → (图标字符, 卡底色, 边框色)
_ROLE_STYLES = {
    "primary": ("主", GREEN_SOFT, GREEN),
    "timeline": ("轴", WARM, WARM_BORDER),
    "review": ("核", GREEN_SOFT, GREEN),
}
_ROLE_LABELS = {"primary": "主力转写", "timeline": "字幕时间轴", "review": "文字复核"}
_ROLE_DESCRIPTIONS = {
    "primary": "中文多人转写与说话人区分",
    "timeline": "断句、时间轴与字幕节奏校准",
    "review": "错词复核、专名与上下文纠正",
}


class RecognitionRoleCard(QFrame):
    """单张角色模型卡。整卡 clickable + 键盘可触发。"""

    clicked = Signal(str)  # role
    recovery_requested = Signal(str, str)  # role, action: install/api

    # role → (qtawesome 图标, 卡底色, 边框/强调色)
    _ROLE_STYLES = {
        "primary": ("fa5s.wave-square", GREEN_SOFT, GREEN),
        "timeline": ("fa5s.clock", WARM, WARM_BORDER),
        "review": ("fa5s.check-circle", GREEN_SOFT, GREEN),
    }
    _ROLE_LABELS = {"primary": "主力转写", "timeline": "字幕时间轴", "review": "文字复核"}

    def __init__(self, role: str, parent=None):
        super().__init__(parent)
        import qtawesome as qta

        self.role = role
        self.setObjectName("recognitionRoleCard")
        self.setProperty("role", role)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumHeight(228)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        bind_text(self, '{value0} 模型卡', property='accessibleName', value0=_ROLE_LABELS.get(role, role))
        self._responsive_profile = ""
        self._responsive_apply_count = 0
        self._identity_centered = False

        icon_name, _card_bg, _border = self._ROLE_STYLES.get(
            role, ("fa5s.circle", GREEN_SOFT, GREEN)
        )
        self._icon_name = icon_name
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(8)

        self._leading_space_index = layout.count()
        self._leading_space = QSpacerItem(
            0,
            0,
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Fixed,
        )
        layout.addSpacerItem(self._leading_space)

        top = QHBoxLayout()
        top.setSpacing(10)
        top.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.icon_label = QLabel()
        self.icon_label.setObjectName("recognitionRoleIcon")
        self.icon_label.setFixedSize(44, 44)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setPixmap(qta.icon(icon_name, color=self._icon_color()).pixmap(20, 20))
        top.addWidget(self.icon_label)
        top.addStretch(1)
        layout.addLayout(top)
        self._upper_gap = QSpacerItem(
            0,
            0,
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Fixed,
        )
        layout.addSpacerItem(self._upper_gap)
        self.role_label = QLabel(_ROLE_LABELS.get(role, role))
        self.role_label.setObjectName("recognitionRoleLabel")
        layout.addWidget(self.role_label)

        self.model_label = QLabel("—")
        self.model_label.setProperty("uiZoomOwnSize", True)  # height measured from its own text
        self.model_label.setObjectName("recognitionModelName")
        self.model_label.setWordWrap(True)
        self.model_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self.model_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        layout.addWidget(self.model_label)
        self.description_label = QLabel(_ROLE_DESCRIPTIONS.get(role, ""))
        self.description_label.setObjectName("recognitionModelDescription")
        self.description_label.setWordWrap(True)
        layout.addWidget(self.description_label)
        self._body_stretch_index = layout.count()
        layout.addStretch(3)

        rule = QFrame()
        rule.setObjectName("contentRule")
        rule.setFixedHeight(1)
        layout.addWidget(rule)

        status_row = self._status_layout = QGridLayout()
        status_row.setSpacing(6)
        self.kind_badge = QLabel("")
        self.kind_badge.setObjectName("recognitionKindBadge")
        self.kind_badge.setSizePolicy(
            QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed
        )
        self.kind_badge.hide()
        status_row.addWidget(self.kind_badge, 0, 0)
        self.status_badge = QLabel("")
        self.status_badge.setObjectName("recognitionStatusGood")
        self.status_badge.setSizePolicy(
            QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed
        )
        status_row.addWidget(self.status_badge, 0, 1)
        status_row.setColumnStretch(2, 1)
        self.recovery = QPushButton("")
        self.recovery.setObjectName("recognitionRecovery")
        self.recovery.setCursor(Qt.CursorShape.PointingHandCursor)
        self.recovery.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        # Beside the chips the button must not pin the card's minimum width:
        # otherwise a card widened once (maximized window) can never narrow
        # again, so it never wraps the button below and the page overflows.
        self.recovery.setProperty("flexibleWidth", True)
        self.recovery.setMinimumWidth(1)
        self.recovery.hide()
        self.recovery.clicked.connect(
            lambda: self.recovery_requested.emit(self.role, self._recovery_action)
        )
        status_row.addWidget(self.recovery, 0, 3)
        layout.addLayout(status_row)

        footer = QHBoxLayout()
        self.change_hint = QLabel("点击更换")
        self.change_hint.setObjectName("recognitionChangeHint")
        footer.addWidget(self.change_hint)
        footer.addStretch(1)
        swap = QLabel("详情  ›")
        swap.setObjectName("recognitionChangeHint")
        bind_text(swap, '查看模型详情', property='toolTip')
        swap.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        footer.addWidget(swap)
        layout.addLayout(footer)

        for child in (
            self.icon_label,
            self.role_label,
            self.model_label,
            self.description_label,
            self.kind_badge,
            self.status_badge,
            self.change_hint,
        ):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._recovery_action = ""
        self.apply_responsive_profile("compact")

    def retranslate(self, language: str | None = None):
        language = language or current_language()
        role_text = translate(_ROLE_LABELS.get(self.role, self.role), language)
        self.role_label.setText(role_text)
        bind_text(self.change_hint, translate('点击更换', language))
        self.setAccessibleName(
            f"{role_text} " + ("model card" if language == "en" else "模型卡")
        )

    def refresh_theme_palette(self) -> None:
        import qtawesome as qta

        size = max(20, round(self.icon_label.width() * 0.46))
        self.icon_label.setPixmap(
            qta.icon(self._icon_name, color=self._icon_color()).pixmap(size, size)
        )
        self._sync_model_slot_height()

    def _icon_color(self):
        theme = theme_definition(theme_key())
        # The chip is painted with the role's identity hue (theme.role_colors).
        return theme.on_vivid

    # ------------------------------------------------------------ 事件

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.role)
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return, Qt.Key.Key_Space):
            self.clicked.emit(self.role)
            return
        super().keyPressEvent(event)

    # ------------------------------------------------------------ 状态

    def set_state(self, model_name: str, kind: str, status: str, tone: str, recovery: str = ""):
        """model_name 主值；kind=本地/在线；status=已就绪/需要下载/未配置/已关闭；
        tone=good/warn/muted；recovery=唯一恢复动作文案（空=无）。"""
        self.model_label.setText(model_name)
        if kind:
            self.kind_badge.setText(kind)
            self.kind_badge.show()
        else:
            self.kind_badge.clear()
            self.kind_badge.hide()
        self.status_badge.setText(status)
        self.status_badge.setVisible(bool(status))
        self.status_badge.setObjectName(
            {"good": "recognitionStatusGood", "warn": "recognitionStatusWarn",
             "muted": "recognitionStatusMuted"}.get(tone, "recognitionStatusMuted")
        )
        self._recovery_action = recovery
        if recovery:
            self.recovery.setText(recovery)
            self.recovery.show()
        else:
            self.recovery.hide()
        self.status_badge.style().unpolish(self.status_badge)
        self.status_badge.style().polish(self.status_badge)
        self.status_badge.update()
        self._sync_model_slot_height()
        self._layout_status()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # During a reparent the card is briefly 0x0. Running the height sync
        # then schedules a QTimer that fires while Qt is still mid-layout,
        # which loops (C++ stack overflow). Only sync on a real size.
        if self.width() > 0 and self.height() > 0:
            self._sync_model_slot_height()
        self._layout_status()

    def retranslate_ui(self):
        self._layout_status()

    def _layout_status(self):
        if not hasattr(self, 'recovery'):
            return
        margins=self.layout().contentsMargins()
        available=self.width()-margins.left()-margins.right()
        needed=sum(w.sizeHint().width() for w in (self.kind_badge,self.status_badge,self.recovery) if not w.isHidden())+18
        wrapped=needed>available and not self.recovery.isHidden()
        if wrapped==getattr(self,'_status_wrapped',None):
            return
        self._status_wrapped=wrapped
        self._status_layout.removeWidget(self.recovery)
        if wrapped:
            self._status_layout.addWidget(self.recovery,1,0,1,4,Qt.AlignmentFlag.AlignRight)
        else:
            self._status_layout.addWidget(self.recovery,0,3)

    def apply_ui_zoom(self, _factor):
        """Interface zoom changed: re-apply the current profile (glyph size)."""
        profile, self._responsive_profile = self._responsive_profile, None
        self.apply_responsive_profile(profile or "normal")

    def apply_responsive_profile(self, profile: str):
        """Apply one of three bounded density profiles.

        This is deliberately threshold-based. Continuous window resizing does
        not rebuild QSS or repolish the card until the profile actually changes.
        """
        profile = profile if profile in {
            "compact", "normal", "large", "extra_large"
        } else "normal"
        if profile == self._responsive_profile:
            return False

        config = {
            # 四十八轮（用户"主页变丑了，能变回原样吗"）：03bd900 把三档卡片
            # 全部压成小图标+等边距的紧凑形态，角色卡失去呼吸感——回滚到
            # 原始分档（compact/normal/large/extra_large 各自有层次）。
            "compact": {"margins": (16, 14, 16, 12), "spacing": 7, "icon": 44, "glyph": 20, "gap": 0, "minimum": 228},
            "normal": {"margins": (18, 18, 18, 14), "spacing": 9, "icon": 56, "glyph": 26, "gap": 4, "minimum": 288},
            "large": {"margins": (20, 20, 20, 16), "spacing": 10, "icon": 68, "glyph": 32, "gap": 7, "minimum": 342},
            "extra_large": {"margins": (22, 22, 22, 17), "spacing": 11, "icon": 68, "glyph": 32, "gap": 8, "minimum": 376},
        }[profile]
        self._responsive_profile = profile
        self._responsive_apply_count += 1
        self.setProperty("density", profile)
        layout = self.layout()
        from . import ui_zoom
        # Logical px: the interface zoom scales them (ui_zoom).
        ui_zoom.set_layout(layout, config["margins"], config["spacing"])
        self._upper_gap.changeSize(
            0,
            config["gap"],
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Fixed,
        )
        self._apply_identity_balance(profile != "compact")
        ui_zoom.set_size(self.icon_label, fixed_w=config["icon"], fixed_h=config["icon"])
        self.description_label.setVisible(profile != "compact")
        import qtawesome as qta
        self.icon_label.setPixmap(
            qta.icon(self._icon_name, color=self._icon_color()).pixmap(
                ui_zoom.px(config["glyph"]), ui_zoom.px(config["glyph"])
            )
        )
        ui_zoom.set_size(self, min_h=config["minimum"])
        self.style().unpolish(self)
        self.style().polish(self)
        # Qt does not always invalidate child rules that depend on a dynamic
        # property of the parent. Refresh only the two responsive labels when
        # the bounded profile changes, never on every resize pixel.
        for label in (self.role_label, self.model_label, self.description_label):
            label.style().unpolish(label)
            label.style().polish(label)
        # Every card owns the same top-aligned two-line model slot. A one-line
        # name never recenters itself and cannot move the rows below it.
        self._sync_model_slot_height()
        layout.invalidate()
        self.update()
        return True

    def _sync_model_slot_height(self) -> None:
        """Keep the two-line identity slot valid after application QSS changes."""
        # 同步执行 + 守卫：在 Qt 布局激活中途用 QTimer 触发 setFixedHeight 会
        # 让 C++ 布局层自激递归（栈溢出）。这里直接走父级的批量同步，父级用
        # _syncing_identity_height 标志挡住 setFixedHeight 触发的子卡回环。
        parent = self.parentWidget()
        sync = getattr(parent, "_sync_identity_height", None)
        if callable(sync):
            sync()
        else:
            self.model_label.setFixedHeight(self._required_model_slot_height())

    def _required_model_slot_height(self) -> int:
        self.model_label.ensurePolished()
        metrics = QFontMetrics(self.model_label.font())
        # Long online model names wrap naturally; reserve two rows as the
        # common baseline, with a third only when the actual label needs it.
        width = max(80, self.width() - self.layout().contentsMargins().left() - self.layout().contentsMargins().right())
        height = metrics.boundingRect(0, 0, width, 2000, Qt.TextFlag.TextWordWrap, self.model_label.text()).height()
        return max(metrics.lineSpacing() * 2, height)

    def _apply_identity_balance(self, centered: bool):
        centered = bool(centered)
        if centered == self._identity_centered:
            return False
        self._identity_centered = centered
        layout = self.layout()
        self._leading_space.changeSize(
            0,
            0,
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Expanding if centered else QSizePolicy.Policy.Fixed,
        )
        # Balance the identity block between equal flexible spaces; the
        # fixed footer keeps model names near the optical center of the card.
        layout.setStretch(self._leading_space_index, 1 if centered else 0)
        layout.setStretch(self._body_stretch_index, 1)
        layout.invalidate()
        return True


class RecognitionPlanWidget(QWidget):
    """识别方案：三张角色卡横排；窄容器自动改为纵向堆叠。"""

    role_requested = Signal(str)          # 点击卡 → 打开工坊该角色
    recovery_requested = Signal(str, str)  # role, action → MainWindow 处理

    # 每张卡的最小逻辑宽约 230px；两张并排至少需要 ~560px 内容宽，三张 ~760。
    # 右停泊面板约 790px，减去边距后模型卡区仅 ~730px，三卡横排会超出右缘。
    # 阈值取 900：在面板内一律竖排，避免横向裁切/溢出。
    STACK_BELOW = 900

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # QBoxLayout (not QHBoxLayout) so the direction can flip at runtime.
        layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self.cards: dict[str, RecognitionRoleCard] = {}
        for role in ("primary", "timeline", "review"):
            card = RecognitionRoleCard(role)
            card.clicked.connect(self.role_requested.emit)
            card.recovery_requested.connect(self.recovery_requested.emit)
            layout.addWidget(card, 12 if role == "primary" else 10)
            self.cards[role] = card
        self._responsive_profile = ""
        self._stacked: bool | None = None

    def apply_density(self, comfortable: bool):
        self._update_responsive_profile(comfortable)

    def _sync_identity_height(self) -> None:
        if not self.cards or getattr(self, "_syncing_identity_height", False):
            return
        self._syncing_identity_height = True
        try:
            height = max(card._required_model_slot_height() for card in self.cards.values())
            for card in self.cards.values():
                card.model_label.setFixedHeight(height)
        finally:
            self._syncing_identity_height = False

    def retranslate(self, language: str | None = None):
        for card in self.cards.values():
            card.retranslate(language)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_stacking()
        self._update_responsive_profile()

    def showEvent(self, event):
        # Reparenting into the modal scroll area does not fire a resize before
        # show, so re-evaluate the stacking direction here too.
        super().showEvent(event)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self._apply_stacking)

    def _apply_stacking(self) -> None:
        """Stack the role cards vertically when the widget is too narrow.

        Three cards side by side need roughly 760 logical px; below that the
        rightmost card is clipped by the container edge with no way to reach
        it, so the row re-orients instead.
        """
        layout = self.layout()
        if layout is None:
            return
        stacked = self.width() < self.STACK_BELOW
        if stacked == self._stacked:
            return
        self._stacked = stacked
        layout.setDirection(
            QBoxLayout.Direction.TopToBottom if stacked
            else QBoxLayout.Direction.LeftToRight
        )

    def _update_responsive_profile(self, comfortable: bool | None = None):
        layout = self.layout()
        spacing = layout.spacing() if layout is not None else 10
        calculated_width = max(0, (self.width() - spacing * 2) // 3)
        card_widths = [card.width() for card in self.cards.values() if card.width() > 0]
        available_width = min(card_widths) if card_widths else calculated_width
        # During a resize event child geometries can still describe the
        # previous layout pass.  The calculated width is the actual per-card
        # allocation for the new size, so use the smaller value.
        if calculated_width > 0:
            available_width = min(available_width, calculated_width) if available_width else calculated_width
        card_heights = [card.height() for card in self.cards.values() if card.height() > 0]
        available_height = min(card_heights) if card_heights else self.height()
        available_height = min(available_height, self.height())
        # Thresholds are in 100% pixels: at a larger interface zoom the cards
        # take the profile of a correspondingly smaller window.
        from .ui_zoom import logical
        available_width, available_height = logical(available_width), logical(available_height)

        if available_height < 300 or available_width < 175:
            profile = "compact"
        elif available_height < 365 or available_width < 285:
            profile = "normal"
        elif available_height < 455 or available_width < 325:
            profile = "large"
        else:
            profile = "extra_large"
        if available_height <= 0:
            profile = "normal" if comfortable else "compact"
        if profile == self._responsive_profile:
            return False
        self._responsive_profile = profile
        for card in self.cards.values():
            card.apply_responsive_profile(profile)
        return True
