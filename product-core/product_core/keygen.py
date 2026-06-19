# -*- coding: utf-8 -*-
"""
Генератор лицензий product-core v4 (ТОЛЬКО у разработчика, не в сборке!).

v4 = асимметричная подпись Ed25519:
  • лицензии подписываются ПРИВАТНЫМ ключом (хранится только здесь);
  • в приложение встраивается лишь ПУБЛИЧНЫЙ ключ проверки + ключ контента;
  • извлечение встроенных ключей НЕ позволяет подделать лицензию.

Команды:
    python -m product_core.keygen init [--force]
        Создать хранилище разработчика ecosystem.keys (Ed25519 + мастер контента).
        Один раз! Сделайте резервную копию — без него нельзя выпускать лицензии.

    python -m product_core.keygen embed <product_id>
        Вывести _secret.py для встраивания (PRODUCT_ID + публичный ключ + ключ контента).

    python -m product_core.keygen genlicense <product_id> <variant_id> <client_id> \\
            --device <DEVICE_ID> [--months 12] [--note "Школа №5"]
        Выпустить ПОДПИСАННУЮ лицензию для устройства. Печатает строку лицензии.

    python -m product_core.keygen verify <LICENSE> --device <DEVICE_ID>
        Проверить лицензию публичным ключом.

    python -m product_core.keygen list [--product <id>]
        Показать выданные лицензии.
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime

from . import _protocol as proto

_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_DIR)
KEYSTORE_FILE = os.path.join(_ROOT, "ecosystem.keys")   # приватные ключи разработчика
DB_FILE = os.path.join(_ROOT, "keys.db")


# ─── Хранилище ключей разработчика ───

def load_keystore() -> dict:
    if not os.path.exists(KEYSTORE_FILE):
        print(f"❌ {KEYSTORE_FILE} не найден. Запустите: python -m product_core.keygen init")
        sys.exit(1)
    with open(KEYSTORE_FILE, "r", encoding="utf-8") as f:
        ks = json.load(f)
    if "ed25519_priv" not in ks or "content_master" not in ks:
        print("❌ Повреждённое ecosystem.keys")
        sys.exit(1)
    return ks


def cmd_init(args):
    if os.path.exists(KEYSTORE_FILE) and not args.force:
        print(f"⚠️  {KEYSTORE_FILE} уже существует.")
        print("   Перезапись сделает ВСЕ ранее выпущенные лицензии и сборки несовместимыми.")
        print("   Если уверены — добавьте --force.")
        return
    priv, pub = proto.generate_signing_keypair()
    ks = {
        "version": 4,
        "ed25519_priv": priv.hex(),
        "ed25519_pub": pub.hex(),
        "content_master": os.urandom(32).hex(),
        "created": datetime.now().isoformat(timespec="seconds"),
    }
    with open(KEYSTORE_FILE, "w", encoding="utf-8") as f:
        json.dump(ks, f, indent=2)
    print(f"✅ Хранилище разработчика создано: {KEYSTORE_FILE}")
    print("   • Ed25519 (подпись лицензий) + мастер-ключ контента (256 бит)")
    print("   ⚠️  СДЕЛАЙТЕ РЕЗЕРВНУЮ КОПИЮ и НЕ коммитьте в git.")
    print("   ⚠️  Без него нельзя выпускать лицензии и пересобирать продукты.")


def cmd_embed(args):
    ks = load_keystore()
    pub = bytes.fromhex(ks["ed25519_pub"])

    print("# ─── _secret.py (v4) — сгенерировано keygen embed. НЕ коммитить. ───")
    print(f"# Продукт #{args.product_id}")
    print(f"# Содержит ТОЛЬКО публичный ключ проверки. Ни секрета подписи, ни ключа")
    print(f"# контента в сборке нет: подделать лицензию и достать контент из самого")
    print(f"# установщика невозможно (ключ контента приходит внутри лицензии).")
    print(f"PRODUCT_ID = {args.product_id}")
    print(f"LICENSE_VERSION = 4")
    print(f"_PUB = {list(pub)}")
    print()
    print("def get_public_key():")
    print("    return bytes(_PUB)")
    print()
    print("# Для Android вставьте _PUB в Licensing.kt (публичный ключ Ed25519).")


# ─── База выданных лицензий ───

def _db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license TEXT UNIQUE NOT NULL,
            product_id INTEGER NOT NULL, variant_id INTEGER NOT NULL,
            client_id INTEGER NOT NULL, duration_months INTEGER NOT NULL,
            device_id TEXT NOT NULL, note TEXT DEFAULT '', created_at TEXT NOT NULL
        )""")
    conn.commit()
    return conn


def cmd_genlicense(args):
    for name, val, hi in (("product_id", args.product_id, 255),
                          ("variant_id", args.variant_id, 255),
                          ("client_id", args.client_id, 65535)):
        if not (0 <= val <= hi):
            print(f"❌ {name} должен быть 0–{hi}"); sys.exit(1)
    if not (1 <= args.months <= 65535):
        print("❌ months должен быть 1–65535"); sys.exit(1)
    device_id = (args.device or "").strip().upper()
    if len(device_id) != 16:
        print(f"❌ Device ID должен быть 16 hex-символов (получено {len(device_id)})"); sys.exit(1)

    ks = load_keystore()
    priv = bytes.fromhex(ks["ed25519_priv"])
    content_master = bytes.fromhex(ks["content_master"])
    content_key = proto.derive_content_key(content_master, args.product_id)
    payload = proto.pack_payload(args.product_id, args.variant_id, args.client_id, args.months)
    sig = proto.sign_license(priv, payload, content_key, device_id)
    license_str = proto.encode_license(payload, content_key, sig)

    conn = _db()
    conn.execute(  # OR IGNORE: ключ детерминирован, повторная выдача для того же устройства — не ошибка
        "INSERT OR IGNORE INTO licenses (license, product_id, variant_id, client_id, duration_months, "
        "device_id, note, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (license_str, args.product_id, args.variant_id, args.client_id, args.months,
         device_id, args.note or "", datetime.now().isoformat(timespec="seconds")))
    conn.commit(); conn.close()

    print()
    print("  🔑  ЛИЦЕНЗИЯ (отправьте клиенту, он вставит её на экране активации):")
    print(f"\n  {license_str}\n")
    print(f"  Продукт #{args.product_id}  вариант #{args.variant_id}  клиент #{args.client_id}")
    print(f"  Устройство:  {device_id}")
    print(f"  Срок:        {args.months} мес. (с момента активации)")
    if args.note:
        print(f"  Заметка:     {args.note}")
    print()


def cmd_genshort(args):
    if not (0 <= args.variant_id <= 255):
        print("❌ variant_id должен быть 0–255"); sys.exit(1)
    if not (0 <= args.client_id <= 65535):
        print("❌ client_id должен быть 0–65535"); sys.exit(1)
    if not (1 <= args.months <= 255):
        print("❌ months должен быть 1–255 (для короткого ключа)"); sys.exit(1)
    device_id = (args.device or "").strip().upper()
    if len(device_id) != 16:
        print(f"❌ Device ID должен быть 16 hex-символов (получено {len(device_id)})"); sys.exit(1)

    ks = load_keystore()
    content_key = proto.derive_content_key(bytes.fromhex(ks["content_master"]), args.product_id)
    key = proto.encode_short(content_key, args.variant_id, args.client_id, args.months, device_id)

    conn = _db()
    conn.execute(
        "INSERT OR IGNORE INTO licenses (license, product_id, variant_id, client_id, duration_months, "
        "device_id, note, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (key, args.product_id, args.variant_id, args.client_id, args.months,
         device_id, args.note or "short", datetime.now().isoformat(timespec="seconds")))
    conn.commit(); conn.close()

    print()
    print("  🔑  КОРОТКИЙ КЛЮЧ (20 символов, вставьте на экране активации):")
    print(f"\n  {key}\n")
    print(f"  Продукт #{args.product_id}  вариант #{args.variant_id}  клиент #{args.client_id}")
    print(f"  Устройство:  {device_id}")
    print(f"  Срок:        {args.months} мес. (с момента активации)")
    print()


def cmd_verify(args):
    device_id = (args.device or "").strip().upper()
    if len(device_id) != 16:
        print("❌ Нужен корректный --device (16 hex)"); sys.exit(1)
    ks = load_keystore()
    pub = bytes.fromhex(ks["ed25519_pub"])
    decoded = proto.decode_license(args.license)
    if decoded is None:
        print("  ❌ Неверный формат лицензии"); sys.exit(1)
    payload, content_key, sig = decoded
    if not proto.verify_license(pub, payload, content_key, sig, device_id):
        print("  ❌ Подпись неверна для этого устройства"); sys.exit(1)
    data = proto.unpack_payload(payload)
    print(f"  ✅ Лицензия валидна для устройства {device_id}")
    print(f"  Продукт #{data['product_id']}  вариант #{data['variant_id']}  "
          f"клиент #{data['client_id']}  срок {data['duration_months']} мес.")


def cmd_list(args):
    conn = _db()
    q = ("SELECT license, product_id, variant_id, client_id, duration_months, device_id, note, created_at "
         "FROM licenses")
    rows = (conn.execute(q + " WHERE product_id=? ORDER BY id DESC", (args.product,)).fetchall()
            if args.product is not None else
            conn.execute(q + " ORDER BY id DESC").fetchall())
    conn.close()
    if not rows:
        print("  Лицензий пока нет."); return
    for lic, pid, vid, cid, dur, dev, note, created in rows:
        print(f"  prod {pid} var {vid} cli {cid} {dur}мес  dev {dev}  {created}  {note}")
        print(f"     {lic}")
    print(f"\n  Всего: {len(rows)}")


def main():
    ap = argparse.ArgumentParser(
        description="Генератор лицензий product-core v4 (Ed25519)",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = ap.add_subparsers(dest="command")

    i = sub.add_parser("init", help="Создать ecosystem.keys (один раз!)")
    i.add_argument("--force", action="store_true")

    e = sub.add_parser("embed", help="Вывести _secret.py для встраивания")
    e.add_argument("product_id", type=int)

    g = sub.add_parser("genlicense", help="Выпустить подписанную лицензию (длинная, Ed25519)")
    g.add_argument("product_id", type=int)
    g.add_argument("variant_id", type=int)
    g.add_argument("client_id", type=int)
    g.add_argument("--device", required=True, help="Device ID устройства (16 hex)")
    g.add_argument("--months", type=int, default=12)
    g.add_argument("--note", default="")

    gs = sub.add_parser("genshort", help="Выпустить короткий ключ (20 символов, симметричный)")
    gs.add_argument("product_id", type=int)
    gs.add_argument("variant_id", type=int)
    gs.add_argument("client_id", type=int)
    gs.add_argument("--device", required=True, help="Device ID устройства (16 hex)")
    gs.add_argument("--months", type=int, default=12)
    gs.add_argument("--note", default="")

    v = sub.add_parser("verify", help="Проверить лицензию")
    v.add_argument("license")
    v.add_argument("--device", required=True)

    l = sub.add_parser("list", help="Показать выданные лицензии")
    l.add_argument("--product", type=int, default=None)

    args = ap.parse_args()
    cmds = {"init": cmd_init, "embed": cmd_embed, "genlicense": cmd_genlicense,
            "genshort": cmd_genshort, "verify": cmd_verify, "list": cmd_list}
    if args.command in cmds:
        cmds[args.command](args)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
