"""统一读取键盘和鼠标按键状态。"""

import ctypes

import keyboard

MOUSE_KEYS = {
    "mouse_left": 0x01,
    "mouse_right": 0x02,
    "mouse_middle": 0x04,
    "mouse_x1": 0x05,
    "mouse_x2": 0x06,
}


def is_mouse_key(key: str) -> bool:
    return key in MOUSE_KEYS


def is_pressed(key: str) -> bool:
    if key in MOUSE_KEYS:
        return bool(ctypes.windll.user32.GetAsyncKeyState(MOUSE_KEYS[key]) & 0x8000)
    return keyboard.is_pressed(key)
