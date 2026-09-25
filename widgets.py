"""命定 · 自绘控件

QSS 画不出来的东西都在这里：三牌扇面、开关、角标、能录制按键的输入框。

注意两个 Qt 的事实：
- QSS 不支持 letter-spacing，字标字距只能用 QFont.setLetterSpacing。
- QSS 不支持过渡动画，开关的滑块位置用 QPropertyAnimation 驱动自绘属性。
"""

from __future__ import annotations

from PySide6.QtCore import (
    Property,
    QObject,
    QEasingCurve,
    QPropertyAnimation,
    QRectF,
    Qt,
    Signal,
    QTimer,
)
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

import theme
import input_keys

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
    mouse_labels = {
        "mouse_left": "鼠标左键",
        "mouse_right": "鼠标右键",
        "mouse_middle": "鼠标中键",
        "mouse_x1": "鼠标侧键 1",
        "mouse_x2": "鼠标侧键 2",
    }
    if name in mouse_labels:
        return mouse_labels[name]
    return name.upper()


def mouse_button_name(button) -> str | None:
    return {
        Qt.MouseButton.LeftButton: "mouse_left",
        Qt.MouseButton.RightButton: "mouse_right",
        Qt.MouseButton.MiddleButton: "mouse_middle",
        Qt.MouseButton.BackButton: "mouse_x1",
        Qt.MouseButton.ForwardButton: "mouse_x2",
    }.get(button)


# ============================================================
# 品牌标记：三张牌，中间的默认目标是黄牌
# ============================================================


def card_fan_pixmap(size: int) -> QPixmap:
    """三牌扇面。中央黄牌保留默认目标的品牌记忆。

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


class MouseCaptureMonitor(QObject):
    """录制期间轮询全局鼠标状态；先等待启动录制的点击松开。"""

    captured = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._armed = False
        self._timer = QTimer(self)
        self._timer.setInterval(10)
        self._timer.timeout.connect(self._poll)

    def start(self):
        self._armed = False
        self._timer.start()

    def stop(self):
        self._timer.stop()

    def _poll(self):
        pressed = [key for key in input_keys.MOUSE_KEYS if input_keys.is_pressed(key)]
        if not pressed:
            self._armed = True
        elif self._armed and len(pressed) == 1:
            self.stop()
            self.captured.emit(pressed[0])


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
        self.setToolTip("点一下，再按键盘键或鼠标键；Esc 取消")
        self.setAccessibleName("启停快捷键")
        self._capturing = False
        self._key = key
        self._mouse_capture = MouseCaptureMonitor(self)
        self._mouse_capture.captured.connect(self._commit_key)
        self.clicked.connect(self._on_clicked)

    def set_key(self, key: str):
        self._key = key
        self.setText(pretty_key(key))

    def _set_capturing(self, capturing: bool):
        self._capturing = capturing
        if capturing:
            self._mouse_capture.start()
        else:
            self._mouse_capture.stop()
        self.setProperty("capturing", "true" if capturing else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        if capturing:
            self.setText("按键或鼠标…")
            self.setFocus(Qt.FocusReason.OtherFocusReason)
        else:
            self.set_key(self._key)
            self.captureFinished.emit()

    def _on_clicked(self):
        if not self._capturing:
            self.begin_capture()

    def begin_capture(self):
        self._set_capturing(True)
        self.captureStarted.emit()

    def _commit_key(self, name: str):
        if not self._capturing:
            return
        self.set_key(name)
        self.keyCaptured.emit(name)
        self._set_capturing(False)

    def mousePressEvent(self, event):
        if self._capturing:
            name = mouse_button_name(event.button())
            if name:
                self._commit_key(name)
                event.accept()
                return
        super().mousePressEvent(event)

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

        self._commit_key(name)

    def focusOutEvent(self, event):
        if self._capturing:
            self._capturing = False
            self._set_capturing(False)
        super().focusOutEvent(event)


class KeyField(QLineEdit):
    """可复用的按键录制框；Esc 取消后恢复原键。"""

    captureStarted = Signal()
    captureFinished = Signal()
    keyCaptured = Signal(str)

    def __init__(self, key: str, parent=None, allow_mouse: bool = True):
        super().__init__(parent)
        self.setObjectName("KeyField")
        self.setReadOnly(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFont(theme.num_font(theme.SIZE_BODY, QFont.Weight.DemiBold))
        self.setFixedWidth(96 if allow_mouse else 64)
        self.setToolTip("点一下，再按键盘键或鼠标键；Esc 取消" if allow_mouse else "点一下，再按游戏内绑定的键盘键；Esc 取消")
        self._capturing = False
        self._key = key
        self._allow_mouse = allow_mouse
        self._mouse_capture = MouseCaptureMonitor(self) if allow_mouse else None
        if self._mouse_capture:
            self._mouse_capture.captured.connect(self._commit_key)
        self.set_key(key)

    def set_key(self, key: str):
        self._key = key
        self.setText(pretty_key(key))

    def _set_capturing(self, capturing: bool):
        self._capturing = capturing
        if self._mouse_capture:
            if capturing:
                self._mouse_capture.start()
            else:
                self._mouse_capture.stop()
        self.setProperty("capturing", "true" if capturing else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        if capturing:
            self.setText("按键或鼠标…" if self._allow_mouse else "按键…")
        else:
            self.set_key(self._key)
            self.captureFinished.emit()

    def mousePressEvent(self, event):
        if not self._capturing:
            self.begin_capture()
        elif self._allow_mouse:
            mouse_name = mouse_button_name(event.button())
            if mouse_name:
                self._commit_key(mouse_name)
        event.accept()

    def begin_capture(self):
        self._set_capturing(True)
        self.setFocus(Qt.FocusReason.OtherFocusReason)
        self.captureStarted.emit()

    def _commit_key(self, name: str):
        if not self._capturing:
            return
        self.set_key(name)
        self.keyCaptured.emit(name)
        self._set_capturing(False)

    def keyPressEvent(self, event):
        if not self._capturing:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
                self.begin_capture()
                event.accept()
                return
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

        self._commit_key(name)

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
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        content = QVBoxLayout(self)
        content.setContentsMargins(
            theme.PAD_CARD, theme.PAD_CARD, theme.PAD_CARD, theme.PAD_CARD
        )
        content.setSpacing(9)

        top = QHBoxLayout()
        top.setSpacing(10)
        self.key_cap = KeyCap(hotkey)
        self.key_cap.setAccessibleName(f"{title}启停快捷键")
        self.key_cap.keyCaptured.connect(self.hotkeyRequested.emit)
        hotkey_label = QLabel("启停键")
        hotkey_label.setObjectName("FieldLabel")
        top.addWidget(hotkey_label)
        top.addWidget(self.key_cap)
        top.addStretch(1)

        self.state_label = QLabel("已关闭")
        self.state_label.setObjectName("CardNote")
        top.addWidget(self.state_label)

        self.switch = ToggleSwitch()
        self.switch.setAccessibleName(f"{title}开关")
        self.switch.toggled.connect(self._on_toggled)
        top.addWidget(self.switch)
        content.addLayout(top)

        title_label = QLabel(title)
        title_label.setObjectName("CardTitle")
        title_label.setFont(theme.ui_font(theme.SIZE_TITLE, QFont.Weight.DemiBold))
        content.addWidget(title_label)

        self.note_label = QLabel(note)
        self.note_label.setObjectName("CardNote")
        self.note_label.setWordWrap(True)
        content.addWidget(self.note_label)

        self.error = ErrorBanner()
        content.addWidget(self.error)

        self._extra = QVBoxLayout()
        self._extra.setSpacing(9)
        content.addLayout(self._extra)

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

    def set_note(self, note: str):
        self.note_label.setText(note)

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


class SelectSettings(QWidget):
    """蓝、黄、红三张牌各自的选牌按键。"""

    cardKeyChanged = Signal(str, str)

    def __init__(self, card_keys: dict[str, str], parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        self.fields = {}
        for color, label in (("blue", "蓝牌"), ("yellow", "黄牌"), ("red", "红牌")):
            column = QVBoxLayout()
            column.setSpacing(5)
            card_label = QLabel(label)
            card_label.setObjectName("CardKeyLabel")
            card_label.setProperty("cardColor", color)
            column.addWidget(card_label)
            field = KeyField(card_keys[color])
            field.setAccessibleName(f"{label}选牌按键")
            field.keyCaptured.connect(
                lambda key, chosen=color: self.cardKeyChanged.emit(chosen, key)
            )
            card_label.setBuddy(field)
            column.addWidget(field, 0, Qt.AlignmentFlag.AlignLeft)
            self.fields[color] = field
            layout.addLayout(column, 1)

    def set_card_key(self, color: str, key: str):
        self.fields[color].set_key(key)


class MoveSettingsRow(QWidget):
    """自由移动的按键与间隔；改完立刻生效。"""

    keyChanged = Signal(str)
    intervalChanged = Signal(int)

    def __init__(self, key: str, interval_ms: int, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(9)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        key_label = QLabel("按键")
        key_label.setObjectName("FieldLabel")
        layout.addWidget(key_label)

        self.key_field = KeyField(key, allow_mouse=False)
        self.key_field.setAccessibleName("游戏内鼠标移动按键")
        self.key_field.keyCaptured.connect(self.keyChanged.emit)
        key_label.setBuddy(self.key_field)
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
        self.interval_field.setAccessibleName("自由移动连发间隔，毫秒")
        interval_label.setBuddy(self.interval_field)
        # 打字打到一半不要立刻生效，编辑结束或点上下箭头才生效
        self.interval_field.setKeyboardTracking(False)
        self.interval_field.valueChanged.connect(self.intervalChanged.emit)
        layout.addWidget(self.interval_field)

        layout.addStretch(1)
        outer.addLayout(layout)

        self.guide = QLabel()
        self.guide.setObjectName("CardNote")
        self.guide.setWordWrap(True)
        outer.addWidget(self.guide)
        self.set_guidance(key, interval_ms)

    def set_guidance(self, key: str, interval_ms: int):
        self.guide.setText(
            f"先在游戏内将「鼠标移动按键」设为 {pretty_key(key)}（与上方按键一致）。"
            f"开启后按住鼠标右键，程序每 {interval_ms} 毫秒发送一次 {pretty_key(key)}。"
        )
