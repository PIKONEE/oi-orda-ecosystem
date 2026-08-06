# -*- coding: utf-8 -*-
"""
product_core — централизованное ядро для образовательных продуктов.

Содержит:
  - licensing : валидация HMAC-ключей, активация, шифрование license.dat
  - keygen    : генерация ключей (только у разработчика)
  - device_id : кросс-платформенный отпечаток устройства
  - config    : загрузка product.json
  - shell.app : универсальная Windows-оболочка (PySide6 + QWebEngine)

Один формат ключа и одно шифрование используются на Windows и Android.
"""

__version__ = "1.0.0"
