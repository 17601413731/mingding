# -*- mode: python ; coding: utf-8 -*-
"""命定 · PyInstaller 打包配置（onedir）

用 onedir 而不是 onefile：PySide6 打成单文件后每次启动都要把上百 MB 解包到临时目录，
冷启动会拖到好几秒，对一个游戏辅助工具来说不能接受。onedir 启动约一秒。

排除项只排真正用不到的东西——这个程序只用到 QtCore/QtGui/QtWidgets。
排错的后果是运行时崩，改完请务必跑一次 dist\mingding\mingding.exe 验证。
"""

import os

a = Analysis(
    ['mingding.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['dxcam', 'keyboard', 'pydirectinput'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # PySide6 里用不到的模块
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebEngineQuick',
        'PySide6.QtQuick',
        'PySide6.QtQuickWidgets',
        'PySide6.QtQml',
        'PySide6.Qt3DCore',
        'PySide6.Qt3DRender',
        'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets',
        'PySide6.QtCharts',
        'PySide6.QtDataVisualization',
        'PySide6.QtPdf',
        'PySide6.QtPdfWidgets',
        'PySide6.QtDesigner',
        'PySide6.QtHelp',
        'PySide6.QtSql',
        'PySide6.QtTest',
        'PySide6.QtBluetooth',
        'PySide6.QtNfc',
        'PySide6.QtPositioning',
        'PySide6.QtSensors',
        'PySide6.QtSerialPort',
        'PySide6.QtWebSockets',
        'PySide6.QtWebChannel',
        'PySide6.QtSvg',
        'PySide6.QtSvgWidgets',
        'PySide6.QtOpenGL',
        'PySide6.QtOpenGLWidgets',
        # 这台机器上装了一堆重库，别被牵连进来
        'matplotlib',
        'scipy',
        'pandas',
        'torch',
        'torchvision',
        'transformers',
        'PIL',
        'tkinter',
        'IPython',
        'pytest',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# PySide6 的 hook 会把整套 Qt 拖进来，模块级 excludes 拦不住 DLL，这里按文件名再筛一遍。
# 这个程序只用 QtCore / QtGui / QtWidgets，下面这些一个都加载不到：
#   opengl32sw      Qt 的软件 OpenGL 兜底，光栅渲染的 Widgets 程序用不上（省 19.7MB）
#   Qt6Quick/Qml    只用 Widgets，不碰 QML（省 12.5MB）
#   Qt6Pdf          不显示 PDF（省 4.4MB）
#   Qt6Svg          图标全是 QPainter 现画的，没有 SVG
#   ffmpeg          cv2 的视频解码器，只做图像检测用不到（省 27.3MB）
#   .qm              Qt 自带对话框的翻译，界面文案都是我们自己的
SKIP_BINARIES = (
    'opengl32sw',
    'Qt6Quick',
    'Qt6Qml',
    'Qt6Pdf',
    'Qt6Svg',
    'Qt6VirtualKeyboard',
    'opencv_videoio_ffmpeg',
)

a.binaries = [
    entry
    for entry in a.binaries
    if not any(skip in os.path.basename(entry[0]) for skip in SKIP_BINARIES)
]
a.datas = [entry for entry in a.datas if not entry[0].endswith('.qm')]

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='mingding',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/mingding.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='mingding',
)
