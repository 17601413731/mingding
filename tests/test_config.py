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
        self.path = Path(self._tmp.name) / "config.json"
        config.config_path = lambda: self.path

    def tearDown(self):
        config.config_path = self._original_path
        self._tmp.cleanup()

    def test_missing_file_falls_back_to_defaults_and_creates_it(self):
        self.assertFalse(self.path.exists())
        self.assertEqual(config.load(), config.DEFAULTS)
        self.assertTrue(self.path.exists())

    def test_round_trip(self):
        saved = dict(config.DEFAULTS, move_key="k", move_interval_ms=250)
        self.assertTrue(config.save(saved))
        loaded = config.load()
        self.assertEqual(loaded["move_key"], "k")
        self.assertEqual(loaded["move_interval_ms"], 250)

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
