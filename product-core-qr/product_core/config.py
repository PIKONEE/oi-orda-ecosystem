# -*- coding: utf-8 -*-
"""
Загрузка и валидация product.json — единого описания продукта.

product.json — единственный файл, который меняется для нового продукта.
Описывает: id, имя, контент, варианты, поведение оболочки, сборку.
"""

import json
import os


class ProductConfig:
    """Обёртка над product.json с удобными аксессорами."""

    def __init__(self, data: dict, base_dir: str):
        self._d = data
        self.base_dir = base_dir

    # ── обязательные поля ──
    @property
    def product_id(self) -> int:
        return int(self._d["product_id"])

    @property
    def slug(self) -> str:
        return self._d["slug"]

    @property
    def name(self) -> str:
        return self._d.get("name", self.slug)

    @property
    def version(self) -> str:
        return self._d.get("version", "1.0.0")

    @property
    def publisher(self) -> str:
        return self._d.get("publisher", "DigiTouch")

    @property
    def android_namespace(self) -> str:
        return self._d.get("android_namespace", f"kz.digitouch.{self.slug}")

    @property
    def engine(self) -> str:
        """Движок Windows-оболочки: 'webview2' (по умолчанию) или 'qt'."""
        return self._d.get("engine", "webview2")

    # ── контент ──
    @property
    def content_dir(self) -> str:
        return os.path.join(self.base_dir, self._d.get("content_dir", "content"))

    @property
    def entry_html(self) -> str:
        return self._d.get("entry_html", "index.html")

    @property
    def icon(self) -> str:
        icon = self._d.get("icon", "assets/icon.svg")
        return os.path.join(self.base_dir, icon)

    # ── варианты (предметы/языки/категории) ──
    @property
    def variants(self) -> list:
        """[{id, slug, name}], может быть пустым для односоставного продукта."""
        return self._d.get("variants", [])

    def variant_by_id(self, variant_id: int) -> dict | None:
        for v in self.variants:
            if int(v.get("id", -1)) == variant_id:
                return v
        return None

    # ── окно / поведение ──
    @property
    def window(self) -> dict:
        return self._d.get("window", {})

    @property
    def window_title(self) -> str:
        return self.window.get("title") or self.name

    @property
    def fullscreen(self) -> bool:
        return bool(self.window.get("fullscreen", True))

    # ── безопасность ──
    @property
    def security(self) -> dict:
        return self._d.get("security", {})

    @property
    def anti_copy(self) -> bool:
        return bool(self.security.get("anti_copy", True))

    @property
    def flag_secure(self) -> bool:
        return bool(self.security.get("flag_secure", True))

    @property
    def skip_activation(self) -> bool:
        return bool(self.security.get("skip_activation", False))

    def raw(self) -> dict:
        return dict(self._d)


REQUIRED_FIELDS = ("product_id", "slug")


def load(path_or_dir: str) -> ProductConfig:
    """Загружает product.json из файла или из папки продукта."""
    if os.path.isdir(path_or_dir):
        path = os.path.join(path_or_dir, "product.json")
    else:
        path = path_or_dir
    if not os.path.exists(path):
        raise FileNotFoundError(f"product.json не найден: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    missing = [k for k in REQUIRED_FIELDS if k not in data]
    if missing:
        raise ValueError(f"В product.json нет обязательных полей: {missing}")
    return ProductConfig(data, base_dir=os.path.dirname(os.path.abspath(path)))
