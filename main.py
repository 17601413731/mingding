import cv2
import numpy as np
import pydirectinput
import time
import mss
import keyboard

# =====================
# 配置区域
# =====================

# 👉 选牌区域
ROI_CARD = (854, 996, 33, 34)

# 👉 技能图标区域（⚠️改成你的技能位置）
ROI_SKILL = (854, 996, 33, 34)

# 👉 黄牌HSV
LOWER_YELLOW = np.array([15, 140, 150])
UPPER_YELLOW = np.array([35, 255, 255])

YELLOW_RATIO_THRESHOLD = 0.15

CONFIRM_FRAMES = 9
SELECT_WINDOW = 1.5
LOOP_DELAY = 0.005

# 👉 技能检测参数（核心）
S_THRESHOLD = 119   # 饱和度（有颜色）
V_THRESHOLD = 115   # 亮度（亮）
READY_RATIO = 0.20  # 占比

# =====================
# 状态机
# =====================

STATE_IDLE = 0
STATE_SELECTING = 1
STATE_LOCKED = 2

state = STATE_IDLE
select_start_time = 0
yellow_count = 0

# =====================
# mss 初始化
# =====================

sct = mss.MSS()


def capture_hsv(roi):
    x, y, w, h = roi
    monitor = {"left": x, "top": y, "width": w, "height": h}

    img = np.array(sct.grab(monitor))
    img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    return hsv


# =====================
# ✅ 技能是否未冷却（最终版）
# =====================

def is_skill_ready(hsv_img):
    s = hsv_img[:, :, 1]
    v = hsv_img[:, :, 2]

    # 👉 只保留“亮 + 有颜色”的像素
    mask = (s > S_THRESHOLD) & (v > V_THRESHOLD)

    ratio = np.sum(mask) / mask.size

    # 👉 中心点加强判断（防误触）
    h, w = hsv_img.shape[:2]
    center = hsv_img[h // 2, w // 2]

    center_ok = (center[1] > S_THRESHOLD and center[2] > V_THRESHOLD)

    return ratio > READY_RATIO and center_ok


# =====================
# 黄牌检测
# =====================

def is_yellow_fast(hsv_img):
    mask = cv2.inRange(hsv_img, LOWER_YELLOW, UPPER_YELLOW)
    ratio = np.sum(mask > 0) / mask.size

    h, w = hsv_img.shape[:2]
    center = hsv_img[h // 2, w // 2]

    center_ok = (
        LOWER_YELLOW[0] <= center[0] <= UPPER_YELLOW[0] and
        LOWER_YELLOW[1] <= center[1] <= UPPER_YELLOW[1] and
        LOWER_YELLOW[2] <= center[2] <= UPPER_YELLOW[2]
    )

    return ratio > YELLOW_RATIO_THRESHOLD and center_ok


def press_w():
    pydirectinput.press('w')


# =====================
# 主循环
# =====================

print("脚本启动：按 E 触发（仅技能未冷却时）")

while True:

    # ---------- 手动触发 ----------
    if keyboard.is_pressed("e") and state == STATE_IDLE:

        hsv_skill = capture_hsv(ROI_SKILL)

        if not is_skill_ready(hsv_skill):
            print("技能冷却中，忽略")
            time.sleep(0.1)
            continue

        press_w()

        state = STATE_SELECTING
        select_start_time = time.time()
        yellow_count = 0

        print("开始选牌")

        time.sleep(0.15)

    # ---------- 选牌中 ----------
    if state == STATE_SELECTING:
        now = time.time()

        if now - select_start_time > SELECT_WINDOW:
            state = STATE_IDLE
            print("超时未锁定")
            continue

        hsv = capture_hsv(ROI_CARD)

        if is_yellow_fast(hsv):
            yellow_count += 1
        else:
            yellow_count = 0

        if yellow_count >= CONFIRM_FRAMES:
            press_w()

            state = STATE_LOCKED
            print("锁定黄牌")

            time.sleep(0.25)

    # ---------- 冷却 ----------
    elif state == STATE_LOCKED:
        time.sleep(0.4)
        state = STATE_IDLE

    time.sleep(LOOP_DELAY)
