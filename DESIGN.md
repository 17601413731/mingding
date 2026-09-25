---
version: alpha
name: "命定"
description: "面向游戏中快速设置的深靛蓝 PySide6 工具，三种牌色各有独立按键。"
colors:
  ink: "#0F1220"
  felt: "#171B2E"
  edge: "#272C46"
  brass: "#C9A227"
  card: "#F2C230"
  blue-card: "#8DB8FF"
  red-card: "#FF8F83"
  chalk: "#E9EAF2"
  ash: "#868CA6"
  error: "#DC5A3C"
typography:
  ui:
    fontFamily: "Microsoft YaHei UI"
  numerals:
    fontFamily: "Segoe UI"
rounded:
  card: "14px"
  control: "8px"
spacing:
  window-padding: "20px"
  card-gap: "12px"
  card-padding: "16px"
components:
  feature-card: {}
  key-field: {}
  card-key: {}
---

# 命定 Design System

## Overview

### Creative North Star

一张深色游戏桌上的三张牌：界面安静，牌色只用来辨认各牌的独立按键。

### Product context and register

- **Audience and job:** Windows 玩家在进入游戏前设置三张牌各自的按键、启停键和自由移动，运行时从托盘查看状态。
- **Locale and usage:** 简体中文、Windows 桌面；设置应快速读懂，不要求用户记住隐藏手势。
- **Register and signature:** 实用工具；三牌扇面是唯一装饰性标记。
- **Restraint:** 不把整张功能卡染成蓝、黄、红；每种牌色始终配文字标签。
- **Token ownership:** `theme.py` 是运行时唯一令牌来源，本文件镜像其语义和数值。改全局令牌时同时更新两处；`window.py` 和 `widgets.py` 只引用 `theme.py` 常量。

## Colors

`INK` 是窗口背景，`FELT` 是功能卡，`EDGE` 是边界。`BRASS` 表示常态开启与焦点；`CARD`、`BLUE_CARD`、`RED_CARD` 只标记三张牌对应的按键，错误始终使用 `EMBER`。牌名必须用文字显示。

## Typography

中文界面用 Microsoft YaHei UI；快捷键和毫秒数用 Segoe UI 的等宽数字特性。字号由 `theme.py` 控制，说明文字保持可换行。

## Layout

窗口按内容定高，宽度由 `window.py` 的 `WINDOW_WIDTH` 控制。两张功能卡分别容纳选牌和自由移动；卡内按“状态、功能说明、设置”顺序阅读。错误横幅出现时重新计算窗口高度，不遮挡设置。

## Elevation & Depth

使用底色、卡面和细边框建立层级，不用阴影或模糊。托盘菜单沿用同一深色表面。

## Shapes

功能卡圆角 14px，输入与按钮圆角 8px。三牌扇面保留几何绘制，不引入外部图标素材。

## Components

### Foundational visual states

开关同时显示位置与“已开启/已关闭”文字；错误显示具体修正方法。键盘焦点必须可见，牌色选择不能只靠颜色识别。

### Buttons and actions

蓝、黄、红牌各有独立按键录制框，支持键盘和鼠标左键、中键、侧键。启停键也可录入鼠标键；鼠标右键保留给自由移动。录制时显示“按键或鼠标…”，Esc 取消并恢复原值。

### Forms and overlays

按键与间隔修改即时生效并写入配置。自由移动说明实时显示需要在游戏内绑定的按键；保存失败时展示内联错误。

### Motion

只保留开关滑块的短动画；避免持续闪烁或干扰游戏操作的装饰动效。

## Do's and Don'ts

- **Do:** 将“启停键”“每张牌自己的按键”“游戏技能键 W”明确区分。
- **Do:** 文案解释游戏内按键设置步骤与自由移动的用途。
- **Don't:** 以牌色代替文字说明或用错误色表示红牌。
