import cv2
import numpy as np

img = cv2.imread("yellow_card.png")
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

# =====================
# ✅ 关键：过滤“无效像素”
# =====================

# 只保留：亮 + 有颜色（避免背景干扰）
mask = (hsv[:, :, 1] > 80) & (hsv[:, :, 2] > 120)

pixels = hsv[mask]

h_vals = pixels[:, 0]
s_vals = pixels[:, 1]
v_vals = pixels[:, 2]

# =====================
# ✅ 输出更有用的数据
# =====================

print("====== 精准统计（建议用这个）======")
print("H范围:", np.min(h_vals), "~", np.max(h_vals))
print("S范围:", np.min(s_vals), "~", np.max(s_vals))
print("V范围:", np.min(v_vals), "~", np.max(v_vals))

print("\n====== 均值（更重要）======")
print("H均值:", int(np.mean(h_vals)))
print("S均值:", int(np.mean(s_vals)))
print("V均值:", int(np.mean(v_vals)))

print("\n====== 建议阈值 ======")

S_threshold = int(np.mean(s_vals) * 0.7)
V_threshold = int(np.mean(v_vals) * 0.7)

print("S_THRESHOLD ≈", S_threshold)
print("V_THRESHOLD ≈", V_threshold)