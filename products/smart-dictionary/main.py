# -*- coding: utf-8 -*-
"""
Точка входа продукта «Умный словарь» (product_id=2, архетип A — WebView).

Весь продукт — это контент в content/ + product.json + _secret.py.
Оболочку, активацию, защиту и сборку (Windows + Android) даёт product-core.

Запуск в разработке:
    pip install -e <путь_к_product-core>
    python main.py

Сборка:
    python -m build <путь_к_этой_папке>
"""
from product_core.shell import run

if __name__ == "__main__":
    raise SystemExit(run(__file__))
