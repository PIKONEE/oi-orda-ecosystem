# Oi-Orda — экосистема образовательных продуктов

Монорепозиторий: общее ядро **product-core** + продукты, построенные на нём.

## Структура
```
product-core/        ← хребет: лицензии v4 (Ed25519), оболочки WebView2/Qt/Android, keygen, сборка
products/
├── smart-dictionary/      (id=2) Умный словарь (англ.)
├── interactive-map/       (id=4) Интерактивная карта истории Казахстана
├── music-encyclopedia/    (id=6) Музыкальная энциклопедия (карта/лента/тренажёр слуха)
└── speech-therapy/        (id=7) Кабинет логопеда (карточки/игра звуков/скороговорки, RU+KZ)
```

Каждый продукт = `content/` + `product.json` + `_secret.py` (генерируется keygen, **в репозиторий не входит**).
Архитектура и правила — в [`product-core/ECOSYSTEM.md`](product-core/ECOSYSTEM.md); по каждому продукту — его `CLAUDE.md`.

## Важно
Секреты (`ecosystem.keys`, `_secret.py`, `keys.db`, `master.key`, `license.dat`) и сборки
(`builds/`, APK/EXE) **исключены** из репозитория (`.gitignore`). Ключи хранятся только у разработчика.

## Запуск продукта (dev)
```bash
pip install -e product-core
cd products/<продукт> && python main.py
# или быстрый просмотр контента:  python -m http.server -d content
```

## Сборка
```bash
cd product-core
python -m build ../products/<продукт> --windows     # Windows
python -m build ../products/<продукт> --android      # Android APK (JDK17 + Android SDK)
```
