"""命定 · 配置读写

配置存在 exe（或源码目录）同级的 config.json，删掉它会自动重建为默认值。
只负责读写与合法性校验，不认识任何界面。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

DEFAULTS = {
    "hotkey_select": "f2",      # 选牌总开关热键
    "hotkey_move": "f3",        # 自动移动总开关热键
    "move_key": "n",            # 自动移动时反复按下的键
    "move_interval_ms": 100,    # 自动移动的连发间隔
}

MOVE_INTERVAL_MIN_MS = 20
MOVE_INTERVAL_MAX_MS = 1000

_KEY_FIELDS = ("hotkey_select", "hotkey_move", "move_key")


def config_path() -> Path:
    """打包后放在 exe 旁边，开发时放在源码目录。"""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent
    return base / "config.json"


def _clean(raw: object) -> dict:
    """把任意内容收敛成一份合法配置，缺什么补什么。"""
    cfg = dict(DEFAULTS)
    if not isinstance(raw, dict):
        return cfg

    for name in _KEY_FIELDS:
        value = raw.get(name)
        if isinstance(value, str) and value.strip():
            cfg[name] = value.strip().lower()

    ms = raw.get("move_interval_ms")
    if isinstance(ms, (int, float)):
        cfg["move_interval_ms"] = max(
            MOVE_INTERVAL_MIN_MS, min(MOVE_INTERVAL_MAX_MS, int(ms))
        )

    return cfg


def load() -> dict:
    """读配置；文件不存在时顺手写出默认配置，方便用户直接编辑。"""
    path = config_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        cfg = dict(DEFAULTS)
        save(cfg)
        return cfg
    except (OSError, ValueError):
        return dict(DEFAULTS)
    return _clean(raw)


def save(cfg: dict) -> bool:
    """原子写入，避免中途失败留下半个文件。写不进去时返回 False。"""
    path = config_path()
    tmp = path.with_suffix(".json.tmp")
    try:
        tmp.write_text(
            json.dumps(_clean(cfg), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp, path)
    except OSError:
        return False
    return True
