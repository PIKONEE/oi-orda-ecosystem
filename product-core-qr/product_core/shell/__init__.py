# -*- coding: utf-8 -*-
"""
Оболочка продукта. Диспетчер движка:
  • "webview2" (по умолчанию) — системный Edge WebView2 (лёгкий, см. app_webview2.py)
  • "qt"                      — встроенный QtWebEngine (тяжёлый, запасной, app.py)

Движок задаётся в product.json: "engine": "webview2" | "qt".
Импорт движка — ленивый, чтобы webview2-сборка не тянула PySide6.
"""

from .. import config as config_mod
from . import common


def run(entry_file: str) -> int:
    base = common.base_dir(entry_file)
    cfg = config_mod.load(base)
    engine = (cfg.engine or "webview2").lower()
    if engine == "qt":
        from .app import run as _run
    else:
        from .app_webview2 import run as _run
    return _run(entry_file)
