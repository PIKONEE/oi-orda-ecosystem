# -*- coding: utf-8 -*-
"""
Точка входа продукта. Запускает универсальную оболочку product-core.

Для запуска в разработке:
    pip install -e <путь_к_product-core>
    python main.py

Для сборки:
    python -m build <путь_к_этой_папке>
"""
from product_core.shell import run

if __name__ == "__main__":
    raise SystemExit(run(__file__))
