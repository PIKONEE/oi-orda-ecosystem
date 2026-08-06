# -*- coding: utf-8 -*-
"""
Лёгкая Windows-оболочка на СИСТЕМНОМ движке (Edge WebView2 через pywebview).

Не бандлит Chromium → размер продукта в разы меньше (как APK на Android, где
используется системный WebView). Защита та же, что в Qt-оболочке:
  - лицензия проверяется публичным ключом Ed25519 (логика в licensing.py — без изменений);
  - контент отдаётся локальным сервером 127.0.0.1 (случайный порт + секретный токен),
    расшифровывается В ПАМЯТИ; на диск plaintext не пишется; без активной лицензии — отказ;
  - DevTools/контекстное меню выключены (pywebview debug=False).

Точка входа — та же: product_core.shell.run(__file__) (диспетчер в __init__.py).
"""

import logging
import os
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")

import webview

from .. import config as config_mod
from .. import licensing
from .. import _protocol as proto
from ..device_id import get_device_id
from . import common

# Шим: даёт контенту привычный window.core поверх моста pywebview.
# Ставится после загрузки страницы; если страница уже определила core — не трогаем.
_SHIM_JS = """
(function(){
  if(window.__coreShim) return; window.__coreShim=1;
  function api(){ return (window.pywebview && window.pywebview.api) || null; }
  if(!window.core){
    window.core = {
      getDeviceId:function(cb){var a=api();if(a)a.get_device_id().then(function(v){if(cb)cb(v);});},
      getStatus:function(cb){var a=api();if(a)a.get_status().then(function(v){if(cb)cb(JSON.stringify(v));});},
      activateKey:function(k){var a=api();if(a)a.activate(k).then(function(r){
        if(r&&r.ok){if(window.onActivationSuccess)onActivationSuccess(r.msg);}
        else{if(window.onActivationError)onActivationError((r&&r.msg)||'Ошибка');}});},
      log:function(m){var a=api();if(a){try{a.log(String(m));}catch(e){}}}
    };
  }
})();
"""


def _make_handler(content_dir, key_getter, is_unlocked, token):
    real_dir = os.path.realpath(content_dir)
    prefix = "/" + token + "/"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _deny(self, code=403):
            try:
                self.send_response(code)
                self.end_headers()
            except Exception:
                pass

        def do_GET(self):
            try:
                path = self.path.split("?", 1)[0].split("#", 1)[0]
                if not path.startswith(prefix):      # без токена — отказ
                    return self._deny(403)
                if not is_unlocked():                # без активной лицензии — отказ
                    return self._deny(403)
                rel = path[len(prefix):] or "index.html"
                full = os.path.realpath(os.path.join(real_dir, rel))
                if not (full == real_dir or full.startswith(real_dir + os.sep)) \
                        or not os.path.isfile(full):
                    return self._deny(404)
                with open(full, "rb") as f:
                    raw = f.read()
                if raw.startswith(proto.CONTENT_MAGIC):
                    key = key_getter()
                    if key is None:
                        return self._deny(403)
                    data = proto.decrypt_content(raw, key)
                else:
                    data = raw                       # dev-режим: не зашифровано
                if data is None:
                    return self._deny(500)
                self.send_response(200)
                self.send_header("Content-Type", common.mime_for(full))
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)
            except Exception:
                logging.exception("Ошибка сервера контента")
                self._deny(500)

    return Handler


class ContentServer:
    """Локальный сервер контента: 127.0.0.1, случайный порт + токен, расшифровка в памяти."""

    def __init__(self, content_dir, key_getter, is_unlocked):
        self.token = secrets.token_urlsafe(18)
        handler = _make_handler(content_dir, key_getter, is_unlocked, self.token)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def url(self, entry: str) -> str:
        return f"http://127.0.0.1:{self.port}/{self.token}/{entry}"


class Api:
    """JS-мост (pywebview js_api). Имена методов видны как window.pywebview.api.*."""

    def __init__(self, cfg):
        # ВАЖНО: внутренние ссылки — строго с префиксом "_". Иначе pywebview
        # включает публичные атрибуты в JS-мост и пытается сериализовать
        # self.window → window.native (нативная WinForms-форма) → её свойства
        # (AccessibilityObject, DataBindings, browser.webview …), которые
        # ссылаются сами на себя через .NET-перечисления (Empty/Never/A …) →
        # бесконечная рекурсия и подвисание процесса («Python не отвечает»).
        self._cfg = cfg
        self._window = None
        self._content_url = None
        self._unlocked = False

    # gate для сервера контента
    def unlocked(self) -> bool:
        return self._unlocked or self._cfg.skip_activation

    def get_device_id(self):
        return get_device_id()

    def get_status(self):
        return licensing.get_license_status()

    def log(self, msg):
        logging.info("[web] %s", msg)
        return True

    def activate(self, key):
        if licensing._PUBLIC_KEY is not None:
            ok, msg = licensing.activate_license(key)   # v4
        else:
            ok, msg = licensing.activate_key(key)        # v3 legacy
        if ok:
            self._unlocked = True
            threading.Timer(1.2, self._go_content).start()
        return {"ok": ok, "msg": msg}

    def _go_content(self):
        try:
            if self._window:
                self._window.load_url(self._content_url)
        except Exception:
            logging.exception("Ошибка перехода к контенту")


def run(entry_file: str) -> int:
    base = common.base_dir(entry_file)
    cfg = config_mod.load(base)

    info = common.load_embedded_secret(base)
    if info is None:
        if not cfg.skip_activation:
            raise RuntimeError(
                "Не найден _secret.py. Сгенерируйте: "
                f"python -m product_core.keygen embed {cfg.product_id} > _secret.py"
            )
    elif info["mode"] == "v4":
        licensing.configure_verify(info["public_key"], info["product_id"], app_name=cfg.slug)
    else:  # v3 legacy
        licensing.configure(info["secret"], info["product_id"], app_name=cfg.slug)

    api = Api(cfg)
    server = ContentServer(cfg.content_dir, licensing.get_content_key, api.unlocked)
    api._content_url = server.url(cfg.entry_html)

    if cfg.skip_activation or licensing.is_activated():
        api._unlocked = True
        initial = api._content_url
    else:
        initial = common.activation_html_path(base) or "data:text/html,activation.html not found"

    window = webview.create_window(
        cfg.window_title, url=initial, js_api=api,
        fullscreen=cfg.fullscreen, width=1280, height=800,
        text_select=not cfg.anti_copy,
    )
    api._window = window

    def on_loaded():
        try:
            window.evaluate_js(_SHIM_JS)
            if cfg.anti_copy:
                window.evaluate_js(common.ANTI_COPY_JS)
        except Exception:
            logging.exception("Ошибка инжекта JS")

    window.events.loaded += on_loaded

    # отдельное хранилище (localStorage и т.п. сохраняются между запусками)
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    storage = os.path.join(appdata, cfg.slug, "webview")
    try:
        os.makedirs(storage, exist_ok=True)
    except Exception:
        storage = None

    # debug=False → DevTools и контекстное меню выключены (замена «глушилке» отладки)
    webview.start(debug=False, private_mode=False, storage_path=storage)
    return 0
