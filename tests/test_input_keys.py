"""键盘和鼠标按键状态读取。"""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import input_keys  # noqa: E402


class InputKeysTest(unittest.TestCase):
    def test_mouse_button_reads_windows_virtual_key(self):
        with mock.patch.object(input_keys.ctypes, "windll", create=True) as windll:
            windll.user32.GetAsyncKeyState.return_value = 0x8000
            self.assertTrue(input_keys.is_pressed("mouse_x1"))
            windll.user32.GetAsyncKeyState.assert_called_once_with(0x05)

    def test_keyboard_key_uses_keyboard_hook(self):
        with mock.patch.object(input_keys.keyboard, "is_pressed", return_value=True) as pressed:
            self.assertTrue(input_keys.is_pressed("e"))
            pressed.assert_called_once_with("e")
