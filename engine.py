"""命定 · 采集与操作引擎

检测、采集与输入不依赖界面框架；notify 是普通回调。
"""

from __future__ import annotations

import ctypes
import time

import cv2
import dxcam
import numpy as np
import pydirectinput

import input_keys

# ===================== 屏幕区域 (x, y, w, h)，需按分辨率标定 =====================
ROI_CARD = (854, 996, 33, 34)
ROI_SKILL = (854, 996, 33, 34)

# ===================== 牌色 HSV 阈值（依据 assets/*_card.png）=====================
LOWER_YELLOW = np.array([15, 140, 150])
UPPER_YELLOW = np.array([35, 255, 255])
YELLOW_RATIO_THRESHOLD = 0.15
CARD_RANGES = {
    "blue": ((np.array([100, 55, 100]), np.array([135, 255, 255])),),
    "yellow": ((LOWER_YELLOW, UPPER_YELLOW),),
    # OpenCV 的 H 是 0..179；红色跨过色相首尾，必须合并两个区间。
    "red": (
        (np.array([0, 120, 80]), np.array([10, 255, 255])),
        (np.array([170, 120, 80]), np.array([179, 255, 255])),
    ),
}
CARD_RATIO_THRESHOLD = YELLOW_RATIO_THRESHOLD

# ===================== 技能是否就绪 =====================
S_THRESHOLD = 119
V_THRESHOLD = 115
READY_RATIO = 0.20

# ===================== 时序 =====================
CONFIRM_FRAMES = 1
SELECT_WINDOW = 1.2
LOOP_DELAY = 0.001
AFTER_TRIGGER_DELAY = 0.04
LOCK_COOLDOWN = 0.20
TARGET_FPS = 180
DISABLED_DELAY = 0.05

# ===================== 键位 =====================
CONFIRM_KEY = "w"    # 开始轮牌、认出目标牌后锁定
VK_RBUTTON = 0x02    # 自由移动的触发条件：按住鼠标右键

STATE_IDLE = 0
STATE_SELECTING = 1
STATE_LOCKED = 2

if hasattr(pydirectinput, "PAUSE"):
    pydirectinput.PAUSE = 0
if hasattr(pydirectinput, "FAILSAFE"):
    pydirectinput.FAILSAFE = False


def _noop(event_name, payload=None):
    """没有界面时的默认上报口。"""


def build_capture_region(*rois):
    left = min(roi[0] for roi in rois)
    top = min(roi[1] for roi in rois)
    right = max(roi[0] + roi[2] for roi in rois)
    bottom = max(roi[1] + roi[3] for roi in rois)
    return left, top, right, bottom


def to_local_roi(roi, capture_region):
    left, top, _, _ = capture_region
    x, y, w, h = roi
    return x - left, y - top, w, h


def crop_roi(frame_bgr, roi):
    x, y, w, h = roi
    return frame_bgr[y:y + h, x:x + w]


def bgr_roi_to_hsv(frame_bgr, roi):
    return cv2.cvtColor(crop_roi(frame_bgr, roi), cv2.COLOR_BGR2HSV)


def is_skill_ready(hsv_img):
    s = hsv_img[:, :, 1]
    v = hsv_img[:, :, 2]
    mask = (s > S_THRESHOLD) & (v > V_THRESHOLD)
    ratio = np.count_nonzero(mask) / mask.size

    h, w = hsv_img.shape[:2]
    center = hsv_img[h // 2, w // 2]
    center_ok = center[1] > S_THRESHOLD and center[2] > V_THRESHOLD

    return ratio > READY_RATIO and center_ok


def is_card_color(hsv_img, color):
    """目标色须同时覆盖足够面积且落在图像中心，避免背景误判。"""
    ranges = CARD_RANGES[color]
    mask = cv2.inRange(hsv_img, *ranges[0])
    for lower, upper in ranges[1:]:
        mask = cv2.bitwise_or(mask, cv2.inRange(hsv_img, lower, upper))
    ratio = cv2.countNonZero(mask) / mask.size

    h, w = hsv_img.shape[:2]
    center_ok = bool(mask[h // 2, w // 2])

    return ratio > CARD_RATIO_THRESHOLD and center_ok


def is_yellow_fast(hsv_img):
    """保留原接口，供现有黄牌回归测试使用。"""
    return is_card_color(hsv_img, "yellow")


def press_confirm():
    pydirectinput.press(CONFIRM_KEY)


CAPTURE_REGION = build_capture_region(ROI_CARD, ROI_SKILL)
ROI_CARD_LOCAL = to_local_roi(ROI_CARD, CAPTURE_REGION)
ROI_SKILL_LOCAL = to_local_roi(ROI_SKILL, CAPTURE_REGION)


class ScreenCapture:
    def __init__(self, region):
        self.region = region
        try:
            self.camera = dxcam.create(region=region, output_color="BGR")
            self.camera.start(region=region, target_fps=TARGET_FPS, video_mode=True)
        except Exception as exc:
            raise RuntimeError(f"截图初始化失败：{exc}") from exc

    def grab_bgr(self):
        return self.camera.get_latest_frame()

    def stop(self):
        if hasattr(self.camera, "stop"):
            self.camera.stop()


def capture_loop(enabled_event, stop_event, selection, capture_paused, notify=_noop):
    """每种牌各有触发键；本次选牌只锁定按键所对应的颜色。"""
    capture = None
    state = STATE_IDLE
    select_start_time = 0.0
    lock_until = 0.0
    match_count = 0
    target_card = None
    trigger_armed = True

    try:
        capture = ScreenCapture(CAPTURE_REGION)

        while not stop_event.is_set():
            if not enabled_event.is_set():
                state = STATE_IDLE
                match_count = 0
                trigger_armed = False
                time.sleep(DISABLED_DELAY)
                continue

            if capture_paused.is_set():
                state = STATE_IDLE
                match_count = 0
                trigger_armed = False
                time.sleep(DISABLED_DELAY)
                continue

            frame = capture.grab_bgr()
            if frame is None:
                time.sleep(LOOP_DELAY)
                continue

            now = time.perf_counter()

            pressed_colors = [
                color for color, key in selection.items() if input_keys.is_pressed(key)
            ]
            if not pressed_colors:
                trigger_armed = True
            elif len(pressed_colors) > 1:
                trigger_armed = False

            if state == STATE_IDLE and trigger_armed and len(pressed_colors) == 1:
                trigger_armed = False
                hsv_skill = bgr_roi_to_hsv(frame, ROI_SKILL_LOCAL)

                if not is_skill_ready(hsv_skill):
                    time.sleep(DISABLED_DELAY)
                    continue

                press_confirm()
                state = STATE_SELECTING
                target_card = pressed_colors[0]
                select_start_time = now
                match_count = 0
                time.sleep(AFTER_TRIGGER_DELAY)
                continue

            if state == STATE_SELECTING:
                if now - select_start_time > SELECT_WINDOW:
                    state = STATE_IDLE
                    match_count = 0
                else:
                    hsv_card = bgr_roi_to_hsv(frame, ROI_CARD_LOCAL)

                    if is_card_color(hsv_card, target_card):
                        match_count += 1
                    else:
                        match_count = 0

                    if match_count >= CONFIRM_FRAMES:
                        press_confirm()
                        state = STATE_LOCKED
                        lock_until = now + LOCK_COOLDOWN

            elif state == STATE_LOCKED and now >= lock_until:
                state = STATE_IDLE

            time.sleep(LOOP_DELAY)
    except Exception as exc:
        notify("error", str(exc))
        enabled_event.clear()
    finally:
        if capture is not None:
            capture.stop()


def auto_move_loop(move_enabled_event, stop_event, move, notify=_noop):
    """按住鼠标右键时，反复按下配置的键。

    move 形如 {"key": "n", "interval": 0.1}，interval 单位是秒；
    界面改了值会立刻生效，因为读的是同一个字典。
    """
    get_key_state = ctypes.windll.user32.GetAsyncKeyState

    while not stop_event.is_set():
        if not move_enabled_event.is_set():
            time.sleep(DISABLED_DELAY)
            continue

        if not get_key_state(VK_RBUTTON) & 0x8000:
            time.sleep(0.01)
            continue

        try:
            pydirectinput.press(move["key"])
        except Exception as exc:
            # 配置里手写了一个 pydirectinput 不认识的键名时，别让线程悄悄死掉
            notify("move_error", f"按键 {move['key']!r} 发送失败：{exc}")
            move_enabled_event.clear()
            continue

        time.sleep(move["interval"])
