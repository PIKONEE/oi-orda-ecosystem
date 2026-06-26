# -*- coding: utf-8 -*-
"""
Математическая лаборатория — точка входа десктоп-приложения.

Запускает универсальную оболочку product-core: проверка лицензии, экран
активации, защита, загрузка content/index.html. Вся логика продукта — в content/.

Разработка:   pip install -e <путь_к_product-core>;  python main.py
Сборка:       python -m build .            (Windows + Android)
              python -m build . --windows  (только Windows)

ВАЖНО: активация работает только здесь (через оболочку). При открытии
content/index.html напрямую в браузере активации нет — это режим превью.
"""
from product_core.shell import run

if __name__ == "__main__":
    raise SystemExit(run(__file__))
