# 命定

英雄联盟卡牌大师（TF）黄牌自动选牌辅助工具。

按 `E` 触发选牌，程序在 W 技能的三张牌里认出黄牌并自动按 `W` 锁定。
另带一个自动移动：按住鼠标右键时，反复按下你指定的键。

## 运行

需要 **管理员权限**——游戏是管理员权限运行时，非管理员的热键和模拟按键都不生效。

```bash
python mingding.py
```

直接跑源码需要：`PySide6`、`opencv-python`、`numpy`、`dxcam`、`keyboard`、`pydirectinput`。

调试界面时用这两个参数，它们不会碰游戏、也不会注册热键：

```bash
python mingding.py --ui-only                 # 只开界面
python mingding.py --screenshot out.png      # 渲染一张界面图后退出
```

## 热键

| 键 | 作用 |
|---|---|
| `F2` | 选牌总开关 |
| `F3` | 自动移动总开关 |
| `E` | 选牌时手动触发（技能未冷却时忽略） |

`F2` / `F3` 以及自动移动的按键都可以在界面上改：点功能牌左上角的角标，或点「按键」输入框，
然后按下你想用的键即可。录制期间全局热键会临时摘掉，所以把开关热键改成一个新键不会打架。

`E` 和 `W` 是选牌功能自己要用的键，不能被占用，选了会当场提示。

关掉窗口不会退出程序，只是收进系统托盘——游戏里靠热键照样能用。要真正退出请点「退出程序」，
或用托盘菜单里的「退出」。

## 配置

配置存在 `config.json`，位置和 `mingding.py`（打包后是 `mingding.exe`）同级。
文件不存在时自动生成，删掉它会恢复默认值。

```json
{
  "hotkey_select": "f2",
  "hotkey_move": "f3",
  "move_key": "n",
  "move_interval_ms": 100
}
```

界面上的每一次改动都会立刻写回这个文件并即时生效，没有「应用」按钮。
间隔的合法范围是 20 ~ 1000 毫秒，超出的值会被夹到边界。

> 打包后的 `config.json` 在 `dist\mingding\` 里。如果程序放在 `Program Files` 这类没有写权限的
> 目录，配置会写不进去，界面会明确提示，此时改动只在本次运行有效。

## 界面

深靛蓝黑底，两级金色：黄铜是常态，牌黄只留给品牌标记里那张黄牌。
左上角的三牌扇面就是这个工具干的事——从三张牌里认出黄牌。

配色、字号、圆角全部集中在 `theme.py`，改那一个文件就能改整体观感。

## 打包

```bash
build_mingding.bat
```

产物在 `dist\mingding\`，入口是 `dist\mingding\mingding.exe`。**整个目录一起拷贝**，
它不能像单文件那样只拷一个 exe。

用的是 onedir 而不是 onefile：PySide6 打成单文件后每次启动都要把上百 MB 解包到临时目录，
冷启动会拖到好几秒。`mingding.spec` 里排掉了所有用不到的 Qt 模块来压体积。

实测（本机，Python 3.13 + PySide6 6.11）：

| | |
|---|---|
| 总体积 | **175.7 MB**（179 个文件）。不排除的话是 247 MB |
| 冷启动 | **约 1.3 秒** |

体积的大头是躲不掉的依赖：`cv2.pyd` 71 MB、`numpy` 26 MB、Qt 本体（Core/Gui/Widgets）约 35 MB。
排掉的是 `opengl32sw.dll`（19.7 MB）、Qt6Quick/Qml（12.5 MB）、Qt6Pdf（4.4 MB）、
cv2 的 ffmpeg 视频解码器（27.3 MB）和 Qt 自带翻译（6.4 MB）——这个程序一个都加载不到。

> 如果还想再小，唯一的办法是把 `engine.py` 里那三个 cv2 调用（`cvtColor` / `inRange` /
> `countNonZero`）换成 numpy 实现，能直接省掉 98 MB。但那会动到检测核心，
> 必须靠 `tests/test_detect.py` 逐位对齐才敢改。

改过排除列表之后，一定要实际跑一次 `dist\mingding\mingding.exe` 验证——排错了不会打包失败，
而是运行时崩溃。

其它注意事项：

- 首次运行如果被杀毒软件拦截，需要加入白名单。
- 依赖当前机器支持 dxcam。换机器后如果界面报「截图初始化失败」，说明那台机器不适合 dxcam 方案，
  或者没给管理员权限。

## 检测标定

屏幕区域在 `engine.py` 顶部，格式是 `(x, y, w, h)`，换分辨率要重新量：

```python
ROI_CARD = (854, 996, 33, 34)     # 三张牌的位置
ROI_SKILL = (854, 996, 33, 34)    # 技能图标的位置
```

黄牌阈值同样在 `engine.py`：HSV 落在 `[15, 140, 150]` ~ `[35, 255, 255]`，且占比超过 15%
并且中心像素也在范围内才算数。技能是否就绪则是看「亮且有颜色」的像素占比。

用 `tools/mouse_pos.py` 量坐标，用 `tools/hsv_probe.py` 标阈值：

```bash
python tools/mouse_pos.py     # 把鼠标移到目标位置，看坐标
python tools/hsv_probe.py     # 读 assets/yellow_card.png 的 HSV 分布
```

`tools/hsv_probe.py` 默认读 `assets/yellow_card.png`，换图改脚本里的 `IMAGE` 一行。

### 回归样本（已固化为测试）

`tests/test_detect.py` 用仓库里现成的图钉死了检测行为，重构检测逻辑后必须仍然全过：

| 图 | 黄牌占比 | 中心像素 HSV | 判定 |
|---|---|---|---|
| `assets/yellow_card.png` | 0.532 | (29, 240, 232) | 黄牌 |
| `assets/red_card.png` | 0.000 | (0, 232, 178) | 不是 |
| `assets/blue_card.png` | 0.000 | (119, 68, 231) | 不是 |
| `assets/img.png` | 0.085 | (149, 119, 118) | 不是 |

```bash
python -m unittest discover -s tests
```

### 历史标定记录

早期用 `tools/hsv_probe.py` 记下的两组读数，保留备查（当时未记录分别取自哪张图）：

```
H范围 0~179    S范围 81~255    V范围 121~255
均值 H 89      S 214           V 180
建议 S_THRESHOLD ≈ 150   V_THRESHOLD ≈ 126
```

```
H范围 24~123   S范围 82~216    V范围 121~255
均值 H 113     S 162           V 177
建议 S_THRESHOLD ≈ 113   V_THRESHOLD ≈ 124
```

当前实际使用的是 `S_THRESHOLD = 119`、`V_THRESHOLD = 115`、`READY_RATIO = 0.20`。

## 目录结构

```
mingding.py     入口：命令行参数、装配窗口
window.py       主窗口、托盘、热键、引擎接线
widgets.py      自绘控件：三牌扇面、开关、角标、键位录制
theme.py        设计令牌与样式表
engine.py       截图采集、选牌状态机、自动移动线程（不含任何界面代码）
config.py       配置读写
tests/          回归测试
tools/          标定与打包用的小工具
assets/         标定素材与图标
legacy/         早期版本，保留备查
```

`legacy/main_fast_dxcam.py` 是重构前的 tkinter 版本，`legacy/main.py` 是更早的 mss 命令行版本，
两者都已被 `mingding.py` 取代，不再维护。

## 已知限制

- 自动移动只支持「按住鼠标右键连发」这一种触发方式，触发键固定在鼠标右键，只有按下的键和间隔可配。
- 屏幕区域和 HSV 阈值只能改代码，没有做进界面。
- 没有做多分辨率自适应，换分辨率需要重新标定 `ROI_*`。
