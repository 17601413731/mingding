"""选牌与自由移动设置的界面交互测试。"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
import input_keys  # noqa: E402
import theme  # noqa: E402
from window import MainWindow  # noqa: E402


class SettingsWindowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        theme.apply(cls.app)

    def setUp(self):
        self.real_save = config.save
        self.save_patch = mock.patch.object(config, "save", return_value=True)
        self.save_patch.start()
        self.window = MainWindow(dict(config.DEFAULTS), ui_only=True)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.hide()
        self.window.deleteLater()
        self.app.processEvents()
        self.save_patch.stop()

    def test_each_card_has_its_own_key(self):
        fields = self.window.select_settings.fields
        self.assertEqual({color: field.text() for color, field in fields.items()}, {
            "blue": "鼠标侧键 2", "yellow": "E", "red": "鼠标侧键 1",
        })

    def test_trigger_recording_suspends_engine_and_rejects_conflicts(self):
        field = self.window.select_settings.fields["blue"]
        field.begin_capture()
        self.assertTrue(self.window.capture_paused.is_set())
        QTest.keyClick(field, Qt.Key.Key_N)
        self.assertFalse(self.window.capture_paused.is_set())
        self.assertEqual(field.text(), "鼠标侧键 2")
        self.assertEqual(self.window.cfg["card_key_blue"], "mouse_x2")
        self.assertIn("占用", self.window.select_card.error._label.text())

    def test_trigger_recording_accepts_a_free_key(self):
        field = self.window.select_settings.fields["red"]
        field.begin_capture()
        QTest.keyClick(field, Qt.Key.Key_Q)
        self.assertEqual(self.window.cfg["card_key_red"], "q")
        self.assertEqual(self.window.selection["red"], "q")
        self.assertEqual(self.window.cfg["card_key_yellow"], "e")
        self.assertFalse(self.window.capture_paused.is_set())

    def test_card_records_mouse_side_button(self):
        self.window._change_card_key("red", "r")
        field = self.window.select_settings.fields["blue"]
        field.begin_capture()
        with mock.patch.object(input_keys, "is_pressed", side_effect=lambda key: False):
            field._mouse_capture._poll()
        with mock.patch.object(input_keys, "is_pressed", side_effect=lambda key: key == "mouse_x1"):
            field._mouse_capture._poll()
        self.assertEqual(self.window.cfg["card_key_blue"], "mouse_x1")
        self.assertEqual(self.window.selection["blue"], "mouse_x1")
        self.assertEqual(field.text(), "鼠标侧键 1")
        self.assertFalse(self.window.capture_paused.is_set())

    def test_card_records_mouse_left_button_clicked_on_field(self):
        field = self.window.select_settings.fields["red"]
        field.begin_capture()
        QTest.mouseClick(field, Qt.MouseButton.LeftButton)
        self.assertEqual(self.window.cfg["card_key_red"], "mouse_left")
        self.assertEqual(field.text(), "鼠标左键")

    def test_toggle_recorder_accepts_mouse_click(self):
        cap = self.window.select_card.key_cap
        cap.begin_capture()
        QTest.mouseClick(cap, Qt.MouseButton.MiddleButton)
        self.assertEqual(self.window.cfg["hotkey_select"], "mouse_middle")
        self.assertEqual(cap.text(), "鼠标中键")

    def test_toggle_uses_mouse_button_on_press_edge(self):
        self.window.cfg["hotkey_select"] = "mouse_middle"
        self.window.ui_only = False
        with mock.patch.object(input_keys, "is_pressed", return_value=False), mock.patch("window.keyboard.add_hotkey", return_value=1):
            self.window._register_hotkeys()
        seen = []
        self.window.bridge.message.connect(lambda name, _: seen.append(name))
        with mock.patch.object(input_keys, "is_pressed", side_effect=lambda key: key == "mouse_middle"):
            self.window._poll_mouse_hotkeys()
            self.window._poll_mouse_hotkeys()
        self.assertEqual(seen, ["toggle_select"])
        self.window._remove_hotkeys()

    def test_right_button_reserved_for_free_move(self):
        self.window._change_card_key("red", "mouse_right")
        self.assertEqual(self.window.cfg["card_key_red"], "mouse_x1")
        self.assertIn("自由移动", self.window.select_card.error._label.text())

    def test_free_move_instruction_tracks_the_configured_key(self):
        self.window._change_move_key("k")
        self.window._change_interval(250)
        guide = self.window.move_row.guide.text()
        self.assertIn("游戏内", guide)
        self.assertIn("鼠标移动按键", guide)
        self.assertIn("K", guide)
        self.assertIn("250 毫秒", guide)

    def test_changed_keys_survive_window_reopen(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "mingding" / "config.json"
            with (
                mock.patch.object(config, "config_path", return_value=path),
                mock.patch.object(config, "save", side_effect=self.real_save),
            ):
                self.window._change_card_key("blue", "q")
                self.window._change_card_key("red", "r")
                self.window._change_interval(250)
                reopened = MainWindow(config.load(), ui_only=True)
                try:
                    self.assertEqual(reopened.select_settings.fields["blue"].text(), "Q")
                    self.assertEqual(reopened.select_settings.fields["red"].text(), "R")
                    self.assertEqual(reopened.move_row.interval_field.value(), 250)
                finally:
                    reopened.deleteLater()


if __name__ == "__main__":
    unittest.main(verbosity=2)
