# CLAUDE.md — инструкция ИИ-ассистенту по этому продукту

> Этот файл лежит в каждом продукте экосистемы Oi-Orda. Прочитай его перед любой
> доработкой. Главный документ экосистемы — `product-core/ECOSYSTEM.md`; при
> сомнениях верны он и реальный код в `product_core/`. Защита — **v4 (Ed25519)**.

## Что это за продукт

- **Название / slug:** `<ЗАПОЛНИ>` / `<slug>`
- **product_id:** `<из реестра ECOSYSTEM.md §7>`
- **Архетип:** `A (WebView)` или `B (Python)` — оставь нужное
- **Движок (Windows):** `webview2` (по умолчанию, ~45 МБ) или `qt` (~445 МБ) — в `product.json → "engine"`
- **Платформы:** Windows + Android, активация по лицензии
- **Языки:** RU + KZ (полный перевод)

## Железные правила

1. **`_secret.py` НЕ ТРОГАТЬ** и не коммитить. В v4 он содержит только публичный
   ключ проверки. Создаётся владельцем: `python -m product_core.keygen embed <id> > _secret.py`.
2. **Не писать свою оболочку, окно, экран активации, систему лицензий.** Всё это в
   `product-core`. Дублировать = неразбериха.
3. **Защита включена всегда.** `product.json`: `skip_activation: false`,
   `anti_copy: true`, `flag_secure: true`. Не отключай без явной просьбы.
4. **Двуязычность RU/KZ** во всём новом UI.

## Архетип A (WebView) — что можно менять

- Пиши только в `content/` (HTML/JS/CSS/ассеты/`locales/`). Точка входа — `content/index.html`.
- `main.py` — две строки, не трогай:
  ```python
  from product_core.shell import run
  run(__file__)
  ```
- Мост к оболочке из контента (одинаков на Win/Android, оба движка):
  ```js
  // window.core.getDeviceId(cb)  -> cb("A3F2...")  (16 hex)
  // window.core.getStatus(cb)    -> cb('{"valid":true,"variant_id":0,"days_left":120,...}')
  // window.core.activateKey(lic) -> вызовет onActivationSuccess / onActivationError
  // window.core.log("...")       -> лог оболочки
  ```
  Экран активации рисует оболочка — в контенте его делать не нужно.

## Архетип B (Python) — что можно менять

- Свой код (Flask / PySide6 / SQLite). В начало `main.py` — блок лицензии **v4**:
  ```python
  from product_core import licensing
  from product_core.device_id import get_device_id
  from _secret import PRODUCT_ID, get_public_key
  licensing.configure_verify(get_public_key(), PRODUCT_ID, app_name="<slug>")
  if not licensing.is_activated():
      ok, msg = licensing.activate_license(input(f"Device {get_device_id()}\nЛицензия: ").strip())
      if not ok:
          raise SystemExit(msg)
  ```

## Реальный API лицензирования (v4 — бери эти имена)

| Функция | Назначение |
|---|---|
| `licensing.configure_verify(public_key, product_id, app_name=...)` | задать публичный ключ |
| `licensing.is_activated() -> bool` | есть ли активная лицензия |
| `licensing.activate_license(lic) -> (ok, msg)` | проверить подпись + сохранить `license.dat` |
| `licensing.validate_license(lic) -> (ok, dict)` | проверить без сохранения |
| `licensing.get_license_status() -> dict` | `{valid, reason, variant_id, expires_at, days_left}` |
| `licensing.get_content_key() -> bytes\|None` | ключ контента из активной лицензии |
| `from product_core.device_id import get_device_id` | ID устройства (16 hex) |

`_secret.py` экспортирует `PRODUCT_ID` и `get_public_key() -> bytes`.
(Старый v3: `configure`/`activate_key`/`get_secret` — только для legacy-плакатов.)

## Запуск и сборка

```bash
# превью контента БЕЗ активации: открыть content/index.html в браузере
python main.py                                  # десктоп С активацией (нужен pip install -e product-core)

# сборка — ИЗ каталога product-core:
cd <путь_к_product-core>
python -m build <папка_продукта> --windows           # PyInstaller (быстро)
python -m build <папка_продукта> --windows --nuitka  # Nuitka (машинный код; ТОЛЬКО engine=qt)
python -m build <папка_продукта> --android
```

## Выдать лицензию клиенту

```bash
python -m product_core.keygen genlicense <id> <variant> <client> --device <DEVICE_ID> --months 12
#   → строка OL1-…  (клиент вставляет её на экране активации)
```

## Definition of Done (перед релизом)

- [ ] работает на Windows (проверено запуском собранного EXE);
- [ ] без лицензии — экран активации; с лицензией — контент; чужая/подделка — отказ;
- [ ] контент в бандле — шифртекст (`OLENC1`), plaintext не виден;
- [ ] RU и KZ переведены полностью;
- [ ] `product_id`/`variant_id` вписаны в `product-core/ECOSYSTEM.md §7`;
- [ ] `_secret.py`, `keys.db`, `license.dat`, `ecosystem.keys` не попали в git.
