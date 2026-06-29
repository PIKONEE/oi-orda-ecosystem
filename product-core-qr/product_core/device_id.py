# -*- coding: utf-8 -*-
"""
Кросс-платформенный отпечаток устройства (device fingerprint).

Возвращает стабильный 16-символьный hex-ID, привязанный к железу.
Используется для привязки лицензии: ключ валиден ТОЛЬКО на устройстве,
для которого был сгенерирован.

Соответствует Android-реализации (Licensing.kt → getDeviceId):
    SHA256(raw)[:16].upper()
"""

import hashlib
import platform
import subprocess


def get_device_id() -> str:
    """Уникальный стабильный ID устройства (16 hex-символов, в верхнем регистре)."""
    system = platform.system()
    raw = ""

    try:
        if system == "Windows":
            output = subprocess.check_output(
                "wmic csproduct get uuid", shell=True, stderr=subprocess.DEVNULL
            ).decode(errors="ignore").strip()
            lines = [l.strip() for l in output.splitlines() if l.strip()]
            if len(lines) >= 2:
                raw = lines[1]
        elif system == "Darwin":
            output = subprocess.check_output(
                "ioreg -d2 -c IOPlatformExpertDevice | awk -F\\\" "
                "'/IOPlatformUUID/{print $(NF-1)}'",
                shell=True, stderr=subprocess.DEVNULL
            ).decode(errors="ignore").strip()
            raw = output
        elif system == "Linux":
            # Android тоже Linux — пробуем getprop (на десктопе его нет)
            try:
                raw = subprocess.check_output(
                    "getprop ro.serialno", shell=True, stderr=subprocess.DEVNULL
                ).decode(errors="ignore").strip()
            except Exception:
                pass
            if not raw:
                for path in ("/var/lib/dbus/machine-id", "/etc/machine-id"):
                    try:
                        with open(path) as f:
                            raw = f.read().strip()
                        if raw:
                            break
                    except Exception:
                        continue
    except Exception:
        pass

    if not raw:
        raw = f"fallback-{platform.node()}-{platform.machine()}"

    return hashlib.sha256(raw.encode()).hexdigest()[:16].upper()
