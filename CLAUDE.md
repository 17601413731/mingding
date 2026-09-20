# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

英雄联盟卡牌大师（TF）黄牌自动选牌辅助工具「命定」。屏幕截图 + HSV 颜色检测，
在 W 技能选牌时自动识别并锁定黄牌；另有一个按住鼠标右键连发的自动移动。

## 架构

界面与引擎完全分离，两边只通过一个 Qt 信号通信（跨线程发信号 Qt 会自己排队）：

- `mingding.py` — 入口，解析参数、装配窗口
- `window.py` — 主窗口、系统托盘、全局热键、线程与引擎接线
- `widgets.py` — 自绘控件（三牌扇面、开关、角标、键位录制框）
- `theme.py` — 设计令牌与样式表
- `engine.py` — 截图采集、选牌状态机、自动移动线程。**不含任何界面代码**，
  上报事件只用一个 `notify(name, payload)` 回调
- `config.py` — `config.json` 的读写与校验

核心状态机（`engine.capture_loop`）：

1. `IDLE` → 检测触发键 + 技能是否就绪（HSV 饱和度/亮度判断）
2. `SELECTING` → 高速截图检测黄牌（HSV inRange），连续确认帧达标后锁定
3. `LOCKED` → 冷却后回到 `IDLE`

`legacy/` 下是重构前的两个旧版本，已被取代，不再维护，只作参考。

## 运行与构建

```bash
python mingding.py                # 直接运行（需管理员权限）
python mingding.py --ui-only      # 只开界面，不碰游戏、不注册热键
python -m unittest discover -s tests

build_mingding.bat                # 打包，输出 dist\mingding\mingding.exe（onedir）
```

依赖：PySide6, opencv-python, numpy, dxcam, keyboard, pydirectinput
（`tools/make_icon.py` 额外用到 pillow）

打包用的是 onedir 而不是 onefile——PySide6 单文件冷启动要好几秒。
`mingding.spec` 排掉了大量用不到的 Qt 模块，**改过排除列表必须实际跑一次 exe 验证**，
排错了不会打包失败而是运行时崩溃。

## 关键配置

用户可改的参数在 `config.json`（与 `mingding.exe` 同级）：热键、自动移动的按键与间隔。

代码里的常量都在 `engine.py` 顶部：

- `ROI_CARD` / `ROI_SKILL` — 屏幕区域，格式 `(x, y, w, h)`，换分辨率要重新量
- `LOWER_YELLOW` / `UPPER_YELLOW` / `YELLOW_RATIO_THRESHOLD` — 黄牌判定
- `S_THRESHOLD` / `V_THRESHOLD` / `READY_RATIO` — 技能是否就绪

标定用 `tools/mouse_pos.py`（量坐标）和 `tools/hsv_probe.py`（看 HSV 分布）。

## 改动检测逻辑时

`tests/test_detect.py` 用仓库里的真实截图钉死了检测结果（占比、中心像素、最终判定）。
动 `is_yellow_fast` / `is_skill_ready` / 阈值之后必须跑一遍：

```bash
python -m unittest discover -s tests
```
