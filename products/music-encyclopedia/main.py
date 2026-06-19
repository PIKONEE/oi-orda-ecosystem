# -*- coding: utf-8 -*-
"""
Точка входа продукта «Интерактивная музыкальная энциклопедия»
(product_id=6, архетип A — WebView, движок webview2).

Весь продукт — контент в content/ + product.json + _secret.py.
Оболочку, активацию (v4 Ed25519), шифрование контента и сборку
(Windows + Android) даёт product-core.

Запуск в разработке:
    pip install -e <путь_к_product-core>
    python main.py

Сборка:
    python -m build <путь_к_этой_папке>
"""
from product_core.shell import run

if __name__ == "__main__":
    raise SystemExit(run(__file__))
