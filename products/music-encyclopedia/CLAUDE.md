# CLAUDE.md — Интерактивная музыкальная энциклопедия

> Перед доработкой прочитай `product-core/ECOSYSTEM.md` (актуально — v4 Ed25519,
> движок webview2). При сомнениях верен он и код в `product_core/`.

## Что это
- **slug / product_id:** `music-encyclopedia` / **6**; вариант **0 = music**.
- **Архетип A (WebView), движок webview2.** Расположение: `D:\Products\music-encyclopedia`.
- Три раздела в одном окне (верхняя навигация): **Карта традиций** (клик по региону →
  карточка: инструменты, ритм/лад, традиция, демо-звук; ≥20 регионов, акцент на
  Казахстане), **Лента истории** (Барокко→современность; клик по эпохе → черты стиля,
  композиторы, инструменты, музыкальный фрагмент), **Тренажёр слуха** (нота / интервал /
  аккорд; статистика). Языки: **RU + KZ** (полностью). Тема — «концертный тёмный».

## Технологии и факты ядра
- **Звук — гибрид.** Тренажёр слуха и фолбэк целиком синтезируются в `js/audio.js`
  (Web Audio: точные ноты/интервалы/аккорды, без файлов). Для ленты истории и демо
  инструментов — вшитые короткие записи **только со свободными лицензиями**
  (Public Domain / CC0 / CC BY) из Wikimedia Commons; если файла нет — короткий
  синт-мотив. `AudioContext` стартует по первому жесту (политика автоплея).
- **Карта** — **Leaflet** локально (`content/lib/`) + физические тайлы мира
  `content/tiles/{z}/{x}/{y}.jpg` (как в interactive-map: базовый слой с
  `maxNativeZoom:3` → нет пустых краёв; `capWorldZoom`; зум-контролы справа). Тайлы
  затемнены CSS-фильтром под тёмную тему.
- webview2-оболочка отдаёт контент локальным http-сервером (расшифровка в памяти),
  сборка шифрует **весь** `content/`. `common.MIME` уже знает mp3/ogg/wav → вшитое
  аудио работает офлайн (fetch+decodeAudioData), и на Android тоже.
- `_secret.py` (v4) — только публичный ключ; `python -m product_core.keygen embed 6`
  (на этой машине: префикс `PYTHONIOENCODING=utf-8` при редиректе).

## Структура контента
```
content/
├── index.html  app.css
├── lib/        leaflet.js, leaflet.css
├── assets/     fonts.css, fonts/ (PT Serif + Inter)
├── tiles/{z}/{x}/{y}.jpg      ← физические тайлы мира (офлайн)
├── audio/      instr_*.(mp3|ogg|wav), era_*.*   ← вшитые свободные записи (опц.)
├── locales/i18n.js            ← window.I18N {ru,kz} — строки интерфейса
├── js/  audio.js · map.js (MMap) · timeline.js (MTimeline) · ear.js (MEar)
└── data/
    ├── regions.js     ← window.REGIONS    (традиции мира)
    ├── eras_music.js  ← window.MUSIC_ERAS (эпохи)
    ├── eartrainer.js  ← window.EAR        (ноты/интервалы/аккорды/уровни)
    └── credits.js     ← window.CREDITS    (источники аудио; генерит fetch_audio.py)
```
Данные грузятся через `<script>`-глобалы `window.*` (надёжно, офлайн, Android).
Порядок в `index.html`: leaflet → data/* → i18n → audio.js → **app.js** (создаёт
`window.APP`) → map.js/timeline.js/ear.js. `app.js` даёт `APP.t(key)` (UI),
`APP.pick(obj,'name')`/`APP.L({ru,kz})` (контент), навигацию и переключение языка.

## Как добавить контент (отделён от кода!)
- **Регион:** один объект в `data/regions.js` (`id, lat, lng, nameRu/Kz, instrRu/Kz[],
  rhythmRu/Kz, descRu/Kz, scale, audio?, kazakh?, extra?[]`). `scale` — лад для
  синт-демо (`pentatonic/minor/maqam/phrygian/blues/...`). `audio` — ключ файла
  `audio/<audio>.*`; нет файла → синтез по `scale`.
- **Эпоха:** объект в `data/eras_music.js` (`id, from, to, nameRu/Kz, traits[{ru,kz}],
  composers[], instrRu/Kz[], descRu/Kz, motif[[полутон,доля]], audio?, kazakhRu/Kz?`).
- **Тренажёр:** наборы/уровни — в `data/eartrainer.js` (midi 60=C4). Логика — `js/ear.js`.
- Все тексты — RU **и** KZ. После правок: **`node tools/validate.js`**.

## Инструменты
- `node tools/validate.js` — проверка regions/eras/eartrainer/i18n + покрытие аудио.
- `python tools/fetch_audio.py` — скачать свободные (PD/CC0/CC BY) аудио-демо из
  Wikimedia Commons в `audio/` и заполнить `credits.js` (best-effort; чего нет — синтез).
- `python tools/fetch_world_tiles.py` — (при необходимости) догрузить тайлы мира.

## main.py — две строки, не трогать
```python
from product_core.shell import run
run(__file__)
```

## Запуск и сборка
```bash
python main.py                 # запуск (нужен pip install -e product-core)
node tools/validate.js         # проверка данных
python -m build .              # Windows + Android
python -m build . --windows    # только Windows
```
Локальная проверка контента без оболочки: статический http-сервер над `content/`
(в dev контент не шифруется). Контент-сервер шлёт `Cache-Control: no-store`.

## Definition of Done
- [x] три раздела (карта/лента/тренажёр) в одном окне, навигация, RU/KZ;
- [x] карта ≥20 традиций + углублённый Казахстан; лента Барокко→современность;
- [x] тренажёр: нота/интервал/аккорд + статистика; синтез Web Audio;
- [x] аудио гибрид: вшитые PD/CC0/CC-BY + синт-фолбэк, офлайн, раздел «Источники»;
- [x] тема «концертный тёмный»; `node tools/validate.js` → OK; консоль чистая;
- [x] защита включена (skip_activation:false, anti_copy, flag_secure), `_secret.py` v4;
- [x] `product_id=6`, вариант 0=music внесён в `product-core/ECOSYSTEM.md §7`;
- [ ] проверка вживую (сборка): без лицензии — активация; с лицензией — контент; чужая — отказ.
