# -*- coding: utf-8 -*-
"""
Общий протокол лицензионных ключей v3 (product-agnostic).

Формат payload (7 байт / 56 бит):
    byte 0     : product_id        (0-255)   — какой продукт
    byte 1     : variant_id        (0-255)   — вариант (предмет/язык/категория)
    byte 2-3   : client_id         (0-65535) — номер клиента
    byte 4-5   : duration_months   (0-65535) — срок с момента активации
    byte 6     : flags             (0-255)   — резерв

Ключ: payload(7) + HMAC(product_secret, payload+device_id)[:8] = 15 байт
      base32 → 24 символа → XXXX-XXXX-XXXX-XXXX-XXXX-XXXX

product_secret выводится из master_secret:
    HMAC(master_secret, b"product:" + product_id)[:32]
Так один мастер-секрет обслуживает все продукты, но каждое приложение
встраивает только свой производный секрет (утечка одного != компрометация всех).
"""

import base64
import hashlib
import hmac
import struct

KEY_CHARS = 24            # длина ключа без дефисов
PAYLOAD_LEN = 7
SIG_LEN = 8
RAW_LEN = PAYLOAD_LEN + SIG_LEN  # 15

ENC_SALT = b"product-core-license-v3"
PBKDF2_ITERS = 100_000


def derive_product_secret(master: bytes, product_id: int) -> bytes:
    """Производный секрет конкретного продукта из мастер-секрета."""
    msg = b"product:" + bytes([product_id & 0xFF])
    return hmac.new(master, msg, hashlib.sha256).digest()


def pack_payload(product_id: int, variant_id: int, client_id: int,
                 duration_months: int, flags: int = 0) -> bytes:
    return struct.pack(
        ">BBHHB",
        product_id & 0xFF, variant_id & 0xFF, client_id & 0xFFFF,
        duration_months & 0xFFFF, flags & 0xFF,
    )


def unpack_payload(payload: bytes) -> dict:
    product_id, variant_id, client_id, duration_months, flags = \
        struct.unpack(">BBHHB", payload)
    return {
        "product_id": product_id, "variant_id": variant_id,
        "client_id": client_id, "duration_months": duration_months,
        "flags": flags,
    }


def sign(product_secret: bytes, payload: bytes, device_id: str) -> bytes:
    data = payload + device_id.upper().encode()
    return hmac.new(product_secret, data, hashlib.sha256).digest()[:SIG_LEN]


def encode_key(product_secret: bytes, payload: bytes, device_id: str) -> str:
    raw = payload + sign(product_secret, payload, device_id)
    enc = base64.b32encode(raw).decode().rstrip("=")
    return "-".join(enc[i:i + 4] for i in range(0, KEY_CHARS, 4))


def decode_key(key_str: str):
    """Возвращает (payload, sig) или None при неверном формате."""
    clean = key_str.replace("-", "").replace(" ", "").upper()
    if len(clean) != KEY_CHARS:
        return None
    padded = clean + "=" * ((8 - len(clean) % 8) % 8)
    try:
        raw = base64.b32decode(padded)
    except Exception:
        return None
    if len(raw) != RAW_LEN:
        return None
    return raw[:PAYLOAD_LEN], raw[PAYLOAD_LEN:]


def verify(product_secret: bytes, payload: bytes, sig: bytes,
           device_id: str) -> bool:
    return hmac.compare_digest(sig, sign(product_secret, payload, device_id))


def derive_enc_key(device_id: str) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", device_id.encode(), ENC_SALT, PBKDF2_ITERS)


def _keystream_xor(data: bytes, key: bytes) -> bytes:
    out = bytearray(len(data))
    for i in range(0, len(data), 32):
        bk = hmac.new(key, struct.pack(">I", i // 32), hashlib.sha256).digest()
        for j, b in enumerate(data[i:i + 32]):
            out[i + j] = b ^ bk[j]
    return bytes(out)


def encrypt_raw(data_bytes: bytes, key: bytes) -> bytes:
    """HMAC-keystream XOR + integrity tag по прямому 32-байтному ключу."""
    ct = _keystream_xor(data_bytes, key)
    tag = hmac.new(key, ct, hashlib.sha256).digest()[:16]
    return tag + ct


def decrypt_raw(raw: bytes, key: bytes):
    """Возвращает bytes или None (повреждён / неверный ключ)."""
    if len(raw) < 17:
        return None
    tag, ct = raw[:16], raw[16:]
    if not hmac.compare_digest(tag, hmac.new(key, ct, hashlib.sha256).digest()[:16]):
        return None
    return _keystream_xor(ct, key)


def encrypt(data_bytes: bytes, device_id: str) -> bytes:
    """Шифрование license.dat ключом, производным от device_id. Совместимо с Kotlin."""
    return encrypt_raw(data_bytes, derive_enc_key(device_id))


def decrypt(raw: bytes, device_id: str):
    return decrypt_raw(raw, derive_enc_key(device_id))


# ═══════════════════════════════════════════════════════════════════════════
#  v4 — АСИММЕТРИЧНАЯ ПОДПИСЬ ЛИЦЕНЗИЙ (Ed25519) + ШИФРОВАНИЕ КОНТЕНТА
#
#  В v3 один и тот же секрет и подписывал, и проверял ключи: кто достал его из
#  сборки — печатает ключи. В v4 лицензии подписываются ПРИВАТНЫМ ключом (только
#  у разработчика), а в приложение встроен лишь ПУБЛИЧНЫЙ ключ проверки.
#  Извлечение публичного ключа НЕ позволяет подделать лицензию.
# ═══════════════════════════════════════════════════════════════════════════

LICENSE_PREFIX = "OL1-"            # маркер строки лицензии v4
CONTENT_MAGIC = b"OLENC1\n"        # старый маркер (HMAC-keystream, медленный) — совместимость
CONTENT_MAGIC2 = b"OLENC2\n"       # AES-256-GCM (аппаратное ускорение, в сотни раз быстрее)


def generate_signing_keypair():
    """(private32, public32). Приватный ключ — ТОЛЬКО у разработчика."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization as _ser
    sk = Ed25519PrivateKey.generate()
    priv = sk.private_bytes(_ser.Encoding.Raw, _ser.PrivateFormat.Raw, _ser.NoEncryption())
    pub = sk.public_key().public_bytes(_ser.Encoding.Raw, _ser.PublicFormat.Raw)
    return priv, pub


def public_from_private(priv32: bytes) -> bytes:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization as _ser
    return (Ed25519PrivateKey.from_private_bytes(priv32)
            .public_key().public_bytes(_ser.Encoding.Raw, _ser.PublicFormat.Raw))


CONTENT_KEY_LEN = 32
SIG_LEN_ED = 64


def _license_message(payload: bytes, content_key: bytes, device_id: str) -> bytes:
    # подпись покрывает payload + ключ контента + устройство
    return payload + content_key + device_id.upper().encode()


def sign_license(priv32: bytes, payload: bytes, content_key: bytes, device_id: str) -> bytes:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    return Ed25519PrivateKey.from_private_bytes(priv32).sign(
        _license_message(payload, content_key, device_id))


def verify_license(pub32: bytes, payload: bytes, content_key: bytes,
                   sig: bytes, device_id: str) -> bool:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    try:
        Ed25519PublicKey.from_public_bytes(pub32).verify(
            sig, _license_message(payload, content_key, device_id))
        return True
    except Exception:
        return False


def encode_license(payload: bytes, content_key: bytes, sig: bytes) -> str:
    """Лицензия несёт payload(7) + ключ контента(32) + подпись(64). Ключа нет в сборке."""
    blob = base64.urlsafe_b64encode(payload + content_key + sig).decode().rstrip("=")
    return LICENSE_PREFIX + blob


def decode_license(license_str: str):
    """Возвращает (payload, content_key, sig) или None при неверном формате."""
    s = license_str.strip().replace(" ", "").replace("\n", "")
    if s.startswith(LICENSE_PREFIX):
        s = s[len(LICENSE_PREFIX):]
    s += "=" * ((4 - len(s) % 4) % 4)
    try:
        raw = base64.urlsafe_b64decode(s)
    except Exception:
        return None
    if len(raw) != PAYLOAD_LEN + CONTENT_KEY_LEN + SIG_LEN_ED:
        return None
    return (raw[:PAYLOAD_LEN],
            raw[PAYLOAD_LEN:PAYLOAD_LEN + CONTENT_KEY_LEN],
            raw[PAYLOAD_LEN + CONTENT_KEY_LEN:])


# ─── Ключ шифрования контента (один на продукт) ───

def derive_content_key(content_master: bytes, product_id: int) -> bytes:
    return hmac.new(content_master, b"content:" + bytes([product_id & 0xFF]),
                    hashlib.sha256).digest()


def encrypt_content(data: bytes, content_key: bytes) -> bytes:
    """Шифрует файл контента в AES-256-GCM (быстро, аппаратно). Используется при сборке.

    Формат: OLENC2\\n + nonce(12) + ciphertext+tag.
    """
    import os
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nonce = os.urandom(12)
    return CONTENT_MAGIC2 + nonce + AESGCM(content_key).encrypt(nonce, data, None)


def decrypt_content(raw: bytes, content_key: bytes):
    """OLENC2 — AES-GCM; OLENC1 — старый keystream (совместимость); без маркера — plaintext (dev)."""
    if raw.startswith(CONTENT_MAGIC2):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        body = raw[len(CONTENT_MAGIC2):]
        nonce, ct = body[:12], body[12:]
        try:
            return AESGCM(content_key).decrypt(nonce, ct, None)
        except Exception:
            return None
    if raw.startswith(CONTENT_MAGIC):
        return decrypt_raw(raw[len(CONTENT_MAGIC):], content_key)
    return raw


# ─── Короткий ключ активации (симметричный, 20 символов) ───
# Формат: base32( variant(1) + client(2) + months(1) + HMAC(content_key, payload+device_id)[:8] )
#         = 12 байт → 20 символов → XXXXX-XXXXX-XXXXX-XXXXX, привязан к устройству.
# Секрет MAC = content_key (встроен в приложение). product_id не кодируется:
# у каждого продукта свой content_key, поэтому чужой ключ не подойдёт.

SHORT_PAYLOAD_FMT = ">BHB"   # variant_id, client_id, duration_months


def _short_mac(content_key: bytes, payload: bytes, device_id: str) -> bytes:
    return hmac.new(content_key, payload + device_id.upper().encode(), hashlib.sha256).digest()[:8]


def encode_short(content_key: bytes, variant_id: int, client_id: int, months: int, device_id: str) -> str:
    payload = struct.pack(SHORT_PAYLOAD_FMT, variant_id & 0xFF, client_id & 0xFFFF, months & 0xFF)
    raw = payload + _short_mac(content_key, payload, device_id)
    enc = base64.b32encode(raw).decode().rstrip("=")
    return "-".join(enc[i:i + 5] for i in range(0, len(enc), 5))


def decode_short(key_str: str, content_key: bytes, device_id: str):
    """Возвращает dict(variant_id, client_id, duration_months) или None."""
    s = key_str.upper().replace("-", "").replace(" ", "").strip()
    s += "=" * ((8 - len(s) % 8) % 8)
    try:
        raw = base64.b32decode(s)
    except Exception:
        return None
    if len(raw) != 12:
        return None
    payload, mac = raw[:4], raw[4:]
    if not hmac.compare_digest(mac, _short_mac(content_key, payload, device_id)):
        return None
    variant, client, months = struct.unpack(SHORT_PAYLOAD_FMT, payload)
    return {"variant_id": variant, "client_id": client, "duration_months": months}
