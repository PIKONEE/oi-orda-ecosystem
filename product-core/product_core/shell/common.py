# -*- coding: utf-8 -*-
"""
Общие помощники оболочки, НЕ зависящие от движка (Qt / WebView2).

Чтобы лёгкая webview2-оболочка не тянула за собой PySide6, всё общее живёт здесь.
"""

import os
import sys

# JS, отключающий выделение/копирование/контекстное меню (кроме полей ввода).
ANTI_COPY_JS = """
(function(){
  var s=document.createElement('style');
  s.textContent='*{-webkit-user-select:none!important;user-select:none!important;'
    +'-webkit-touch-callout:none!important;}::selection{background:transparent!important;}'
    +'input,textarea{-webkit-user-select:text!important;user-select:text!important;}';
  document.head.appendChild(s);
  ['copy','cut','dragstart'].forEach(function(ev){
    document.addEventListener(ev,function(e){e.preventDefault();},true);});
  document.addEventListener('contextmenu',function(e){e.preventDefault();},true);
  document.addEventListener('selectstart',function(e){
    var t=e.target.tagName; if(t==='INPUT'||t==='TEXTAREA')return; e.preventDefault();},true);
})();
"""

MIME = {
    ".html": "text/html", ".htm": "text/html", ".js": "application/javascript",
    ".mjs": "application/javascript", ".css": "text/css", ".json": "application/json",
    ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp",
    ".ico": "image/x-icon", ".woff": "font/woff", ".woff2": "font/woff2",
    ".ttf": "font/ttf", ".otf": "font/otf", ".mp3": "audio/mpeg", ".wav": "audio/wav",
    ".ogg": "audio/ogg", ".mp4": "video/mp4", ".webm": "video/webm",
    ".glb": "model/gltf-binary", ".gltf": "model/gltf+json", ".wasm": "application/wasm",
    ".txt": "text/plain", ".map": "application/json",
}


def mime_for(path: str) -> str:
    return MIME.get(os.path.splitext(path)[1].lower(), "application/octet-stream")


def base_dir(entry_file: str) -> str:
    """Папка с product.json/content. Работает для PyInstaller, Nuitka и dev."""
    if hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS                              # PyInstaller (onedir)
    if "__compiled__" in globals():
        return os.path.dirname(sys.executable)           # Nuitka (standalone)
    return os.path.dirname(os.path.abspath(entry_file))  # запуск из исходников


def load_embedded_secret(base: str):
    """Читает _secret.py рядом с продуктом. Возвращает dict {mode, ...} или None."""
    secret_path = os.path.join(base, "_secret.py")
    if not os.path.exists(secret_path):
        return None
    ns: dict = {}
    with open(secret_path, "r", encoding="utf-8") as f:
        exec(compile(f.read(), secret_path, "exec"), ns)
    if "PRODUCT_ID" not in ns:
        return None
    pid = int(ns["PRODUCT_ID"])
    if "get_public_key" in ns:   # v4 — только публичный ключ
        return {"mode": "v4", "product_id": pid, "public_key": ns["get_public_key"]()}
    if "get_secret" in ns:       # v3 (legacy, симметричный)
        return {"mode": "v3", "product_id": pid, "secret": ns["get_secret"]()}
    return None


def activation_html_path(base: str) -> str | None:
    """Путь к activation.html: рядом с модулем (dev/PyInstaller) или в дист-папке (Nuitka)."""
    for path in (
        os.path.join(os.path.dirname(__file__), "templates", "activation.html"),
        os.path.join(base, "product_core", "shell", "templates", "activation.html"),
    ):
        if os.path.exists(path):
            return path
    return None
