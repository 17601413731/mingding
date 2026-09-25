"""命定 · 配置读写

配置保存在用户 AppData；首次运行会迁移旧版 exe 同目录的 config.json。
只负责读写与合法性校验，不认识任何界面。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import input_keys

DEFAULTS = {
    "hotkey_select": "f2",      # 选牌总开关热键
    "card_key_blue": "mouse_x2",  # 蓝牌默认鼠标侧键 2
    "card_key_yellow": "e",     # 保留原来的黄牌触发键
    "card_key_red": "mouse_x1",   # 红牌默认鼠标侧键 1
    "hotkey_move": "f3",        # 自由移动总开关热键
    "move_key": "n",            # 自由移动时反复按下的键
    "move_interval_ms": 100,    # 自由移动的连发间隔
}

CARD_COLORS = ("blue", "yellow", "red")
MOVE_INTERVAL_MIN_MS = 20
MOVE_INTERVAL_MAX_MS = 1000

_KEY_FIELDS = (
    "hotkey_select", "hotkey_move", "move_key",
    "card_key_blue", "card_key_yellow", "card_key_red",
)
_FALLBACK_KEYS = ("f6", "f7", "f8", "f9", "f10", "e", "z", "x", "c")


def config_path() -> Path:
    """放在用户可写的固定位置，更新或移动程序时不会丢失。"""
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    return base / "mingding" / "config.json"


def legacy_config_path() -> Path:
    """旧版配置位于 exe（或源码）旁边，仅用于首次迁移。"""
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

    # 兼容上一版“一个触发键 + 一个目标牌”：旧触发键分配给当时选中的牌。
    legacy_color = raw.get("target_card", "yellow")
    legacy_key = raw.get("select_trigger_key")
    legacy_field = None
    if isinstance(legacy_color, str) and legacy_color.lower() in CARD_COLORS:
        legacy_field = f"card_key_{legacy_color.lower()}"
    if (
        legacy_field and legacy_field not in raw
        and isinstance(legacy_key, str) and legacy_key.strip()
    ):
        cfg[legacy_field] = legacy_key.strip().lower()

    # 手工修改配置时也保持按键唯一；优先保留旧版正在使用的选牌键。
    card_fields = [f"card_key_{color}" for color in CARD_COLORS]
    if legacy_field and legacy_field not in raw and legacy_key:
        card_fields.remove(legacy_field)
        card_fields.insert(0, legacy_field)
    used = {"w", "mouse_right"}
    for field in ("hotkey_select", "hotkey_move", "move_key", *card_fields):
        if cfg[field] in used or (field == "move_key" and input_keys.is_mouse_key(cfg[field])):
            cfg[field] = next(
                candidate for candidate in (DEFAULTS[field], *_FALLBACK_KEYS)
                if candidate not in used
            )
        used.add(cfg[field])

    ms = raw.get("move_interval_ms")
    if isinstance(ms, (int, float)):
        cfg["move_interval_ms"] = max(
            MOVE_INTERVAL_MIN_MS, min(MOVE_INTERVAL_MAX_MS, int(ms))
        )

    return cfg


def load() -> dict:
    """优先读 AppData；没有时迁移旧版配置或创建默认配置。"""
    path = config_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        try:
            raw = json.loads(legacy_config_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raw = None
        cfg = _clean(raw)
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
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(
            json.dumps(_clean(cfg), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp, path)
    except OSError:
        return False
    return True
