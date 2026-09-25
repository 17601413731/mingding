"""命定 · 主窗口

界面只做三件事：让人一眼看出开没开、不用切出游戏就能改、改完立刻生效。
真正干活的是 engine.py，两边通过一个 Qt 信号通信——跨线程发信号 Qt 会自动排队，
所以引擎线程直接 emit 是安全的，界面线程不会被别的东西碰。
"""

from __future__ import annotations

import threading
import winsound

import keyboard
from PySide6.QtCore import QObject, Qt, Signal, QTimer
from PySide6.QtGui import QAction, QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMenu,
    QPushButton,
    QSizePolicy,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

import config
import engine
import input_keys
import theme
from widgets import (
    CardFanMark,
    FeatureCard,
    MoveSettingsRow,
    SelectSettings,
    card_fan_pixmap,
    pretty_key,
)

WINDOW_WIDTH = 470
CARD_LABELS = {"blue": "蓝牌", "yellow": "黄牌", "red": "红牌"}

# W 是程序发出的游戏技能键，不能分配给其它功能。
RESERVED_KEYS = (engine.CONFIRM_KEY, "mouse_right")
KEY_SLOTS = (
    "hotkey_select", "hotkey_move", "move_key",
    "card_key_blue", "card_key_yellow", "card_key_red",
)


def play_toggle_sound(enabled: bool):
    """开关音放后台线程响。

    winsound.Beep 是阻塞的，会在界面线程里卡一百多毫秒——原版每次按 F2/F3
    界面都会顿一下，就是因为它在主循环里直接响。
    """
    tones = [(880, 120), (1046, 120)] if enabled else [(660, 180)]

    def beep():
        for frequency, duration in tones:
            try:
                winsound.Beep(frequency, duration)
            except RuntimeError:
                winsound.MessageBeep()
                break

    threading.Thread(target=beep, daemon=True, name="beep").start()


class Bridge(QObject):
    """引擎线程 → 界面线程的唯一通道。"""

    message = Signal(str, object)


class MainWindow(QWidget):
    def __init__(self, cfg, ui_only=False):
        super().__init__()
        self.cfg = cfg
        self.ui_only = ui_only

        self.setObjectName("Root")
        self.setWindowTitle("命定")
        self.setWindowIcon(QIcon(card_fan_pixmap(256)))

        self.select_enabled = threading.Event()
        self.move_enabled = threading.Event()
        self.stop_event = threading.Event()
        self.move = {
            "key": cfg["move_key"],
            "interval": cfg["move_interval_ms"] / 1000.0,
        }
        self.selection = {
            color: cfg[f"card_key_{color}"] for color in config.CARD_COLORS
        }
        self.capture_paused = threading.Event()

        self.bridge = Bridge()
        self.bridge.message.connect(self._on_message)
        self._hotkeys = {}
        self._mouse_hotkeys = {}
        self._mouse_hotkey_states = {}
        self._mouse_hotkey_timer = QTimer(self)
        self._mouse_hotkey_timer.setInterval(10)
        self._mouse_hotkey_timer.timeout.connect(self._poll_mouse_hotkeys)
        self._hotkeys_suspended = False
        self._threads = []
        self._tray_notice_shown = False
        self._config_error = False

        self._build_ui()
        self._build_tray()
        theme.enable_dark_titlebar(self)

        self.select_card.error.toggled.connect(self._fit_window)
        self.move_card.error.toggled.connect(self._fit_window)
        self._fit_window()

        if not ui_only:
            self._register_hotkeys()
            self._start_engine()

    def _fit_window(self):
        """窗口宽度固定，高度贴着内容走。

        必须先解开高度锁定再量，否则错误横幅弹出来时会被裁掉一半。
        """
        self.setFixedWidth(WINDOW_WIDTH)
        self.setMinimumHeight(0)
        self.setMaximumHeight(16777215)
        self.adjustSize()
        self.setFixedHeight(self.height())

    # ==================== 界面 ====================

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(
            theme.PAD_WINDOW, theme.PAD_WINDOW, theme.PAD_WINDOW, theme.PAD_WINDOW
        )
        root.setSpacing(0)

        header = QWidget()
        header.setLayout(self._build_header())
        header.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        root.addWidget(header)
        root.addSpacing(18)

        self.select_card = FeatureCard(
            "自由选牌",
            "每张牌各有一个按键；按对应键后程序按 W 轮牌，出现该牌时再按 W 锁定。",
            self.cfg["hotkey_select"],
        )
        self.select_card.toggled.connect(self._apply_select)
        self.select_card.hotkeyRequested.connect(
            lambda key: self._change_hotkey("hotkey_select", key, self.select_card)
        )
        self.select_card.key_cap.captureStarted.connect(self._suspend_hotkeys)
        self.select_card.key_cap.captureFinished.connect(self._resume_hotkeys)
        self.select_settings = SelectSettings(self.selection)
        self.select_settings.cardKeyChanged.connect(self._change_card_key)
        for field in self.select_settings.fields.values():
            field.captureStarted.connect(self._suspend_hotkeys)
            field.captureFinished.connect(self._resume_hotkeys)
        self.select_card.add_content(self.select_settings)
        root.addWidget(self.select_card)
        root.addSpacing(theme.GAP_CARDS)

        self.move_card = FeatureCard(
            "自由移动",
            "减少长时间反复点击鼠标导致的手疼。",
            self.cfg["hotkey_move"],
        )
        self.move_card.toggled.connect(self._apply_move)
        self.move_card.hotkeyRequested.connect(
            lambda key: self._change_hotkey("hotkey_move", key, self.move_card)
        )
        self.move_card.key_cap.captureStarted.connect(self._suspend_hotkeys)
        self.move_card.key_cap.captureFinished.connect(self._resume_hotkeys)

        self.move_row = MoveSettingsRow(
            self.cfg["move_key"], self.cfg["move_interval_ms"]
        )
        self.move_row.keyChanged.connect(self._change_move_key)
        self.move_row.intervalChanged.connect(self._change_interval)
        self.move_row.key_field.captureStarted.connect(self._suspend_hotkeys)
        self.move_row.key_field.captureFinished.connect(self._resume_hotkeys)
        self.move_card.add_content(self.move_row)
        root.addWidget(self.move_card)

        root.addSpacing(18)
        root.addLayout(self._build_footer())

    def _build_header(self):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(14)
        row.addWidget(CardFanMark(44), 0, Qt.AlignmentFlag.AlignTop)

        text = QVBoxLayout()
        text.setSpacing(1)

        wordmark = QLabel("命定")
        wordmark.setObjectName("Wordmark")
        wordmark.setFont(
            theme.ui_font(
                theme.SIZE_WORDMARK, QFont.Weight.Light, letter_spacing=0.28
            )
        )
        text.addWidget(wordmark)

        self.tagline = QLabel("蓝 · 黄 · 红，按键直达")
        self.tagline.setObjectName("Tagline")
        text.addWidget(self.tagline)

        row.addLayout(text)
        row.addStretch(1)
        return row

    def _build_footer(self):
        row = QHBoxLayout()
        row.setSpacing(10)

        hint = QLabel("关掉窗口会留在托盘")
        hint.setObjectName("CardNote")
        row.addWidget(hint)
        row.addStretch(1)

        quit_button = QPushButton("退出程序")
        quit_button.setObjectName("Quit")
        quit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        quit_button.clicked.connect(self.quit)
        row.addWidget(quit_button)
        return row

    def _build_tray(self):
        self.tray = QSystemTrayIcon(QIcon(card_fan_pixmap(64)), self)
        self.tray.setToolTip("命定")

        menu = QMenu()

        show_action = QAction("显示主界面", self)
        show_action.triggered.connect(self._restore_window)
        menu.addAction(show_action)
        menu.addSeparator()

        self.tray_select = QAction("自由选牌", self)
        self.tray_select.setCheckable(True)
        self.tray_select.triggered.connect(self._toggle_select)
        menu.addAction(self.tray_select)

        self.tray_move = QAction("自由移动", self)
        self.tray_move.setCheckable(True)
        self.tray_move.triggered.connect(self._toggle_move)
        menu.addAction(self.tray_move)

        menu.addSeparator()
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.quit)
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        if not self.ui_only:
            self.tray.show()

    # ==================== 开关 ====================

    def _apply_select(self, enabled: bool):
        if enabled:
            self.select_enabled.set()
        else:
            self.select_enabled.clear()

        self.select_card.switch.set_checked_silently(enabled)
        self.select_card.set_active(enabled)
        self.tray_select.setChecked(enabled)
        play_toggle_sound(enabled)

    def _apply_move(self, enabled: bool):
        if enabled:
            self.move_enabled.set()
        else:
            self.move_enabled.clear()

        self.move_card.switch.set_checked_silently(enabled)
        self.move_card.set_active(enabled)
        self.tray_move.setChecked(enabled)
        play_toggle_sound(enabled)

    def _toggle_select(self):
        self._apply_select(not self.select_enabled.is_set())

    def _toggle_move(self):
        self._apply_move(not self.move_enabled.is_set())

    # ==================== 热键 ====================

    def _register_hotkeys(self):
        if self.ui_only or self._hotkeys_suspended:
            return

        self._remove_hotkeys()
        for slot, event_name in (
            ("hotkey_select", "toggle_select"),
            ("hotkey_move", "toggle_move"),
        ):
            key = self.cfg[slot]
            if input_keys.is_mouse_key(key):
                self._mouse_hotkeys[slot] = (key, event_name)
                self._mouse_hotkey_states[slot] = input_keys.is_pressed(key)
                continue
            try:
                self._hotkeys[slot] = keyboard.add_hotkey(
                    key, lambda name=event_name: self.bridge.message.emit(name, None)
                )
            except Exception as exc:
                # 原版这里没有保护，非管理员启动时热键会直接失效且毫无提示
                self._card_for(slot).set_error(
                    f"热键 {key.upper()} 注册失败，请用管理员身份运行。{exc}"
                )
        if self._mouse_hotkeys:
            self._mouse_hotkey_timer.start()

    def _poll_mouse_hotkeys(self):
        for slot, (key, event_name) in self._mouse_hotkeys.items():
            pressed = input_keys.is_pressed(key)
            if pressed and not self._mouse_hotkey_states[slot]:
                self.bridge.message.emit(event_name, None)
            self._mouse_hotkey_states[slot] = pressed

    def _remove_hotkeys(self):
        self._mouse_hotkey_timer.stop()
        self._mouse_hotkeys.clear()
        self._mouse_hotkey_states.clear()
        for handle in self._hotkeys.values():
            try:
                keyboard.remove_hotkey(handle)
            except (KeyError, ValueError):
                pass
        self._hotkeys.clear()

    def _suspend_hotkeys(self):
        """录制新键的时候必须先摘掉全局热键，否则按 F2 会顺手把功能开关掉。"""
        if self._hotkeys_suspended:
            return
        self._hotkeys_suspended = True
        self.capture_paused.set()
        self._remove_hotkeys()

    def _resume_hotkeys(self):
        if not self._hotkeys_suspended:
            return
        self._hotkeys_suspended = False
        self._register_hotkeys()
        self.capture_paused.clear()

    def _card_for(self, slot):
        return self.select_card if slot == "hotkey_select" else self.move_card

    # ==================== 配置改动 ====================

    def _conflict(self, key: str, slot: str):
        """这个键能不能用在 slot 上，不能就说清楚为什么。"""
        if key in RESERVED_KEYS:
            if key == "mouse_right":
                return "鼠标右键用于自由移动，请换一个键"
            return f"{key.upper()} 是游戏选牌技能键，换一个"

        if slot == "move_key" and input_keys.is_mouse_key(key):
            return "自由移动的输出键须是游戏内绑定的键盘键"

        if any(self.cfg[other] == key for other in KEY_SLOTS if other != slot):
            return f"{pretty_key(key)} 已经被别的功能占用了，换一个"
        return None

    def _change_card_key(self, color, key):
        slot = f"card_key_{color}"
        problem = self._conflict(key, slot)
        if problem:
            self.select_settings.set_card_key(color, self.cfg[slot])
            self.select_card.set_error(f"{CARD_LABELS[color]}：{problem}")
            return

        self.cfg[slot] = key
        self.selection[color] = key
        self.select_card.clear_error()
        self._save()

    def _change_hotkey(self, slot, key, card):
        problem = self._conflict(key, slot)
        if problem:
            card.set_hotkey(self.cfg[slot])
            card.set_error(problem)
            return

        self.cfg[slot] = key
        card.set_hotkey(key)
        card.clear_error()
        self._register_hotkeys()
        self._save()

    def _change_move_key(self, key):
        problem = self._conflict(key, "move_key")
        if problem:
            self.move_row.key_field.set_key(self.cfg["move_key"])
            self.move_card.set_error(problem)
            return

        self.cfg["move_key"] = key
        self.move["key"] = key
        self.move_row.set_guidance(key, self.cfg["move_interval_ms"])
        self.move_card.clear_error()
        self._save()

    def _change_interval(self, milliseconds: int):
        self.cfg["move_interval_ms"] = milliseconds
        self.move["interval"] = milliseconds / 1000.0
        self.move_row.set_guidance(self.cfg["move_key"], milliseconds)
        self._save()

    def _save(self):
        ok = config.save(self.cfg)
        if ok and self._config_error:
            self._config_error = False
            self.select_card.clear_error()
        elif not ok:
            self._config_error = True
            self.select_card.set_error(
                "配置写不进去：程序所在目录没有写权限，改动只在本次运行有效"
            )

    # ==================== 引擎 ====================

    def _start_engine(self):
        self._threads = [
            threading.Thread(
                target=engine.capture_loop,
                args=(
                    self.select_enabled,
                    self.stop_event,
                    self.selection,
                    self.capture_paused,
                    self._notify,
                ),
                daemon=True,
                name="capture",
            ),
            threading.Thread(
                target=engine.auto_move_loop,
                args=(
                    self.move_enabled,
                    self.stop_event,
                    self.move,
                    self._notify,
                ),
                daemon=True,
                name="move",
            ),
        ]
        for thread in self._threads:
            thread.start()

    def _notify(self, event_name, payload=None):
        """引擎线程调用；Qt 会把这个信号排队到界面线程再执行。"""
        self.bridge.message.emit(event_name, payload)

    def _on_message(self, event_name, payload):
        if event_name == "toggle_select":
            self._toggle_select()
        elif event_name == "toggle_move":
            self._toggle_move()
        elif event_name == "error":
            self.select_card.set_error(
                f"{payload}　请用管理员身份运行，并确认游戏分辨率和 ROI 一致。"
            )
            self._apply_select(False)
        elif event_name == "move_error":
            self.move_card.set_error(payload)
            self._apply_move(False)

    # ==================== 托盘与退出 ====================

    def _on_tray_activated(self, reason):
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._restore_window()

    def _restore_window(self):
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            # 没有托盘就别把窗口藏起来，否则程序就找不回来了
            self.quit()
            event.accept()
            return

        event.ignore()
        self.hide()
        if not self._tray_notice_shown:
            self._tray_notice_shown = True
            self.tray.showMessage(
                "命定还在后台运行",
                f"{pretty_key(self.cfg['hotkey_select'])} / "
                f"{pretty_key(self.cfg['hotkey_move'])} 照样有效，双击托盘图标可以再打开。",
                QSystemTrayIcon.MessageIcon.Information,
                4000,
            )

    def quit(self):
        self.stop_event.set()
        self._remove_hotkeys()
        for thread in self._threads:
            thread.join(timeout=1.0)
        self.tray.hide()
        QApplication.quit()
