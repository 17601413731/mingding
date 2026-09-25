"""检测逻辑回归测试

用仓库里现成的 3 张牌面截图 + 1 张杂图，把重构前的检测结果钉死：
重构引擎之后，黄牌占比、中心像素、最终判定都必须一模一样。

基线数字来自重构前的 main_fast_dxcam.py（其检测函数已原样搬进 engine.py）。

跑法：
    python -m unittest discover -s tests
"""

from __future__ import annotations

import sys
import threading
import unittest
from pathlib import Path
from unittest import mock

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import engine  # noqa: E402

ASSETS = Path(__file__).resolve().parent.parent / "assets"

# 文件 -> (黄牌占比, 中心像素 HSV, 是否判定为黄牌)
BASELINE = {
    "yellow_card.png": (0.532, (29, 240, 232), True),
    "red_card.png": (0.000, (0, 232, 178), False),
    "blue_card.png": (0.000, (119, 68, 231), False),
    "img.png": (0.085, (149, 119, 118), False),
}


def measure(filename):
    """复现检测流程，回传占比与中心像素，方便逐个对比基线。"""
    image = cv2.imread(str(ASSETS / filename))
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, engine.LOWER_YELLOW, engine.UPPER_YELLOW)
    ratio = cv2.countNonZero(mask) / mask.size
    h, w = hsv.shape[:2]
    center = tuple(int(value) for value in hsv[h // 2, w // 2])
    return hsv, ratio, center


class YellowCardDetectionTest(unittest.TestCase):
    def test_ratio_matches_baseline(self):
        for filename, (expected_ratio, _, _) in BASELINE.items():
            with self.subTest(file=filename):
                _, ratio, _ = measure(filename)
                self.assertAlmostEqual(ratio, expected_ratio, places=3)

    def test_center_pixel_matches_baseline(self):
        for filename, (_, expected_center, _) in BASELINE.items():
            with self.subTest(file=filename):
                _, _, center = measure(filename)
                self.assertEqual(center, expected_center)

    def test_decision_matches_baseline(self):
        for filename, (_, _, expected) in BASELINE.items():
            with self.subTest(file=filename):
                hsv, _, _ = measure(filename)
                self.assertEqual(engine.is_yellow_fast(hsv), expected)

    def test_only_the_yellow_card_is_accepted(self):
        accepted = [
            filename
            for filename in BASELINE
            if engine.is_yellow_fast(measure(filename)[0])
        ]
        self.assertEqual(accepted, ["yellow_card.png"])


class CardColorDetectionTest(unittest.TestCase):
    def test_each_card_matches_only_its_target(self):
        for target in ("blue", "yellow", "red"):
            for sample in ("blue", "yellow", "red"):
                with self.subTest(target=target, sample=sample):
                    hsv, _, _ = measure(f"{sample}_card.png")
                    self.assertEqual(engine.is_card_color(hsv, target), sample == target)

    def test_background_image_is_not_a_card(self):
        hsv, _, _ = measure("img.png")
        for color in ("blue", "yellow", "red"):
            with self.subTest(color=color):
                self.assertFalse(engine.is_card_color(hsv, color))

    def test_full_screen_samples_match_the_card_roi(self):
        for sample in ("blue", "yellow", "red"):
            frame = cv2.imread(str(ASSETS / f"{sample}.png"))
            hsv = engine.bgr_roi_to_hsv(frame, engine.ROI_CARD)
            for target in ("blue", "yellow", "red"):
                with self.subTest(sample=sample, target=target):
                    self.assertEqual(engine.is_card_color(hsv, target), sample == target)

    def test_red_wraps_across_hue_boundary(self):
        import numpy as np

        for hue in (0, 179):
            with self.subTest(hue=hue):
                hsv = np.full((10, 10, 3), (hue, 200, 200), dtype=np.uint8)
                self.assertTrue(engine.is_card_color(hsv, "red"))


class SelectionLoopTest(unittest.TestCase):
    def test_each_card_key_selects_its_own_color(self):
        selection = {"blue": "f6", "yellow": "e", "red": "f7"}
        frames = [cv2.imread(str(ASSETS / "img.png"))] + [
            cv2.imread(str(ASSETS / f"{color}_card.png"))
            for color in ("yellow", "red", "blue")
        ]

        for target, target_key in selection.items():
            with self.subTest(target=target):
                class Capture:
                    def __init__(self):
                        self.frames = iter(frames)

                    def grab_bgr(self):
                        return next(self.frames)

                    def stop(self):
                        pass

                class StopAfterFrames:
                    def __init__(self):
                        self.count = 0

                    def is_set(self):
                        self.count += 1
                        return self.count > len(frames)

                calls = 0

                def pressed(key):
                    nonlocal calls
                    frame_index = calls // len(selection)
                    calls += 1
                    return frame_index == 0 and key == target_key

                enabled = threading.Event()
                enabled.set()
                with (
                    mock.patch.object(engine, "ScreenCapture", return_value=Capture()),
                    mock.patch.object(engine, "bgr_roi_to_hsv", side_effect=lambda frame, roi: cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)),
                    mock.patch.object(engine, "is_skill_ready", return_value=True),
                    mock.patch.object(engine.input_keys, "is_pressed", side_effect=pressed),
                    mock.patch.object(engine, "press_confirm") as confirm,
                    mock.patch.object(engine.time, "perf_counter", side_effect=(0.0, 0.1, 0.2, 0.3)),
                    mock.patch.object(engine.time, "sleep"),
                ):
                    engine.capture_loop(enabled, StopAfterFrames(), selection, threading.Event())

                self.assertEqual(confirm.call_count, 2)


class CaptureGeometryTest(unittest.TestCase):
    def test_region_covers_every_roi(self):
        left, top, right, bottom = engine.CAPTURE_REGION
        for roi in (engine.ROI_CARD, engine.ROI_SKILL):
            x, y, w, h = roi
            self.assertLessEqual(left, x)
            self.assertLessEqual(top, y)
            self.assertGreaterEqual(right, x + w)
            self.assertGreaterEqual(bottom, y + h)

    def test_local_roi_is_relative_to_region(self):
        left, top = engine.CAPTURE_REGION[0], engine.CAPTURE_REGION[1]
        for roi, local in (
            (engine.ROI_CARD, engine.ROI_CARD_LOCAL),
            (engine.ROI_SKILL, engine.ROI_SKILL_LOCAL),
        ):
            x, y, w, h = roi
            self.assertEqual(local, (x - left, y - top, w, h))


if __name__ == "__main__":
    unittest.main(verbosity=2)
