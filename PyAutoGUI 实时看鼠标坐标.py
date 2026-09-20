import pyautogui
import time

print("把鼠标移动到目标位置，按 Ctrl+C 退出")

try:
    while True:
        x, y = pyautogui.position()
        print(f"\r坐标: ({x}, {y})", end="")
        time.sleep(0.1)
except KeyboardInterrupt:
    print("\n结束")

#854，996
#887，1030

#小地图
#1508，657
#1916,1074