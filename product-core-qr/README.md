# product-core — централизованное ядро для образовательных продуктов

Единая система **лицензирования, защиты и сборки** для всех продуктов линейки
(плакаты, 3D-модели, словари, карты, матлаборатория и т.д.).
Один раз настроил — переиспользуешь на каждом новом продукте.

> 📘 **Главный документ — [ECOSYSTEM.md](ECOSYSTEM.md)**: как устроена линейка и как
> создавать продукты (архетипы, реестр id, правила защиты, движки, миграция).
> Этот README — короткий техсправочник по ядру. При расхождении верны
> `ECOSYSTEM.md` и реальный код в `product_core/`.

Текущая версия защиты — **v4 (Ed25519)**. Старый симметричный v3 оставлен только
для совместимости со старыми сборками плакатов; для новых продуктов не используется.

---

## Что это такое

Библиотека (не фреймворк). Продукт = **твой контент + `product.json` + `_secret.py`**.
Оболочка/окно/активацию/сборку даёт ядро.

Реальный API лицензирования (`product_core/licensing.py`):

| Функция | Что делает |
|---|---|
| `configure_verify(public_key, product_id, app_name=...)` | v4: задать публичный ключ проверки |
| `is_activated() -> bool` | есть ли действующая лицензия |
| `activate_license(license: str) -> (ok, msg)` | проверить подпись Ed25519 и сохранить `license.dat` |
| `validate_license(license) -> (ok, dict)` | проверить без сохранения |
| `get_license_status() -> dict` | `{valid, reason, variant_id, expires_at, days_left}` |
| `get_content_key() -> bytes \| None` | ключ расшифровки контента из активной лицензии |
| `get_device_id() -> str` | ID устройства (из `product_core.device_id`) |

---

## Два архетипа продукта

Подробности — [ECOSYSTEM.md §3, §5](ECOSYSTEM.md). Коротко:

**A — WebView-продукт (HTML/JS/CSS)** — по умолчанию. Пишешь только `content/`,
`main.py` = 2 строки:
```python
from product_core.shell import run
run(__file__)
```
Оболочка даёт окно, активацию, защиту, сборку. Контент общается с ней через
JS-мост `window.core` (`getDeviceId`, `getStatus`, `activateKey`, `log`) — одинаково
на Windows (WebView2/Qt) и Android.

**Б — произвольный Python (Flask, SQLite, своя логика)** — свой код + блок лицензии:
```python
from product_core import licensing
from product_core.device_id import get_device_id
from _secret import PRODUCT_ID, get_public_key
licensing.configure_verify(get_public_key(), PRODUCT_ID, app_name="my-slug")
if not licensing.is_activated():
    print("Device ID:", get_device_id())
    ok, msg = licensing.activate_license(input("Лицензия: ").strip())
    if not ok:
        raise SystemExit(msg)
# дальше — твой код
```

---

## Движок Windows-оболочки и размер

`product.json → "engine"` (см. [ECOSYSTEM.md §8a](ECOSYSTEM.md)):

| engine | Движок | Размер продукта |
|---|---|---|
| **`webview2`** (по умолчанию) | системный Edge WebView2 (как WebView на Android) | бандл ~45 МБ, установщик ~20 МБ |
| `qt` | встроенный QtWebEngine (Chromium внутри) | бандл ~445 МБ, установщик ~115 МБ |

WebView2 встроен в Windows 11 и есть почти на всех Windows 10. Где нет — положи
рядом с установщиком `MicrosoftEdgeWebView2RuntimeInstaller.exe` (установщик
поставит его тихо). Android уже лёгкий (~8 МБ) — системный WebView.

---

## Пошагово: новый продукт

```bash
# 1. Шаблон
cp -r product-core/templates/new_product/  мой-продукт/
#    Заполнить product.json (product_id из реестра ECOSYSTEM.md §7, slug, name, engine)

# 2. Один раз на машине разработчика
cd product-core
pip install -e .
python -m product_core.keygen init                  # создаёт ecosystem.keys (БЭКАП! не коммитить)

# 3. Секрет продукта — в нём ТОЛЬКО публичный ключ
python -m product_core.keygen embed 5 > ../мой-продукт/_secret.py

# 4. Контент (архетип A: content/index.html) или свой код (архетип Б)

# 5. Запуск в разработке (контент НЕ зашифрован, активации нет — режим превью)
cd ../мой-продукт && python main.py

# 6. Сборка — ИЗ каталога product-core. Шифрует контент + делает установщик Inno Setup.
cd ../product-core
python -m build ../мой-продукт --windows            # PyInstaller (быстро)
python -m build ../мой-продукт --windows --nuitka   # Nuitka (машинный код; только engine=qt)
python -m build ../мой-продукт --android            # Android (см. ECOSYSTEM §9)
#    → ../мой-продукт/builds/windows/<Name>/  и  <Name>-Setup-<ver>.exe

# 7. Выдать ЛИЦЕНЗИЮ клиенту (он называет свой Device ID с экрана активации)
python -m product_core.keygen genlicense 5 0 42 --device A3F2B1C8E4D71029 --months 12 --note "Школа №5"
#                                        │ │  └ client_id
#                              product_id┘ └ variant_id
#    → строка OL1-…  (клиент вставляет её на экране активации)
```

---

## Формат лицензии v4 (Ed25519)

Лицензия — строка `OL1-<base64url>`, ~140 символов, вставляется на экране активации:

```
payload(7) + ключ_контента(32) + подпись_Ed25519(64)   →  base64url  →  OL1-…

payload (big-endian):
  byte 0    product_id        какой продукт
  byte 1    variant_id        вариант (предмет/язык/категория)
  byte 2-3  client_id         номер клиента
  byte 4-5  duration_months   срок с момента активации
  byte 6    flags             резерв

подпись = Ed25519(приватный_ключ, payload + ключ_контента + device_id)
```

---

## Модель безопасности

```
ecosystem.keys (ТОЛЬКО у разработчика, gitignored)
  ├── Ed25519 приватный ключ   → подписывает лицензии (keygen genlicense)
  └── мастер-ключ контента     → ключ шифрования контента продукта

embed <id>      →  _secret.py: ТОЛЬКО публичный ключ (раскрытие безопасно)
genlicense …    →  лицензия несёт ключ контента + подпись, привязана к device_id
build           →  content/* шифруется (маркер OLENC1); ключа контента в сборке НЕТ
```

- **Подделать лицензию нельзя:** в продукте только публичный ключ проверки; чтобы
  выпустить лицензию, нужен приватный (его в сборке нет).
- **Контент не достать из установщика:** файлы зашифрованы, ключ приходит внутри
  подписанной лицензии и хранится в device-bound `license.dat`; расшифровка только
  в памяти (oilab:// в Qt / локальный сервер 127.0.0.1 в WebView2). DevTools off.
- **Привязка к устройству:** подпись и `license.dat` завязаны на `device_id`.

Подробный разбор и честные пределы офлайн-DRM — [ECOSYSTEM.md §6](ECOSYSTEM.md).

---

## Архитектура

```
product-core/
  product_core/
    _protocol.py     ← формат лицензии v4 (Ed25519) + шифрование контента
    licensing.py     ← проверка/активация лицензий (в сборке)
    keygen.py        ← выпуск лицензий (ТОЛЬКО у разработчика)
    device_id.py     ← кросс-платформенный отпечаток устройства
    config.py        ← загрузка product.json (+ выбор движка)
    shell/
      __init__.py    ← диспетчер движка (webview2 | qt)
      app_webview2.py← лёгкая оболочка на системном WebView2 (pywebview)
      app.py         ← запасная оболочка на QtWebEngine
      common.py      ← общие помощники (без Qt)
      templates/     ← экран активации (HTML, принимает лицензию v4)
  android_shell/     ← Android WebView-приложение (Kotlin, системный WebView)
  build/
    windows.py       ← PyInstaller/Nuitka + шифрование контента + Inno Setup
    android.py       ← Gradle assembleRelease
    __main__.py      ← python -m build
  templates/new_product/  ← шаблон продукта (product.json, main.py, CLAUDE.md)
  ecosystem.keys     ← (gitignored) приватные ключи разработчика
  keys.db            ← (gitignored) журнал выданных лицензий
```

---

## Файлы, которые НЕЛЬЗЯ коммитить (в `.gitignore`)

| Файл | Причина |
|---|---|
| `ecosystem.keys` | приватный ключ подписи + мастер контента. Утечка = компрометация всего |
| `_secret.py` | секрет продукта (в v4 — публичный ключ, но всё равно не коммитим) |
| `keys.db` | журнал выданных лицензий (клиент ↔ устройство) |
| `master.key` | legacy-секрет v3 (если остался от старой схемы) |

---

## Работа с Claude (ИИ-ассистентом)

В каждом продукте лежит `CLAUDE.md` (шаблон — `templates/new_product/CLAUDE.md`):
он содержит актуальный контракт (архетип, движок, реальный v4-API, что `_secret.py`
не трогать). Открыл папку продукта, попросил доработать — Claude читает этот файл.
**Не используй старые «промпты» — канон в `CLAUDE.md` и ECOSYSTEM.md.**

Реестр продуктов и вариантов — [ECOSYSTEM.md §7](ECOSYSTEM.md).
