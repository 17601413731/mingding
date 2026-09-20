import ctypes
import queue
import threading
import time
import tkinter as tk
import winsound

import cv2
import dxcam
import keyboard
import numpy as np
import pydirectinput

# Regions use (x, y, w, h).
ROI_CARD = (854, 996, 33, 34)
ROI_SKILL = (854, 996, 33, 34)

LOWER_YELLOW = np.array([15, 140, 150])
UPPER_YELLOW = np.array([35, 255, 255])

YELLOW_RATIO_THRESHOLD = 0.15
S_THRESHOLD = 119
V_THRESHOLD = 115
READY_RATIO = 0.20
CONFIRM_FRAMES = 1
SELECT_WINDOW = 1.2
LOOP_DELAY = 0.001
AFTER_TRIGGER_DELAY = 0.04
LOCK_COOLDOWN = 0.20
TARGET_FPS = 180
DISABLED_DELAY = 0.05
UI_POLL_MS = 100
AUTO_MOVE_INTERVAL = 0.10

STATE_IDLE = 0
STATE_SELECTING = 1
STATE_LOCKED = 2

if hasattr(pydirectinput, "PAUSE"):
    pydirectinput.PAUSE = 0
if hasattr(pydirectinput, "FAILSAFE"):
    pydirectinput.FAILSAFE = False


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


def is_yellow_fast(hsv_img):
    mask = cv2.inRange(hsv_img, LOWER_YELLOW, UPPER_YELLOW)
    ratio = cv2.countNonZero(mask) / mask.size

    h, w = hsv_img.shape[:2]
    center = hsv_img[h // 2, w // 2]
    center_ok = (
        LOWER_YELLOW[0] <= center[0] <= UPPER_YELLOW[0]
        and LOWER_YELLOW[1] <= center[1] <= UPPER_YELLOW[1]
        and LOWER_YELLOW[2] <= center[2] <= UPPER_YELLOW[2]
    )

    return ratio > YELLOW_RATIO_THRESHOLD and center_ok


def press_w():
    pydirectinput.press("w")


def play_toggle_sound(is_enabled):
    tones = [(880, 120), (1046, 120)] if is_enabled else [(660, 180)]
    for frequency, duration in tones:
        try:
            winsound.Beep(frequency, duration)
        except RuntimeError:
            winsound.MessageBeep()
            break


class ScreenCapture:
    def __init__(self, region):
        self.region = region
        self.backend = "dxcam"
        try:
            self.camera = dxcam.create(region=region, output_color="BGR")
            self.camera.start(region=region, target_fps=TARGET_FPS, video_mode=True)
        except Exception as exc:
            raise RuntimeError("dxcam init failed") from exc

    def grab_bgr(self):
        return self.camera.get_latest_frame()

    def stop(self):
        if hasattr(self.camera, "stop"):
            self.camera.stop()


CAPTURE_REGION = build_capture_region(ROI_CARD, ROI_SKILL)
ROI_CARD_LOCAL = to_local_roi(ROI_CARD, CAPTURE_REGION)
ROI_SKILL_LOCAL = to_local_roi(ROI_SKILL, CAPTURE_REGION)

def capture_loop(enabled_event, stop_event, ui_queue):
    capture = ScreenCapture(CAPTURE_REGION)
    state = STATE_IDLE
    select_start_time = 0.0
    lock_until = 0.0
    yellow_count = 0

    try:
        while not stop_event.is_set():
            if not enabled_event.is_set():
                state = STATE_IDLE
                yellow_count = 0
                time.sleep(DISABLED_DELAY)
                continue

            frame = capture.grab_bgr()
            if frame is None:
                time.sleep(LOOP_DELAY)
                continue

            now = time.perf_counter()

            if keyboard.is_pressed("e") and state == STATE_IDLE:
                hsv_skill = bgr_roi_to_hsv(frame, ROI_SKILL_LOCAL)

                if not is_skill_ready(hsv_skill):
                    time.sleep(DISABLED_DELAY)
                    continue

                press_w()
                state = STATE_SELECTING
                select_start_time = now
                yellow_count = 0
                time.sleep(AFTER_TRIGGER_DELAY)
                continue

            if state == STATE_SELECTING:
                if now - select_start_time > SELECT_WINDOW:
                    state = STATE_IDLE
                    yellow_count = 0
                else:
                    hsv_card = bgr_roi_to_hsv(frame, ROI_CARD_LOCAL)

                    if is_yellow_fast(hsv_card):
                        yellow_count += 1
                    else:
                        yellow_count = 0

                    if yellow_count >= CONFIRM_FRAMES:
                        press_w()
                        state = STATE_LOCKED
                        lock_until = now + LOCK_COOLDOWN

            elif state == STATE_LOCKED and now >= lock_until:
                state = STATE_IDLE

            time.sleep(LOOP_DELAY)
    except Exception as exc:
        ui_queue.put(("error", str(exc)))
    finally:
        capture.stop()


def auto_move_loop(move_enabled_event, stop_event, move_interval_ref):
    VK_RBUTTON = 0x02
    get_key_state = ctypes.windll.user32.GetAsyncKeyState
    while not stop_event.is_set():
        if not move_enabled_event.is_set():
            time.sleep(DISABLED_DELAY)
            continue
        if get_key_state(VK_RBUTTON) & 0x8000:
            pydirectinput.press("n")
            time.sleep(move_interval_ref[0])
        else:
            time.sleep(0.01)


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("管你这那里")
        self.root.geometry("320x250")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.ui_queue = queue.SimpleQueue()
        self.enabled_event = threading.Event()
        self.move_enabled_event = threading.Event()
        self.stop_event = threading.Event()
        self.worker_thread = None
        self.move_thread = None
        self.hotkey = None
        self.move_hotkey = None

        self.status_var = tk.StringVar(value="选牌关闭，按 F2 开启")
        self.move_status_var = tk.StringVar(value="自动移动关闭，按 F3 开启")
        self.move_interval_ref = [AUTO_MOVE_INTERVAL]

        self.desktop_frame = tk.Frame(self.root, padx=20, pady=20)
        self.build_desktop()

        self.start_worker()
        self.register_hotkey()
        self.desktop_frame.pack(fill="both", expand=True)
        self.root.after(UI_POLL_MS, self.process_ui_queue)

    def build_desktop(self):
        tk.Label(self.desktop_frame, text="管你这那里 已启动").pack(anchor="w")
        tk.Label(self.desktop_frame, textvariable=self.status_var, font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w", pady=(12, 4))
        tk.Label(self.desktop_frame, textvariable=self.move_status_var, font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w", pady=(4, 8))

        interval_frame = tk.Frame(self.desktop_frame)
        interval_frame.pack(anchor="w", pady=(0, 8))
        tk.Label(interval_frame, text="移动间隔(ms):").pack(side="left")
        self.interval_entry = tk.Entry(interval_frame, width=6)
        self.interval_entry.insert(0, str(int(AUTO_MOVE_INTERVAL * 1000)))
        self.interval_entry.pack(side="left", padx=(4, 4))
        tk.Button(interval_frame, text="应用", command=self.apply_interval).pack(side="left")

        tk.Label(self.desktop_frame, text="F2 选牌开关 | F3 自动移动开关").pack(anchor="w")
        tk.Button(self.desktop_frame, text="退出", command=self.close).pack(fill="x", pady=(20, 0))

    def start_worker(self):
        if self.worker_thread is not None:
            return

        self.worker_thread = threading.Thread(
            target=capture_loop,
            args=(self.enabled_event, self.stop_event, self.ui_queue),
            daemon=True,
        )
        self.worker_thread.start()

        self.move_thread = threading.Thread(
            target=auto_move_loop,
            args=(self.move_enabled_event, self.stop_event, self.move_interval_ref),
            daemon=True,
        )
        self.move_thread.start()

    def register_hotkey(self):
        if self.hotkey is not None:
            return

        self.hotkey = keyboard.add_hotkey("f2", self.toggle_enabled)
        self.move_hotkey = keyboard.add_hotkey("f3", self.toggle_move)

    def toggle_enabled(self):
        is_enabled = not self.enabled_event.is_set()
        if is_enabled:
            self.enabled_event.set()
        else:
            self.enabled_event.clear()
        self.ui_queue.put(("toggle", is_enabled))

    def toggle_move(self):
        is_enabled = not self.move_enabled_event.is_set()
        if is_enabled:
            self.move_enabled_event.set()
        else:
            self.move_enabled_event.clear()
        self.ui_queue.put(("toggle_move", is_enabled))

    def apply_interval(self):
        try:
            ms = int(self.interval_entry.get())
            if ms < 20:
                ms = 20
            self.move_interval_ref[0] = ms / 1000.0
        except ValueError:
            pass

    def process_ui_queue(self):
        while True:
            try:
                event_name, payload = self.ui_queue.get_nowait()
            except queue.Empty:
                break

            if event_name == "toggle":
                self.status_var.set("选牌开启" if payload else "选牌关闭，按 F2 开启")
                play_toggle_sound(payload)
            elif event_name == "toggle_move":
                self.move_status_var.set("自动移动开启" if payload else "自动移动关闭，按 F3 开启")
                play_toggle_sound(payload)
            elif event_name == "error":
                self.status_var.set(f"运行失败: {payload}")
                self.enabled_event.clear()

        if self.root.winfo_exists():
            self.root.after(UI_POLL_MS, self.process_ui_queue)

    def close(self):
        self.stop_event.set()
        if self.hotkey is not None:
            keyboard.remove_hotkey(self.hotkey)
            self.hotkey = None
        if self.move_hotkey is not None:
            keyboard.remove_hotkey(self.move_hotkey)
            self.move_hotkey = None
        if self.worker_thread is not None and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=1.0)
        if self.move_thread is not None and self.move_thread.is_alive():
            self.move_thread.join(timeout=1.0)
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
