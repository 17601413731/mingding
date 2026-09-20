"""检测逻辑回归测试

用仓库里现成的 3 张牌面截图 + 1 张杂图，把重构前的检测结果钉死：
重构引擎之后，黄牌占比、中心像素、最终判定都必须一模一样。

基线数字来自重构前的 main_fast_dxcam.py（其检测函数已原样搬进 engine.py）。

跑法：
    python -m unittest discover -s tests
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

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
