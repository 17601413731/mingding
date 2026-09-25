"""命定 · 设计令牌

常态强调仍用黄铜；蓝、黄、红只用在三张牌的按键标签中表达牌色：

    BRASS  黄铜 —— 常态。开启状态、可点的角标、输入框聚焦。
    CARD   牌黄 —— 默认目标牌和品牌标记。

底色用深靛蓝黑而不是中性黑，这是卡牌大师自己的色域，金色压在上面不刺眼。
"""

from __future__ import annotations

import ctypes
import string

# ===================== 颜色 =====================
INK = "#0F1220"       # 窗口底
FELT = "#171B2E"      # 牌面（比窗口底亮一级）
EDGE = "#272C46"      # 描边与关闭态
BRASS = "#C9A227"     # 常态强调：黄铜
CARD = "#F2C230"      # 黄牌标签与品牌标记
BLUE_CARD = "#8DB8FF" # 蓝牌标签
RED_CARD = "#FF8F83"  # 红牌标签，区别于错误橙红
CHALK = "#E9EAF2"     # 主文字
ASH = "#868CA6"       # 次要文字
EMBER = "#DC5A3C"     # 仅错误
EMBER_WASH = "rgba(220, 90, 60, 0.12)"

# 品牌标记里压在后排的两张牌。必须明显亮于 INK，否则 44px 下三张牌会糊成一块。
MARK_BACK = "#262C4C"
MARK_BACK_EDGE = "#414A7C"

# ===================== 圆角 =====================
# 两级：牌面比控件圆得多，让"容器"和"容器里的东西"在形状上就分得开
RADIUS_CARD = 14
RADIUS_CONTROL = 8

# ===================== 字号（pt，随 DPI 缩放）=====================
SIZE_WORDMARK = 22.0
SIZE_TITLE = 13.0
SIZE_BODY = 10.5
SIZE_NOTE = 9.5

# ===================== 间距 =====================
PAD_WINDOW = 20
GAP_CARDS = 12
PAD_CARD = 16

# ===================== 字体族 =====================
# 不打包字体：任何一台 Windows 都要能直接显示中文。
# 在这条约束里做刻意的选择——字标用 Light + 宽字距（字距 QSS 不支持，用 QFont 设），
# 数值用 Segoe UI 并开启 tnum 等宽数位，避免计数跳动时左右抖。
UI_FAMILY = "Microsoft YaHei UI"
NUM_FAMILY = "Segoe UI"


def ui_font(size=SIZE_BODY, weight=None, letter_spacing=None):
    from PySide6.QtGui import QFont

    font = QFont(UI_FAMILY, 1)
    font.setPointSizeF(size)
    if weight is not None:
        font.setWeight(weight)
    if letter_spacing is not None:
        font.setLetterSpacing(
            QFont.SpacingType.PercentageSpacing, 100 + letter_spacing * 100
        )
    return font


def num_font(size=SIZE_BODY, weight=None):
    """数值用：Segoe UI + 等宽数位，数字变化时不会左右抖。"""
    from PySide6.QtGui import QFont

    font = QFont(NUM_FAMILY, 1)
    font.setPointSizeF(size)
    if weight is not None:
        font.setWeight(weight)
    font.setFeature(QFont.Tag("tnum"), 1)
    return font


_STYLESHEET = string.Template(
    """
QWidget#Root {
    background-color: $INK;
}

QLabel {
    color: $CHALK;
    background: transparent;
}

QLabel#Wordmark {
    color: $CHALK;
}

QLabel#Tagline {
    color: $ASH;
}

/* ---------- 功能牌 ---------- */
QFrame#FeatureCard {
    background-color: $FELT;
    border: 1px solid $EDGE;
    border-radius: ${RADIUS_CARD}px;
}

QFrame#FeatureCard[active="true"] {
    border: 1px solid $BRASS;
}

QFrame#Spine {
    background-color: $BRASS;
    border-top-left-radius: 3px;
    border-bottom-left-radius: 3px;
}

QLabel#CardTitle {
    color: $CHALK;
}

QLabel#CardNote {
    color: $ASH;
}

/* ---------- 角标 = 热键 ---------- */
QPushButton#KeyCap {
    color: $BRASS;
    background-color: transparent;
    border: 1px solid $EDGE;
    border-radius: 6px;
    padding: 2px 9px;
}

QPushButton#KeyCap:hover {
    border: 1px solid $BRASS;
}

QPushButton#KeyCap:focus {
    border: 1px solid $BRASS;
}

QPushButton#KeyCap[capturing="true"] {
    color: $INK;
    background-color: $BRASS;
    border: 1px solid $BRASS;
}

/* ---------- 输入 ---------- */
QLineEdit#KeyField, QSpinBox#IntervalField {
    color: $CHALK;
    background-color: $INK;
    border: 1px solid $EDGE;
    border-radius: ${RADIUS_CONTROL}px;
    padding: 4px 8px;
    selection-background-color: $BRASS;
    selection-color: $INK;
}

QLineEdit#KeyField:hover, QSpinBox#IntervalField:hover {
    border: 1px solid $BRASS;
}

QLineEdit#KeyField:focus, QSpinBox#IntervalField:focus {
    border: 1px solid $BRASS;
}

QLineEdit#KeyField[capturing="true"] {
    color: $BRASS;
    border: 1px solid $BRASS;
}

QLineEdit#KeyField[readOnly="true"] {
    color: $CHALK;
}

QSpinBox#IntervalField::up-button, QSpinBox#IntervalField::down-button {
    width: 0px;
    border: none;
}

QLabel#FieldLabel {
    color: $ASH;
}

/* ---------- 独立选牌按键 ---------- */
QLabel#CardKeyLabel[cardColor="blue"] { color: $BLUE_CARD; }
QLabel#CardKeyLabel[cardColor="yellow"] { color: $CARD; }
QLabel#CardKeyLabel[cardColor="red"] { color: $RED_CARD; }

/* ---------- 错误 ---------- */
QFrame#ErrorBanner {
    background-color: $EMBER_WASH;
    border: 1px solid $EMBER;
    border-radius: ${RADIUS_CONTROL}px;
}

QLabel#ErrorText {
    color: $EMBER;
}

/* ---------- 退出 ---------- */
QPushButton#Quit {
    color: $ASH;
    background-color: transparent;
    border: 1px solid $EDGE;
    border-radius: ${RADIUS_CONTROL}px;
    padding: 7px 16px;
}

QPushButton#Quit:hover {
    color: $CHALK;
    border: 1px solid $ASH;
}

QPushButton#Quit:pressed {
    background-color: $EDGE;
}

/* ---------- 托盘菜单 ---------- */
QMenu {
    background-color: $FELT;
    color: $CHALK;
    border: 1px solid $EDGE;
    border-radius: ${RADIUS_CONTROL}px;
    padding: 6px;
}

QMenu::item {
    padding: 6px 22px 6px 12px;
    border-radius: 6px;
}

QMenu::item:selected {
    background-color: $EDGE;
    color: $CHALK;
}

QMenu::separator {
    height: 1px;
    background: $EDGE;
    margin: 5px 8px;
}

QToolTip {
    color: $CHALK;
    background-color: $FELT;
    border: 1px solid $EDGE;
    padding: 4px 7px;
}
"""
).substitute(
    INK=INK,
    FELT=FELT,
    EDGE=EDGE,
    BRASS=BRASS,
    CARD=CARD,
    BLUE_CARD=BLUE_CARD,
    RED_CARD=RED_CARD,
    CHALK=CHALK,
    ASH=ASH,
    EMBER=EMBER,
    EMBER_WASH=EMBER_WASH,
    RADIUS_CARD=RADIUS_CARD,
    RADIUS_CONTROL=RADIUS_CONTROL,
)


def apply(app):
    """套用全局字体与样式表。"""
    from PySide6.QtGui import QFont

    base = QFont(UI_FAMILY, 1)
    base.setPointSizeF(SIZE_BODY)
    app.setFont(base)
    app.setStyleSheet(_STYLESHEET)


def enable_dark_titlebar(widget):
    """让 Windows 原生标题栏跟着一起变深，免得亮色系统栏劈开整个界面。"""
    try:
        hwnd = int(widget.winId())
        enabled = ctypes.c_int(1)
        for attribute in (20, 19):  # 20 是 Win10 20H1+，19 是更早的版本
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attribute, ctypes.byref(enabled), ctypes.sizeof(enabled)
            )
    except Exception:
        # 拿不到句柄或系统不支持时保持原生外观，不值得为此中断启动
        pass
