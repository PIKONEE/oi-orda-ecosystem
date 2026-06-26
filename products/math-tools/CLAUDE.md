# CLAUDE.md — Математическая лаборатория (math-tools)

> Продукт экосистемы Oi-Orda. Главный документ — `product-core/ECOSYSTEM.md`.
> При сомнениях верны он и реальный код в `product_core/`, **а не примеры в
> `product-core/README.md`** (там устаревший API лицензирования).

## Что это за продукт

- **Название / slug:** Математическая лаборатория / `math-tools`
- **product_id:** 5 (см. реестр ECOSYSTEM.md §7)
- **Архетип:** A (WebView) — весь контент в `content/index.html`, без зависимостей
- **Движок (Windows):** `webview2` (системный Edge WebView2; бандл ~45 МБ). Запасной — `qt` (~445 МБ). Задаётся в `product.json → "engine"`.
- **Платформы:** Windows + Android, активация по ключу
- **Языки:** RU + KZ (полный перевод, переключатель в шапке)
- **Модули:** визуализатор графиков функций; калькулятор вероятностей

## Железные правила

1. **`_secret.py` НЕ ТРОГАТЬ** и не коммитить (секрет продукта, сгенерирован
   `python -m product_core.keygen embed 5`).
2. **Оболочку/окно/активацию не писать** — это делает `product-core`. `main.py` —
   две строки, не трогать.
3. **Активация — только в оболочке, не в HTML.** В `content/index.html` НЕ должно
   быть логики активации. Поэтому при открытии файла в браузере активации нет
   (режим превью), а в собранном EXE — есть. Это требование, не баг.
4. Защита включена: `product.json` → `skip_activation:false`, `anti_copy:true`,
   `flag_secure:true`.
5. Двуязычность RU/KZ поддерживать во всём новом UI.

## Что можно менять

- Только `content/` (вёрстка, логика графиков/вероятностей, стили, `locales`).
- Контент самодостаточный: ноль внешних зависимостей, работает офлайн.

## Запуск и сборка

```bash
# Превью контента БЕЗ активации (разработка):
#   открыть content/index.html в браузере  (или Превью-без-активации.bat)

# Десктоп С активацией (как у пользователя), нужен product-core:
pip install -e <путь_к_product-core>
python main.py

# Сборка (ИЗ каталога product-core!). Шифрует контент + делает установщик:
cd <путь_к_product-core>
python -m build D:\math_tools --windows            # быстрый (PyInstaller)
python -m build D:\math_tools --windows --nuitka   # защищённый (Nuitka, машинный код)
#   → builds/windows/Mathtools/Mathtools.exe  и  Mathtools-Setup-1.0.0.exe
```

## Выдать лицензию клиенту (v4, Ed25519 — подделать нельзя)

```bash
# клиент называет Device ID с экрана активации
python -m product_core.keygen genlicense 5 0 <client_id> --device <DEVICE_ID> --months 12 --note "Школа"
#   → строка OL1-…  (клиент вставляет на экране активации). Ключ контента — внутри лицензии.
```

## Реальный API (если понадобится в JS-мосте core.*)

`core.getDeviceId()`, `core.getStatus()` (JSON {valid,variant_id,days_left,...}),
`core.activateKey(k)` → `onActivationSuccess/onActivationError`, `core.log(m)`.
Экран активации рисует оболочка — в контенте его делать не нужно.
