# -*- coding: utf-8 -*-
"""
Универсальная Windows-оболочка: тонкий лицензированный WebView-контейнер.

Защита (v4):
  - лицензия проверяется ПУБЛИЧНЫМ ключом Ed25519 (подделать нельзя);
  - контент отдаётся через собственную схему oilab://, расшифровывается в памяти
    (на диск/в бандл попадает только шифртекст);
  - экран активации, anti-copy, привязка к устройству — как раньше.

Логика продукта (навигация, словарь, 3D, карта) живёт в HTML/JS-контенте.

Использование из main.py продукта:
    from product_core.shell import run
    run(__file__)
"""

import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")


def _harden_runtime_env():
    """Запрещает удалённую отладку движка ДО его инициализации.

    Иначе на активированной машине достаточно выставить
    QTWEBENGINE_REMOTE_DEBUGGING и считать уже расшифрованный контент через
    DevTools. Снимаем эту возможность до импорта/старта QtWebEngine.
    """
    os.environ.pop("QTWEBENGINE_REMOTE_DEBUGGING", None)
    flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    if flags:
        kept = [tok for tok in flags.split()
                if "remote-debugging" not in tok and "remote-allow-origins" not in tok]
        if kept:
            os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join(kept)
        else:
            os.environ.pop("QTWEBENGINE_CHROMIUM_FLAGS", None)


_harden_runtime_env()  # ДО импорта PySide6/QtWebEngine

from PySide6.QtCore import QObject, Slot, QUrl, Qt, QTimer, QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import (
    QWebEngineSettings, QWebEngineProfile, QWebEngineUrlScheme,
    QWebEngineUrlSchemeHandler, QWebEngineUrlRequestJob,
)
from PySide6.QtWebEngineWidgets import QWebEngineView

from .. import config as config_mod
from .. import licensing
from .. import _protocol as proto
from ..device_id import get_device_id
from . import common

SCHEME = b"oilab"          # своя схема для защищённого контента
SCHEME_HOST = "app"        # oilab://app/index.html
_scheme_registered = False


def _register_scheme():
    """Регистрирует схему oilab:// — ОБЯЗАТЕЛЬНО до создания QApplication."""
    global _scheme_registered
    if _scheme_registered:
        return
    scheme = QWebEngineUrlScheme(SCHEME)
    scheme.setSyntax(QWebEngineUrlScheme.Syntax.Host)
    scheme.setFlags(
        QWebEngineUrlScheme.Flag.SecureScheme
        | QWebEngineUrlScheme.Flag.LocalAccessAllowed
        | QWebEngineUrlScheme.Flag.CorsEnabled
        | QWebEngineUrlScheme.Flag.ContentSecurityPolicyIgnored
    )
    QWebEngineUrlScheme.registerScheme(scheme)
    _scheme_registered = True


class ContentSchemeHandler(QWebEngineUrlSchemeHandler):
    """Отдаёт контент из content/, расшифровывая в памяти. На диск plaintext не пишет."""

    def __init__(self, content_dir: str, key_getter, is_unlocked):
        super().__init__()
        self._dir = os.path.realpath(content_dir)
        self._key_getter = key_getter   # callable -> bytes|None (ключ из лицензии)
        self._unlocked = is_unlocked    # callable -> bool

    def requestStarted(self, job: QWebEngineUrlRequestJob):
        try:
            if not self._unlocked():
                job.fail(QWebEngineUrlRequestJob.Error.RequestDenied)
                return
            rel = job.requestUrl().path().lstrip("/") or "index.html"
            full = os.path.realpath(os.path.join(self._dir, rel))
            # защита от выхода за пределы content/
            if not (full == self._dir or full.startswith(self._dir + os.sep)) \
                    or not os.path.isfile(full):
                job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
                return
            with open(full, "rb") as f:
                raw = f.read()
            if raw.startswith(proto.CONTENT_MAGIC):
                key = self._key_getter()
                if key is None:
                    job.fail(QWebEngineUrlRequestJob.Error.RequestDenied)
                    return
                data = proto.decrypt_content(raw, key)
            else:
                data = raw  # dev-режим: контент не зашифрован
            if data is None:
                logging.error("Не удалось расшифровать контент: %s", rel)
                job.fail(QWebEngineUrlRequestJob.Error.RequestFailed)
                return
            buf = QBuffer(job)
            buf.setData(QByteArray(data))
            buf.open(QIODevice.OpenModeFlag.ReadOnly)
            job.reply(QByteArray(common.mime_for(full).encode()), buf)
        except Exception:
            logging.exception("Ошибка обработчика контента")
            try:
                job.fail(QWebEngineUrlRequestJob.Error.RequestFailed)
            except Exception:
                pass


class CoreBridge(QObject):
    """JS-мост core.* — доступен на всех страницах продукта."""

    def __init__(self, window):
        super().__init__()
        self.window = window

    @Slot(result=str)
    def getDeviceId(self):
        return get_device_id()

    @Slot(result=str)
    def getStatus(self):
        return json.dumps(licensing.get_license_status(), ensure_ascii=False)

    @Slot(str)
    def activateKey(self, key):
        # v4 (подписанная лицензия) или v3 (legacy-ключ) — по тому, что встроено
        if licensing._PUBLIC_KEY is not None:
            ok, message = licensing.activate_license(key)
        else:
            ok, message = licensing.activate_key(key)
        esc = message.replace("\\", "\\\\").replace("'", "\\'")
        page = self.window.web_view.page()
        if ok:
            page.runJavaScript(
                f"if(typeof onActivationSuccess==='function')onActivationSuccess('{esc}');")
            QTimer.singleShot(1200, self.window.load_content)
        else:
            page.runJavaScript(
                f"if(typeof onActivationError==='function')onActivationError('{esc}');")

    @Slot(str)
    def log(self, msg):
        logging.info("[web] %s", msg)


class MainWindow(QMainWindow):
    def __init__(self, cfg: config_mod.ProductConfig, base_dir: str):
        super().__init__()
        self.cfg = cfg
        self.base_dir = base_dir
        self._unlocked = False

        self.setWindowTitle(cfg.window_title)
        if os.path.exists(cfg.icon):
            self.setWindowIcon(QIcon(cfg.icon))

        # обработчик защищённого контента: ключ берётся из активной лицензии
        self._handler = ContentSchemeHandler(
            cfg.content_dir, licensing.get_content_key,
            lambda: self._unlocked or cfg.skip_activation)
        QWebEngineProfile.defaultProfile().installUrlSchemeHandler(SCHEME, self._handler)

        self.web_view = QWebEngineView()
        self.setCentralWidget(self.web_view)

        settings = self.web_view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        if not cfg.anti_copy:
            settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, True)

        self.bridge = CoreBridge(self)
        self.channel = QWebChannel()
        self.channel.registerObject("core", self.bridge)
        self.web_view.page().setWebChannel(self.channel)
        self.web_view.loadFinished.connect(self._on_loaded)

        if cfg.fullscreen:
            self.showFullScreen()
        else:
            self.resize(1280, 800)
            self.show()

    def _on_loaded(self, ok):
        if ok and self.cfg.anti_copy:
            self.web_view.page().runJavaScript(common.ANTI_COPY_JS)

    def show_activation(self):
        path = common.activation_html_path(self.base_dir)
        if path:
            self.web_view.setUrl(QUrl.fromLocalFile(path))
        else:
            self.web_view.setHtml("<h1 style='font-family:sans-serif'>activation.html не найден</h1>")

    def load_content(self):
        self._unlocked = True  # с этого момента схема oilab отдаёт контент
        self.web_view.setUrl(QUrl(f"{SCHEME.decode()}://{SCHEME_HOST}/{self.cfg.entry_html}"))

    def start(self):
        if self.cfg.skip_activation or licensing.is_activated():
            self.load_content()
        else:
            self.show_activation()


def run(entry_file: str) -> int:
    """Точка входа продукта. entry_file — обычно __file__ из main.py."""
    base_dir = common.base_dir(entry_file)
    cfg = config_mod.load(base_dir)

    _register_scheme()  # ДО создания QApplication

    info = common.load_embedded_secret(base_dir)
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

    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication.instance() or QApplication(sys.argv)

    win = MainWindow(cfg, base_dir)
    win.start()
    return app.exec()
