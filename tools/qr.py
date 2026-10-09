# -*- coding: utf-8 -*-
"""
Генератор QR-кодов (ссылки, текст, ключи лицензий, Wi-Fi).

    python tools/qr.py "https://oi-orda.kz"                  → out/qr/oi-orda.kz.png
    python tools/qr.py "https://kaspi.kz/pay/..." -o kaspi   → out/qr/kaspi.png
    python tools/qr.py "OL1-..." -o license-school5 --svg    → out/qr/license-school5.svg
    python tools/qr.py --wifi "School-5" --password "12345678" -o wifi

Файлы складываются в out/qr/ (в .gitignore). Нужен пакет segno
(в облачной сессии его ставит .claude/hooks/session-start.sh; локально:
pip install segno).
"""

import argparse
import os
import re
import sys

try:
    import segno
    from segno import helpers as segno_helpers
except ImportError:
    sys.exit("Нужен пакет segno: pip install segno")

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(_ROOT, "out", "qr")


def _default_name(data: str) -> str:
    name = re.sub(r"^[a-z]+://", "", data.strip(), flags=re.I)
    name = re.sub(r"[^\w.-]+", "_", name).strip("._")
    return (name or "qr")[:60]


def main():
    ap = argparse.ArgumentParser(description="Сделать QR-код (PNG или SVG) в out/qr/")
    ap.add_argument("data", nargs="?", help="ссылка или текст для QR")
    ap.add_argument("-o", "--name", help="имя файла без расширения")
    ap.add_argument("--svg", action="store_true", help="SVG вместо PNG (для печати)")
    ap.add_argument("--scale", type=int, default=12, help="размер модуля в пикселях (PNG)")
    ap.add_argument("--wifi", metavar="SSID", help="QR для подключения к Wi-Fi")
    ap.add_argument("--password", default=None, help="пароль Wi-Fi")
    args = ap.parse_args()

    if args.wifi:
        qr = segno_helpers.make_wifi(ssid=args.wifi, password=args.password,
                                    security="WPA" if args.password else None)
        name = args.name or "wifi_" + _default_name(args.wifi)
    elif args.data:
        qr = segno.make(args.data, error="m", micro=False)
        name = args.name or _default_name(args.data)
    else:
        ap.error("укажите текст/ссылку или --wifi")

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, name + (".svg" if args.svg else ".png"))
    if args.svg:
        qr.save(path, scale=4, border=4)
    else:
        qr.save(path, scale=args.scale, border=4)
    print(path)


if __name__ == "__main__":
    main()
