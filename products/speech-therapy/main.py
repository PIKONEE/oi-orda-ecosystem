# -*- coding: utf-8 -*-
"""
Точка входа продукта «Кабинет логопеда — игры для речи»
(product_id=7, архетип A — WebView, для Android-планшета и Windows).

Весь продукт — контент в content/ + product.json + _secret.py.
Оболочку, активацию (v4 Ed25519), шифрование контента и сборку
(Windows + Android) даёт product-core.

Запуск в разработке:
    pip install -e <путь_к_product-core>
    python main.py
Сборка Android:
    python -m build . --android
"""
from product_core.shell import run

if __name__ == "__main__":
    raise SystemExit(run(__file__))
