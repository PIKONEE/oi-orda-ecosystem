# -*- coding: utf-8 -*-
"""Генератор коротких ключей (LEGACY-20) — XXXX-XXXX-XXXX-XXXX-XXXX.

Запасная схема активации: ключ вводится с клавиатуры, QR не нужен.
Секрет подписи выводится из мастер-ключа экосистемы ровно так же, как это
делает сборщик (build/android.py -> _legacy_secret), поэтому ключи подходят
к собранным APK без обмена файлами.

Использование:
    python keygen_legacy20.py gen --product 3 --device A3F2B1C8E4D71029 --client 42 --months 12
    python keygen_legacy20.py gen --product 9 --variant 1 --device A3F2B1C8E4D71029 --client 7
    python keygen_legacy20.py check --product 3 --device A3F2B1C8E4D71029 --key XXXX-XXXX-XXXX-XXXX-XXXX

Мастер-ключ берётся из OI_CONTENT_MASTER или из ecosystem.keys рядом с ядром.
"""
import argparse
import base64
import hashlib
import hmac
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# Продукты и их варианты (0 = «все предметы»)
PRODUCTS = {
    2: ("Smart Dictionary", {0: "все"}),
    3: ("3D Models", {0: "все"}),
    4: ("Historic Map", {0: "все"}),
    5: ("Interactive Math", {0: "все"}),
    6: ("Music Vision", {0: "все"}),
    7: ("Logo Games", {0: "все"}),
    9: ("Virtual Stands", {0: "все предметы", 1: "биология", 2: "химия", 3: "физика"}),
}


def load_master() -> bytes:
    env = os.environ.get("OI_CONTENT_MASTER", "").strip()
    if env:
        return bytes.fromhex(env)
    for p in (os.path.join(HERE, "ecosystem.keys"),
              os.path.join(os.path.dirname(HERE), "product-core", "ecosystem.keys")):
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                return bytes.fromhex(json.load(f)["content_master"].strip())
    sys.exit("❌ Мастер-ключ не найден: задайте OI_CONTENT_MASTER или положите ecosystem.keys.")


def secret_for(product_id: int) -> bytes:
    """Тот же вывод, что и _legacy_secret() в build/android.py."""
    return hmac.new(load_master(), f"legacy20:{product_id}".encode(), hashlib.sha256).digest()


def encode_key(secret: bytes, variant_id: int, client_id: int, months: int,
               device_id: str, flags: int = 0) -> str:
    val = ((variant_id & 0xF) << 28) | ((client_id & 0xFFFF) << 12) | \
          ((months & 0xFF) << 4) | (flags & 0xF)
    payload = struct.pack(">I", val)
    sig = hmac.new(secret, payload + device_id.upper().encode(), hashlib.sha256).digest()[:8]
    enc = base64.b32encode(payload + sig).decode().rstrip("=")
    return "-".join(enc[i:i + 4] for i in range(0, 20, 4))


def decode_key(secret: bytes, key: str, device_id: str):
    clean = key.replace("-", "").replace(" ", "").upper()
    if len(clean) != 20:
        return None, "ключ должен быть из 20 символов"
    try:
        raw = base64.b32decode(clean + "====")
    except Exception:
        return None, "недопустимые символы в ключе"
    if len(raw) != 12:
        return None, "неверный размер"
    payload, sig = raw[:4], raw[4:]
    expect = hmac.new(secret, payload + device_id.upper().encode(), hashlib.sha256).digest()[:8]
    if not hmac.compare_digest(sig, expect):
        return None, "ключ не подходит для этого устройства"
    val = struct.unpack(">I", payload)[0]
    return {
        "variant_id": (val >> 28) & 0xF,
        "client_id": (val >> 12) & 0xFFFF,
        "months": (val >> 4) & 0xFF,
        "flags": val & 0xF,
    }, ""


def main():
    ap = argparse.ArgumentParser(description="Короткие ключи активации (LEGACY-20)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("gen", help="сгенерировать ключ")
    g.add_argument("--product", type=int, required=True, help="product_id (см. список ниже)")
    g.add_argument("--variant", type=int, default=0, help="вариант/предмет, 0 = все")
    g.add_argument("--device", required=True, help="Device ID доски (16 símв. с экрана активации)")
    g.add_argument("--client", type=int, default=0, help="номер клиента 0-65535")
    g.add_argument("--months", type=int, default=12, help="срок в месяцах 1-255")

    c = sub.add_parser("check", help="проверить ключ")
    c.add_argument("--product", type=int, required=True)
    c.add_argument("--device", required=True)
    c.add_argument("--key", required=True)

    sub.add_parser("products", help="показать продукты и варианты")
    a = ap.parse_args()

    if a.cmd == "products":
        for pid, (name, variants) in sorted(PRODUCTS.items()):
            vs = ", ".join(f"{k}={v}" for k, v in variants.items())
            print(f"  {pid:2}  {name:20} варианты: {vs}")
        return

    if a.cmd == "gen":
        did = a.device.strip().upper()
        if len(did) != 16:
            sys.exit("❌ Device ID должен быть ровно 16 символов")
        if not (1 <= a.months <= 255):
            sys.exit("❌ Срок 1-255 месяцев")
        key = encode_key(secret_for(a.product), a.variant, a.client, a.months, did)
        name = PRODUCTS.get(a.product, ("продукт %d" % a.product, {}))[0]
        vname = PRODUCTS.get(a.product, ("", {}))[1].get(a.variant, str(a.variant))
        print(f"\n  Продукт:    {name} (id {a.product})")
        print(f"  Вариант:    {vname} ({a.variant})")
        print(f"  Устройство: {did}")
        print(f"  Клиент:     #{a.client}   Срок: {a.months} мес.")
        print(f"\n  КЛЮЧ:  {key}\n")
        return

    if a.cmd == "check":
        data, err = decode_key(secret_for(a.product), a.key, a.device.strip().upper())
        if err:
            print(f"❌ {err}")
            sys.exit(1)
        print(f"✅ Ключ валиден: {data}")


if __name__ == "__main__":
    main()
