"""生成 exe 图标 assets/mingding.ico

画的就是窗口左上角那个三牌扇面，改标记之后重跑一次即可：

    python tools/make_icon.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtGui import QGuiApplication  # noqa: E402

app = QGuiApplication(sys.argv[:1])

from widgets import card_fan_pixmap  # noqa: E402

SIZES = (16, 24, 32, 48, 64, 128, 256)
OUTPUT = ROOT / "assets" / "mingding.ico"


def main():
    from PIL import Image

    source = ROOT / "assets" / ".mingding-256.png"
    card_fan_pixmap(256).save(str(source))

    Image.open(source).save(OUTPUT, format="ICO", sizes=[(s, s) for s in SIZES])
    source.unlink()

    print(f"已生成 {OUTPUT.relative_to(ROOT)}  尺寸 {SIZES}")


if __name__ == "__main__":
    main()
