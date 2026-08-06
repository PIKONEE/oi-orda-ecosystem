# -*- coding: utf-8 -*-
"""
Лицензирование на стороне приложения (Windows / desktop).

Встраивается в сборку. Проверяет HMAC-подпись ключа с привязкой к device_id,
активирует с шифрованием license.dat, контролирует срок и откат часов.

Перед использованием вызовите configure(...) — обычно это делает shell.app.
Секрет конкретного продукта генерируется командой:
    python -m product_core.keygen embed <product_id>
"""

import hashlib
import json
import os
import sys
from datetime import datetime, timedelta

from . import _protocol as proto
from .device_id import get_device_id

# ─── Конфигурация продукта (устанавливается через configure*) ───
_PRODUCT_SECRET: bytes | None = None      # v3 (legacy, симметричный)
_PUBLIC_KEY: bytes | None = None          # v4 (Ed25519, проверка лицензий)
_CONTENT_KEY: bytes | None = None         # v4: ключ контента из активной лицензии
_PRODUCT_ID: int | None = None
_APP_NAME: str = "ProductCore"

_MAX_CLOCK_DRIFT_HOURS = 24
_LICENSE_VERSION = 4


def configure(product_secret: bytes, product_id: int, app_name: str = "ProductCore") -> None:
    """Настраивает модуль под конкретный продукт. Вызывается один раз при старте."""
    global _PRODUCT_SECRET, _PRODUCT_ID, _APP_NAME
    _PRODUCT_SECRET = product_secret
    _PRODUCT_ID = product_id
    _APP_NAME = app_name


def configure_obfuscated(mask: list[int], kdata: list[int], product_id: int,
                         app_name: str = "ProductCore") -> None:
    """Удобный вариант configure (v3): принимает обфусцированный секрет."""
    secret = bytes((a ^ b) & 0xFF for a, b in zip(mask, kdata))
    configure(secret, product_id, app_name)


def configure_verify(public_key: bytes, product_id: int,
                     app_name: str = "ProductCore") -> None:
    """v4: настраивает проверку лицензий по ПУБЛИЧНОМУ ключу Ed25519."""
    global _PUBLIC_KEY, _PRODUCT_ID, _APP_NAME
    _PUBLIC_KEY = public_key
    _PRODUCT_ID = product_id
    _APP_NAME = app_name


def _ensure_configured() -> None:
    if _PRODUCT_ID is None or (_PRODUCT_SECRET is None and _PUBLIC_KEY is None):
        raise RuntimeError(
            "licensing не сконфигурирован. Вызовите licensing.configure_verify(...) "
            "или используйте product_core.shell.app.run(...)."
        )


# ─── Путь к license.dat в пользовательском профиле ───

def _user_data_dir() -> str:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    d = os.path.join(base, _APP_NAME)
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def _license_file() -> str:
    return os.path.join(_user_data_dir(), "license.dat")


# ─── Валидация ключа ───

def validate_key(key_str: str) -> tuple:
    """(True, data) или (False, error_message). Ключ привязан к этому устройству."""
    _ensure_configured()
    decoded = proto.decode_key(key_str)
    if decoded is None:
        return False, "Неверный формат ключа"
    payload, sig = decoded
    device_id = get_device_id()
    if not proto.verify(_PRODUCT_SECRET, payload, sig, device_id):
        return False, "Ключ не подходит для этого устройства"
    data = proto.unpack_payload(payload)
    if data["product_id"] != _PRODUCT_ID:
        return False, "Ключ от другого продукта"
    return True, data


# ─── Активация ───

def activate_key(key_str: str) -> tuple:
    """Активирует ключ. Срок отсчитывается с момента активации."""
    _ensure_configured()
    valid, result = validate_key(key_str)
    if not valid:
        return False, result

    device_id = get_device_id()
    now = datetime.now()
    duration = result["duration_months"]
    expires = now + timedelta(days=duration * 30)

    license_data = {
        "key_hash": hashlib.sha256(key_str.upper().encode()).hexdigest(),
        "device_id": device_id,
        "product_id": result["product_id"],
        "variant_id": result["variant_id"],
        "client_id": result["client_id"],
        "duration_months": duration,
        "activated_at": now.isoformat(timespec="seconds"),
        "expires_at": expires.isoformat(timespec="seconds"),
        "last_check": now.isoformat(timespec="seconds"),
        "version": _LICENSE_VERSION,
    }
    try:
        plaintext = json.dumps(license_data, ensure_ascii=False).encode("utf-8")
        with open(_license_file(), "wb") as f:
            f.write(proto.encrypt(plaintext, device_id))
    except Exception as e:
        return False, f"Ошибка сохранения лицензии: {e}"

    return True, f"Активация успешна! Лицензия действительна {duration} {_months_word(duration)}."


# ─── v4: активация по подписанной лицензии (Ed25519) ───

def validate_license(license_str: str) -> tuple:
    """(True, data) или (False, error). Проверка ПУБЛИЧНЫМ ключом, привязка к устройству."""
    _ensure_configured()
    if _PUBLIC_KEY is None:
        return False, "Продукт собран без публичного ключа"
    decoded = proto.decode_license(license_str)
    if decoded is None:
        return False, "Неверный формат лицензии"
    payload, content_key, sig = decoded
    device_id = get_device_id()
    if not proto.verify_license(_PUBLIC_KEY, payload, content_key, sig, device_id):
        return False, "Лицензия не подходит для этого устройства"
    data = proto.unpack_payload(payload)
    if data["product_id"] != _PRODUCT_ID:
        return False, "Лицензия от другого продукта"
    data["content_key"] = content_key.hex()
    return True, data


def activate_license(license_str: str) -> tuple:
    """Активирует подписанную лицензию. Срок отсчитывается с момента активации."""
    global _CONTENT_KEY
    valid, result = validate_license(license_str)
    if not valid:
        return False, result

    device_id = get_device_id()
    now = datetime.now()
    duration = result["duration_months"]
    expires = now + timedelta(days=duration * 30)

    license_data = {
        "key_hash": hashlib.sha256(license_str.strip().encode()).hexdigest(),
        "device_id": device_id,
        "product_id": result["product_id"],
        "variant_id": result["variant_id"],
        "client_id": result["client_id"],
        "duration_months": duration,
        "content_key": result["content_key"],   # ключ контента из лицензии
        "activated_at": now.isoformat(timespec="seconds"),
        "expires_at": expires.isoformat(timespec="seconds"),
        "last_check": now.isoformat(timespec="seconds"),
        "version": _LICENSE_VERSION,
    }
    _CONTENT_KEY = bytes.fromhex(result["content_key"])
    try:
        plaintext = json.dumps(license_data, ensure_ascii=False).encode("utf-8")
        with open(_license_file(), "wb") as f:
            f.write(proto.encrypt(plaintext, device_id))
    except Exception as e:
        return False, f"Ошибка сохранения лицензии: {e}"

    return True, f"Активация успешна! Лицензия действительна {duration} {_months_word(duration)}."


# ─── Проверка статуса ───

def get_license_status() -> dict:
    _ensure_configured()
    result = {"valid": False, "reason": "Лицензия не найдена",
              "variant_id": None, "expires_at": None, "days_left": None}

    path = _license_file()
    if not os.path.exists(path):
        return result
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except Exception:
        result["reason"] = "Ошибка чтения файла лицензии"
        return result

    device_id = get_device_id()
    decrypted = proto.decrypt(raw, device_id)
    if decrypted is None:
        result["reason"] = "Лицензия повреждена или принадлежит другому устройству"
        return result
    try:
        data = json.loads(decrypted.decode("utf-8"))
    except Exception:
        result["reason"] = "Повреждены данные лицензии"
        return result

    if data.get("version") != _LICENSE_VERSION:
        result["reason"] = "Устаревший формат лицензии"
        return result
    if data.get("device_id") != device_id:
        result["reason"] = "Лицензия привязана к другому устройству"
        return result
    if data.get("product_id") != _PRODUCT_ID:
        result["reason"] = "Лицензия от другого продукта"
        return result

    now = datetime.now()
    try:
        last_check = datetime.fromisoformat(data["last_check"])
        if (last_check - now).total_seconds() > _MAX_CLOCK_DRIFT_HOURS * 3600:
            result["reason"] = "Обнаружено изменение системных часов. Обратитесь в поддержку."
            return result
    except Exception:
        pass

    try:
        expires_at = datetime.fromisoformat(data["expires_at"])
    except Exception:
        result["reason"] = "Повреждены данные лицензии"
        return result

    if now > expires_at:
        result["reason"] = "Срок действия лицензии истёк"
        result["expires_at"] = data["expires_at"]
        return result

    # обновляем last_check
    try:
        data["last_check"] = now.isoformat(timespec="seconds")
        plaintext = json.dumps(data, ensure_ascii=False).encode("utf-8")
        with open(path, "wb") as f:
            f.write(proto.encrypt(plaintext, device_id))
    except Exception:
        pass

    global _CONTENT_KEY
    ck = data.get("content_key")
    if ck:
        try:
            _CONTENT_KEY = bytes.fromhex(ck)
        except Exception:
            pass

    result.update({
        "valid": True, "reason": "OK",
        "variant_id": data.get("variant_id"),
        "expires_at": data["expires_at"],
        "days_left": (expires_at - now).days,
    })
    return result


def get_content_key() -> bytes | None:
    """Ключ расшифровки контента из активной лицензии (None, если не активировано)."""
    return _CONTENT_KEY


def is_activated() -> bool:
    return get_license_status()["valid"]


def get_activated_variant() -> int | None:
    s = get_license_status()
    return s["variant_id"] if s["valid"] else None


def _months_word(n: int) -> str:
    if 11 <= n % 100 <= 19:
        return "месяцев"
    r = n % 10
    if r == 1:
        return "месяц"
    if 2 <= r <= 4:
        return "месяца"
    return "месяцев"
