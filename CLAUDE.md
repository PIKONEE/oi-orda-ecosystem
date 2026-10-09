# CLAUDE.md — Oi-Orda: точка входа для облачных сессий

Этот репозиторий — «пульт» для работы со всеми продуктами из облачного чата
(claude.ai/code и приложение Claude). Здесь ядро `product-core` и 4 продукта;
остальные проекты лежат в отдельных репозиториях и подключаются по запросу.

Главный документ по архитектуре и защите — `product-core/ECOSYSTEM.md`
(реестр product_id — §7). По каждому продукту — его собственный `CLAUDE.md`.

## Что готовит SessionStart-хук (`.claude/hooks/session-start.sh`)

Только в облаке (`CLAUDE_CODE_REMOTE=true`): ставит `cryptography` и `segno`,
добавляет `product-core` в `PYTHONPATH` (keygen работает без `pip install -e`),
и, если в окружении задан секрет `OI_ORDA_ECOSYSTEM_KEYS`, восстанавливает
`product-core/ecosystem.keys` (права 600, файл в `.gitignore`).

## Карта всех проектов

| Проект | Репозиторий | Что это | Стек | Проверка / запуск |
|---|---|---|---|---|
| Ядро + словарь (id 2), карта истории (id 4), музыкальная энциклопедия (id 6), логопед (id 7) | `PIKONEE/oi-orda-ecosystem` (этот) | лицензии v4, оболочки, сборка + контент продуктов | Python, HTML/JS, Kotlin | `cd products/<p> && node tools/validate.js` |
| 3D-модели (id 3) | `PIKONEE/oi-orda-3D-models` | 163 3D-плаката, three.js | HTML/JS на ядре | см. его `CLAUDE.md` (репо ~750 МБ) |
| Интерактивные плакаты (id 1) | `pikoneeeee/interactive-posters` (другой аккаунт!) | старые плакаты, **своя лицензия v2** | PySide6 | не мигрировать без запроса — сломает выданные ключи |
| Виртуальные стенды (id 9) | `PIKONEE/digital-posters` | био/хим/физ стенды RU+KZ | HTML/JS на ядре | см. его `CLAUDE.md` |
| Исходники стендов | `PIKONEE/digital-posters-` | галереи, OCR, метаданные | скрипты | — |
| Сайт oi-orda.kz (полный) | `PIKONEE/oi-orda.kz-FULL` | Flask-платформа (тесты, профориентация) | Flask, SQLite | `pip install -r requirements.txt && python app.py` |
| Сайт oi-orda.kz (старый) | `PIKONEE/oi-orda.kz` (**публичный**) | ранняя версия сайта | Flask | — |
| BabyBoss | `PIKONEE/babyboss` | школьный транспорт: приложение + админка, Kaspi QR | Django + mobile | см. его `CLAUDE.md` / `SETUP.md` |
| Bereke | `PIKONEE/bereke` | доставка внутри больницы; в планах Telegram-бот и QR отделений | Next.js, Postgres, Drizzle | `npm install && npm run typecheck && npm test` |
| Турникет | `PIKONEE/turniket` | учёт посещаемости (Hikvision iVMS-4200) | Next.js | `npm install && npm run dev` |
| Матлаборатория (id 5) | **нет на GitHub** (`D:\math_tools`) | — | — | сначала запушить в репозиторий |
| Telegram-боты | **нет на GitHub** | — | — | сначала запушить в репозиторий |

### Как подключить другой проект в облачной сессии

1. Вызвать инструмент `add_repo` (owner/repo из таблицы; для правок и push —
   `access: "push"`). Он сообщает путь клона (обычно `/home/user/<repo>`).
2. Клонировать ровно той командой, что он вернул (`git clone --depth 1 …`,
   таймаут ~10 мин — 3D-модели и стенды большие).
3. Прочитать `CLAUDE.md` проекта и следовать его правилам (у Bereke и BabyBoss
   они строгие: стек, красные линии, ревью человеком для платежей/RBAC).

Пользователь может и сам выбрать нужные репозитории при создании сессии.

## Лицензии и активация

```bash
python -m product_core.keygen genlicense <product_id> <variant_id> <client_id> \
    --device <DEVICE_ID_16hex> --months 12 --note "Школа №5"
python -m product_core.keygen verify "<OL1-…>" --device <DEVICE_ID>
python -m product_core.keygen embed <product_id>      # → _secret.py (не коммитить)
```

- Нужен `product-core/ecosystem.keys`. Если его нет — значит секрет
  `OI_ORDA_ECOSYSTEM_KEYS` не задан: так и скажи пользователю, **не** запускай
  `keygen init` (новые ключи сделают все выданные лицензии недействительными).
- `keys.db` в облаке временный (контейнер одноразовый). Поэтому после выпуска
  всегда выводи в ответе: строку лицензии, product/variant/client, Device ID,
  срок и заметку — это и есть запись в журнал.
- Никогда не печатай, не коммить и не отправляй содержимое `ecosystem.keys`,
  `_secret.py`, `keys.db`, `license.dat`.
- Плакаты (id 1) используют свою старую `licensing.py` (v2) — keygen ядра для них
  не подходит.

## QR-коды

```bash
python tools/qr.py "https://…" -o имя           # PNG → out/qr/имя.png
python tools/qr.py "OL1-…" -o license-school5   # лицензия в QR
python tools/qr.py "https://…" -o имя --svg     # для печати
python tools/qr.py --wifi "SSID" --password "…" -o wifi
```

Готовый файл отправляй пользователю через `SendUserFile` (status `normal`).
`out/` в `.gitignore`. Kaspi-QR организации в BabyBoss — это ссылка из поля
`kaspi_pay_url`; QR по ней делается этим же скриптом.

## Telegram-боты

- Кода ботов в репозиториях пока нет — попроси пользователя запушить его.
- `api.telegram.org` по умолчанию закрыт сетевой политикой облака: правки кода
  возможны, а проверка вживую — только после того, как пользователь добавит
  домен в Allowed domains окружения.
- Токены ботов — только через переменные окружения (секреты облака), не в код.
- Облачный контейнер не хостинг: бот, который должен работать постоянно,
  запускается на сервере/VPS, а здесь его правят, тестируют и пушат.

## Что можно только на компьютере пользователя

Сборка Windows-установщиков (`python -m build … --windows`: PyInstaller под
Windows, Inno Setup, WebView2), установка на подключённый Android-планшет,
файлы, которые лежат только на диске `D:\`. Для этого — Claude Desktop или
`claude remote-control` на самом компьютере.

## Превью контента в облаке

`python -m http.server 8765 --directory products/<p>/content` (или
`.claude/launch.json`). Оболочка `main.py` требует экран (pywebview/Qt) и в
облаке не запускается — в браузере контент открывается без активации.

## Правила

- Работать в выданной ветке, коммитить с понятным сообщением, PR — только по
  просьбе пользователя.
- Секреты — только переменные окружения; `.gitignore` не ослаблять.
- Перед правкой продукта — прочитать его `CLAUDE.md`; после правки контента —
  прогнать `node tools/validate.js` этого продукта.
- Отвечать пользователю по-русски.
