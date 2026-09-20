# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

英雄联盟卡牌大师（TF）黄牌自动选牌辅助工具。通过屏幕截图 + HSV 颜色检测，在 W 技能选牌时自动识别并锁定黄牌。

## 架构

两个版本的主程序：
- `main.py` — 基于 mss 截图的基础版，命令行运行，按 E 触发
- `main_fast_dxcam.py` — 基于 dxcam 的高性能版（推荐），带 tkinter GUI、口令登录、F2 热键开关

核心流程（状态机）：
1. IDLE → 检测按键触发 + 技能是否就绪（HSV 饱和度/亮度判断）
2. SELECTING → 高速截图检测黄牌（HSV inRange），连续确认帧达标后锁定
3. LOCKED → 冷却后回到 IDLE

辅助工具：
- `PyAutoGUI 实时看鼠标坐标.py` — 获取屏幕坐标用于配置 ROI
- `实时 HSV 的可视化工具.py` — 分析截图 HSV 值，用于调阈值

## 运行与构建

```bash
# 直接运行（需管理员权限）
python main_fast_dxcam.py

# 打包为 exe
build_fast_dxcam.bat
# 输出: dist/kapai_fast_dxcam.exe
```

依赖：opencv-python, numpy, dxcam, keyboard, pydirectinput, pyautogui（仅坐标工具）

## 关键配置参数

ROI 坐标格式为 `(x, y, w, h)`，需根据分辨率调整。HSV 阈值（S_THRESHOLD, V_THRESHOLD, READY_RATIO, YELLOW_RATIO_THRESHOLD）需配合 `实时 HSV 的可视化工具.py` 标定。