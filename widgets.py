"""命定 · 自绘控件

QSS 画不出来的东西都在这里：三牌扇面、开关、角标、能录制按键的输入框。

注意两个 Qt 的事实：
- QSS 不支持 letter-spacing，字标字距只能用 QFont.setLetterSpacing。
- QSS 不支持过渡动画，开关的滑块位置用 QPropertyAnimation 驱动自绘属性。
"""

from __future__ import annotations

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPropertyAnimation,
    QRectF,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

import theme

# ============================================================
# 按键名：keyboard 与 pydirectinput 都认识的那一批
# ============================================================

_SPECIAL_KEYS = {
    Qt.Key.Key_Space: "space",
    Qt.Key.Key_Tab: "tab",
    Qt.Key.Key_Return: "enter",
    Qt.Key.Key_Enter: "enter",
    Qt.Key.Key_Backspace: "backspace",
    Qt.Key.Key_Delete: "delete",
    Qt.Key.Key_Home: "home",
    Qt.Key.Key_End: "end",
    Qt.Key.Key_Up: "up",
    Qt.Key.Key_Down: "down",
    Qt.Key.Key_Left: "left",
    Qt.Key.Key_Right: "right",
    Qt.Key.Key_Shift: "shift",
    Qt.Key.Key_Control: "ctrl",
    Qt.Key.Key_Alt: "alt",
}


def key_name(event) -> str | None:
    """把按键事件翻成键名；认不出来返回 None。Esc 交给调用方当作取消。"""
    key = event.key()

    if Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
        return chr(key).lower()
    if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
        return chr(key)
    if Qt.Key.Key_F1 <= key <= Qt.Key.Key_F12:
        return f"f{key - Qt.Key.Key_F1 + 1}"

    return _SPECIAL_KEYS.get(key)


def pretty_key(name: str) -> str:
    """键名显示成大写，单字母和 F 键看起来更像键帽。"""
    return name.upper()


# ============================================================
# 品牌标记：三张牌，中间那张是黄牌
# ============================================================


def card_fan_pixmap(size: int) -> QPixmap:
    """三牌扇面。工具干的事就是从三张牌里认出黄牌，所以标记就是这件事本身。

    托盘图标、窗口标记共用这一份画法；不用任何 Riot 素材，全是几何图形。
    """
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    center_x, center_y = size / 2.0, size * 0.47
    card_w, card_h = size * 0.26, size * 0.46
    radius = size * 0.07
    stroke = max(1.0, size * 0.028)

    # 后排三件事缺一不可：让得够开、略微下沉、比前排小一圈。
    # 只旋转会让它们被前排盖掉九成糊成一个黄块；让得不够开又会让两张后排
    # 中间连成一片，整体读成"黄牌放在一个深色托盘里"。倾角则要小，
    # 否则小尺寸下这两张牌就没有牌的形状，变成支棱出去的两只翅膀。
    layers = (
        (-size * 0.26, size * 0.05, -10.0, 0.90, theme.MARK_BACK, theme.MARK_BACK_EDGE),
        (size * 0.26, size * 0.05, 10.0, 0.90, theme.MARK_BACK, theme.MARK_BACK_EDGE),
        (0.0, 0.0, 0.0, 1.0, theme.CARD, theme.CARD),
    )

    for offset, dy, angle, scale, fill, outline in layers:
        width, height = card_w * scale, card_h * scale
        corner = radius * scale
        painter.save()
        painter.translate(center_x + offset, center_y + dy)
        painter.rotate(angle)
        painter.setBrush(QColor(fill))
        painter.setPen(QPen(QColor(outline), stroke))
        painter.drawRoundedRect(
            QRectF(-width / 2, -height / 2, width, height), corner, corner
        )
        painter.restore()

    painter.end()
    return pixmap


class CardFanMark(QWidget):
    def __init__(self, size=44, parent=None):
        super().__init__(parent)
        self._pixmap = card_fan_pixmap(size)
        self.setFixedSize(size, size)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._pixmap)
        painter.end()


# ============================================================
# 开关
# ============================================================


class ToggleSwitch(QAbstractButton):
    """开/关：轨道色 + 滑块位置 + 旁边的状态文字，三者同时表达，不只靠颜色。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(46, 26)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._offset = 0.0
        self._animation = QPropertyAnimation(self, b"offset", self)
        self._animation.setDuration(130)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate)

    def _get_offset(self) -> float:
        return self._offset

    def _set_offset(self, value: float):
        self._offset = value
        self.update()

    offset = Property(float, _get_offset, _set_offset)

    def _animate(self, checked: bool):
        self._animation.stop()
        self._animation.setStartValue(self._offset)
        self._animation.setEndValue(1.0 if checked else 0.0)
        self._animation.start()

    def set_checked_silently(self, checked: bool):
        """界面被外部事件改变时用（比如引擎报错自动关掉），不要触发动画以外的副作用。"""
        if self.isChecked() != checked:
            self.setChecked(checked)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        radius = rect.height() / 2
        inset = 3.0
        knob_d = rect.height() - inset * 2

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(theme.BRASS if self.isChecked() else theme.EDGE))
        painter.drawRoundedRect(rect, radius, radius)

        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(theme.CHALK), 1))
            painter.drawRoundedRect(rect, radius, radius)

        travel = rect.width() - inset * 2 - knob_d
        knob_x = rect.left() + inset + travel * self._offset

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(theme.INK if self.isChecked() else theme.ASH))
        painter.drawEllipse(QRectF(knob_x, inset, knob_d, knob_d))


# ============================================================
# 能录制按键的两个控件
# ============================================================


class KeyCap(QPushButton):
    """功能牌左上角的角标——它就是这张牌的热键，点一下换一个。

    扑克牌的角标本来就是索引，这里让它承载"这个功能绑的哪个键"。
    """

    captureStarted = Signal()
    captureFinished = Signal()
    keyCaptured = Signal(str)

    def __init__(self, key: str, parent=None):
        super().__init__(pretty_key(key), parent)
        self.setObjectName("KeyCap")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFont(theme.num_font(theme.SIZE_NOTE, QFont.Weight.DemiBold))
        self.setMinimumWidth(52)
        self.setToolTip("点一下，然后按下你想用的键")
        self._capturing = False
        self.clicked.connect(self._on_clicked)

    def set_key(self, key: str):
        self.setText(pretty_key(key))

    def _set_capturing(self, capturing: bool):
        self._capturing = capturing
        self.setProperty("capturing", "true" if capturing else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        if capturing:
            self.setText("按键…")
            self.setFocus(Qt.FocusReason.OtherFocusReason)
        else:
            self.captureFinished.emit()

    def _on_clicked(self):
        if not self._capturing:
            self.begin_capture()

    def begin_capture(self):
        self._capturing = True
        self._set_capturing(True)
        self.captureStarted.emit()

    def keyPressEvent(self, event):
        if not self._capturing:
            super().keyPressEvent(event)
            return

        event.accept()
        if event.key() == Qt.Key.Key_Escape:
            self._capturing = False
            self._set_capturing(False)
            return

        name = key_name(event)
        if name is None:
            return

        self._capturing = False
        self.set_key(name)
        self._set_capturing(False)
        self.keyCaptured.emit(name)

    def focusOutEvent(self, event):
        if self._capturing:
            self._capturing = False
            self._set_capturing(False)
        super().focusOutEvent(event)


class KeyField(QLineEdit):
    """自动移动按下的键。点一下进入录制，按什么就是什么。"""

    captureStarted = Signal()
    captureFinished = Signal()
    keyCaptured = Signal(str)

    def __init__(self, key: str, parent=None):
        super().__init__(parent)
        self.setObjectName("KeyField")
        self.setReadOnly(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFont(theme.num_font(theme.SIZE_BODY, QFont.Weight.DemiBold))
        self.setFixedWidth(64)
        self.setToolTip("点一下，然后按下你想用的键")
        self._capturing = False
        self.set_key(key)

    def set_key(self, key: str):
        self.setText(pretty_key(key))

    def _set_capturing(self, capturing: bool):
        self._capturing = capturing
        self.setProperty("capturing", "true" if capturing else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        if capturing:
            self.setText("按键…")
        else:
            self.captureFinished.emit()

    def mousePressEvent(self, event):
        if not self._capturing:
            self._capturing = True
            self._set_capturing(True)
            self.captureStarted.emit()
        event.accept()

    def keyPressEvent(self, event):
        if not self._capturing:
            super().keyPressEvent(event)
            return

        event.accept()
        if event.key() == Qt.Key.Key_Escape:
            self._capturing = False
            self._set_capturing(False)
            return

        name = key_name(event)
        if name is None:
            return

        self._capturing = False
        self.set_key(name)
        self._set_capturing(False)
        self.keyCaptured.emit(name)

    def focusOutEvent(self, event):
        if self._capturing:
            self._capturing = False
            self._set_capturing(False)
        super().focusOutEvent(event)


# ============================================================
# 功能牌
# ============================================================


class FeatureCard(QFrame):
    """一个功能一张牌：左上角是它的热键，右上角是开关和状态，下面是它做什么。"""

    toggled = Signal(bool)
    hotkeyRequested = Signal(str)

    def __init__(self, title, note, hotkey, parent=None):
        super().__init__(parent)
        self.setObjectName("FeatureCard")
        self.setProperty("active", "false")

        content = QVBoxLayout(self)
        content.setContentsMargins(
            theme.PAD_CARD, theme.PAD_CARD, theme.PAD_CARD, theme.PAD_CARD
        )
        content.setSpacing(9)

        top = QHBoxLayout()
        top.setSpacing(10)
        self.key_cap = KeyCap(hotkey)
        self.key_cap.keyCaptured.connect(self.hotkeyRequested.emit)
        top.addWidget(self.key_cap)
        top.addStretch(1)

        self.state_label = QLabel("已关闭")
        self.state_label.setObjectName("CardNote")
        top.addWidget(self.state_label)

        self.switch = ToggleSwitch()
        self.switch.toggled.connect(self._on_toggled)
        top.addWidget(self.switch)
        content.addLayout(top)

        title_label = QLabel(title)
        title_label.setObjectName("CardTitle")
        title_label.setFont(theme.ui_font(theme.SIZE_TITLE, QFont.Weight.DemiBold))
        content.addWidget(title_label)

        note_label = QLabel(note)
        note_label.setObjectName("CardNote")
        note_label.setWordWrap(True)
        content.addWidget(note_label)

        self.error = ErrorBanner()
        content.addWidget(self.error)

        self._extra = QVBoxLayout()
        self._extra.setSpacing(9)
        content.addLayout(self._extra)
        content.addStretch(1)

        self.set_active(False)

    def add_content(self, widget: QWidget):
        self._extra.addWidget(widget)

    def _on_toggled(self, checked: bool):
        self.set_active(checked)
        self.toggled.emit(checked)

    def set_active(self, active: bool):
        self.setProperty("active", "true" if active else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        self.state_label.setText("已开启" if active else "已关闭")
        self.state_label.setStyleSheet(
            f"color: {theme.BRASS if active else theme.ASH};"
        )

    def set_hotkey(self, key: str):
        self.key_cap.set_key(key)

    def set_error(self, message: str):
        self.error.show_message(message)

    def clear_error(self):
        self.error.hide()


class ErrorBanner(QFrame):
    """出错时说清楚哪里错了、怎么办，而不是把状态行改成一串报错。"""

    toggled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ErrorBanner")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)

        self._label = QLabel()
        self._label.setObjectName("ErrorText")
        self._label.setWordWrap(True)
        layout.addWidget(self._label)

        self.hide()

    def showEvent(self, event):
        super().showEvent(event)
        self.toggled.emit()

    def hideEvent(self, event):
        super().hideEvent(event)
        self.toggled.emit()

    def show_message(self, message: str):
        self._label.setText(message)
        self.show()


class MoveSettingsRow(QWidget):
    """自动移动的按键与间隔。改完立刻生效，没有"应用"按钮。"""

    keyChanged = Signal(str)
    intervalChanged = Signal(int)

    def __init__(self, key: str, interval_ms: int, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        key_label = QLabel("按键")
        key_label.setObjectName("FieldLabel")
        layout.addWidget(key_label)

        self.key_field = KeyField(key)
        self.key_field.keyCaptured.connect(self.keyChanged.emit)
        layout.addWidget(self.key_field)

        layout.addSpacing(12)

        interval_label = QLabel("间隔")
        interval_label.setObjectName("FieldLabel")
        layout.addWidget(interval_label)

        self.interval_field = QSpinBox()
        self.interval_field.setObjectName("IntervalField")
        self.interval_field.setRange(20, 1000)
        self.interval_field.setSingleStep(10)
        self.interval_field.setValue(interval_ms)
        self.interval_field.setSuffix(" 毫秒")
        self.interval_field.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.interval_field.setFont(theme.num_font(theme.SIZE_BODY, QFont.Weight.DemiBold))
        self.interval_field.setFixedWidth(96)
        # 打字打到一半不要立刻生效，编辑结束或点上下箭头才生效
        self.interval_field.setKeyboardTracking(False)
        self.interval_field.valueChanged.connect(self.intervalChanged.emit)
        layout.addWidget(self.interval_field)

        layout.addStretch(1)
