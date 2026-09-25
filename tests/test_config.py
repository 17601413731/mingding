"""配置读写测试

用临时目录顶替真实的 config.json，不会碰到你自己的配置。

跑法：
    python -m unittest discover -s tests
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402


class ConfigTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._original_path = config.config_path
        self._original_legacy_path = config.legacy_config_path
        self.path = Path(self._tmp.name) / "config.json"
        self.legacy_path = Path(self._tmp.name) / "legacy" / "config.json"
        config.config_path = lambda: self.path
        config.legacy_config_path = lambda: self.legacy_path

    def tearDown(self):
        config.config_path = self._original_path
        config.legacy_config_path = self._original_legacy_path
        self._tmp.cleanup()

    def test_missing_file_falls_back_to_defaults_and_creates_it(self):
        self.assertFalse(self.path.exists())
        self.assertEqual(config.load(), config.DEFAULTS)
        self.assertTrue(self.path.exists())

    def test_config_path_uses_appdata(self):
        from unittest import mock

        with mock.patch.dict("os.environ", {"APPDATA": str(Path(self._tmp.name) / "Roaming")}, clear=False):
            self.assertEqual(
                self._original_path(),
                Path(self._tmp.name) / "Roaming" / "mingding" / "config.json",
            )

    def test_migrates_old_config_once(self):
        self.legacy_path.parent.mkdir()
        self.legacy_path.write_text(
            json.dumps({"card_key_blue": "q", "card_key_red": "r", "move_interval_ms": 250}),
            encoding="utf-8",
        )
        loaded = config.load()
        self.assertEqual(loaded["card_key_blue"], "q")
        self.assertEqual(loaded["card_key_red"], "r")
        self.assertEqual(loaded["move_interval_ms"], 250)
        self.assertTrue(self.path.exists())
        self.legacy_path.write_text("{}", encoding="utf-8")
        self.assertEqual(config.load(), loaded)

    def test_save_creates_config_directory_and_survives_reload(self):
        self.path = Path(self._tmp.name) / "Roaming" / "mingding" / "config.json"
        saved = dict(config.DEFAULTS, card_key_blue="q", card_key_red="r")
        self.assertTrue(config.save(saved))
        self.assertEqual(config.load(), saved)

    def test_round_trip(self):
        saved = dict(
            config.DEFAULTS,
            card_key_blue="q",
            card_key_red="r",
            move_key="k",
            move_interval_ms=250,
        )
        self.assertTrue(config.save(saved))
        loaded = config.load()
        self.assertEqual(loaded["move_key"], "k")
        self.assertEqual(loaded["move_interval_ms"], 250)
        self.assertEqual(loaded["card_key_blue"], "q")
        self.assertEqual(loaded["card_key_yellow"], "e")
        self.assertEqual(loaded["card_key_red"], "r")

    def test_old_config_gains_selection_defaults(self):
        self.path.write_text(json.dumps({"hotkey_select": "f4", "move_key": "k"}), encoding="utf-8")
        loaded = config.load()
        self.assertEqual(loaded["card_key_blue"], "mouse_x2")
        self.assertEqual(loaded["card_key_yellow"], "e")
        self.assertEqual(loaded["card_key_red"], "mouse_x1")
        self.assertEqual(loaded["hotkey_select"], "f4")
        self.assertEqual(loaded["move_key"], "k")

    def test_previous_selected_card_keeps_its_trigger_key(self):
        self.path.write_text(
            json.dumps({"target_card": "blue", "select_trigger_key": "q"}),
            encoding="utf-8",
        )
        loaded = config.load()
        self.assertEqual(loaded["card_key_blue"], "q")
        self.assertEqual(loaded["card_key_yellow"], "e")
        self.assertNotIn("target_card", loaded)

    def test_duplicate_card_keys_are_made_distinct(self):
        self.path.write_text(
            json.dumps({"card_key_blue": "e", "card_key_yellow": "e"}),
            encoding="utf-8",
        )
        loaded = config.load()
        self.assertEqual(len({loaded[f"card_key_{c}"] for c in config.CARD_COLORS}), 3)

    def test_previous_red_selection_keeps_its_e_key_without_duplicates(self):
        self.path.write_text(
            json.dumps({"target_card": "red", "select_trigger_key": "e"}),
            encoding="utf-8",
        )
        loaded = config.load()
        self.assertEqual(loaded["card_key_red"], "e")
        self.assertEqual(len({loaded[f"card_key_{c}"] for c in config.CARD_COLORS}), 3)

    def test_interval_is_clamped_on_both_ends(self):
        self.path.write_text(json.dumps({"move_interval_ms": 5}), encoding="utf-8")
        self.assertEqual(
            config.load()["move_interval_ms"], config.MOVE_INTERVAL_MIN_MS
        )
        self.path.write_text(json.dumps({"move_interval_ms": 99999}), encoding="utf-8")
        self.assertEqual(
            config.load()["move_interval_ms"], config.MOVE_INTERVAL_MAX_MS
        )

    def test_keys_are_normalised(self):
        self.path.write_text(json.dumps({"move_key": "  K  "}), encoding="utf-8")
        self.assertEqual(config.load()["move_key"], "k")

    def test_mouse_keys_persist_but_right_button_and_move_output_are_reserved(self):
        self.path.write_text(
            json.dumps({
                "card_key_blue": "mouse_x2",
                "card_key_red": "mouse_right",
                "hotkey_select": "mouse_middle",
                "move_key": "mouse_left",
            }), encoding="utf-8"
        )
        loaded = config.load()
        self.assertEqual(loaded["card_key_blue"], "mouse_x2")
        self.assertEqual(loaded["hotkey_select"], "mouse_middle")
        self.assertEqual(loaded["card_key_red"], config.DEFAULTS["card_key_red"])
        self.assertEqual(loaded["move_key"], config.DEFAULTS["move_key"])

    def test_missing_fields_keep_their_defaults(self):
        self.path.write_text(json.dumps({"move_key": "k"}), encoding="utf-8")
        loaded = config.load()
        self.assertEqual(loaded["move_key"], "k")
        self.assertEqual(loaded["hotkey_select"], config.DEFAULTS["hotkey_select"])
        self.assertEqual(
            loaded["move_interval_ms"], config.DEFAULTS["move_interval_ms"]
        )

    def test_blank_or_wrong_typed_values_keep_defaults(self):
        self.path.write_text(
            json.dumps({"move_key": "   ", "hotkey_move": 42}), encoding="utf-8"
        )
        loaded = config.load()
        self.assertEqual(loaded["move_key"], config.DEFAULTS["move_key"])
        self.assertEqual(loaded["hotkey_move"], config.DEFAULTS["hotkey_move"])

    def test_broken_json_falls_back_to_defaults(self):
        self.path.write_text("{ this is not json", encoding="utf-8")
        self.assertEqual(config.load(), config.DEFAULTS)

    def test_saved_file_is_plain_utf8_json(self):
        config.save(dict(config.DEFAULTS))
        self.assertEqual(
            json.loads(self.path.read_text(encoding="utf-8")), config.DEFAULTS
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
