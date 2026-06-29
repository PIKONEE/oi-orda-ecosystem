# -*- coding: utf-8 -*-
"""
ТЕСТ QR-активации: сгенерировать v4-лицензию + QR-картинку из Device ID.

Использование:
    python qr_license.py <DEVICE_ID>

  <DEVICE_ID> — 16 hex-символов с экрана активации доски (кнопка показывает ID).

Нужно один раз:  pip install "qrcode[pil]"   (cryptography обычно уже стоит)

Берёт ТЕСТОВЫЙ ключ из product-core-qr/ecosystem.keys (одноразовый, не настоящий мастер).
Печатает строку OL1-... и сохраняет license_<DEVICE_ID>.png — покажи QR на телефоне и
наведи на него камеру доски (кнопка «Сканировать QR» на экране активации).
"""
import sys
import os
import json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "product-core-qr"))
from product_core import _protocol as proto   # noqa: E402

PRODUCT_ID = 4      # interactive-map (= interactive-map-qr)
VARIANT_ID = 0
CLIENT_ID = 1
MONTHS = 12


def main():
    if len(sys.argv) < 2:
        print("Использование: python qr_license.py <DEVICE_ID>")
        return
    device_id = sys.argv[1].strip().upper()
    if len(device_id) != 16:
        print(f"❌ Device ID должен быть 16 hex-символов (получено {len(device_id)})")
        return

    ks_path = os.path.join(HERE, "product-core-qr", "ecosystem.keys")
    if not os.path.exists(ks_path):
        print(f"❌ Нет {ks_path}")
        return
    ks = json.loads(open(ks_path, encoding="utf-8").read())

    priv = bytes.fromhex(ks["ed25519_priv"])
    content_key = proto.derive_content_key(bytes.fromhex(ks["content_master"]), PRODUCT_ID)
    payload = proto.pack_payload(PRODUCT_ID, VARIANT_ID, CLIENT_ID, MONTHS)
    sig = proto.sign_license(priv, payload, content_key, device_id)
    lic = proto.encode_license(payload, content_key, sig)

    print("\n  🔑  Лицензия (OL1-...):\n")
    print("  " + lic + "\n")
    print(f"  Устройство: {device_id}   срок: {MONTHS} мес.\n")

    try:
        import qrcode
        img = qrcode.make(lic)
        out = os.path.join(HERE, f"license_{device_id}.png")
        img.save(out)
        print(f"  ✅ QR сохранён: {out}")
        print("  Покажи этот QR на телефоне/бумаге и наведи камеру доски.")
    except ImportError:
        print('  (Чтобы получить QR-картинку: pip install "qrcode[pil]")')
        print("  Либо вставь строку OL1-... вручную — она тоже принимается на экране активации.")


if __name__ == "__main__":
    main()
