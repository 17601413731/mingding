"""命定 · 入口

用法：
    python mingding.py                      正常启动（需要管理员权限）
    python mingding.py --ui-only            只开界面，不起截图与热键
    python mingding.py --screenshot x.png   渲染一张界面图后退出

后两个参数是调界面用的，不会碰游戏、不会注册热键。
"""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication

import config
import theme
from window import MainWindow


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)

    ui_only = "--ui-only" in argv

    screenshot = None
    if "--screenshot" in argv:
        index = argv.index("--screenshot")
        if index + 1 < len(argv):
            screenshot = argv[index + 1]

    app = QApplication(argv[:1])
    app.setApplicationName("命定")
    app.setApplicationDisplayName("命定")
    # 关窗口只是收进托盘，别跟着退出
    app.setQuitOnLastWindowClosed(False)
    theme.apply(app)

    window = MainWindow(config.load(), ui_only=ui_only or screenshot is not None)

    if screenshot:
        # 用真实平台插件渲染才有系统字体（离屏插件渲染出来全是方块），
        # WA_DontShowOnScreen 保证它不会真的弹到你屏幕上。
        window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        window.show()

        def grab():
            window.grab().save(screenshot)
            app.quit()

        QTimer.singleShot(400, grab)
    else:
        window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
