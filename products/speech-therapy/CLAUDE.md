# CLAUDE.md — Кабинет логопеда (игры для речи)

> Перед доработкой прочитай `product-core/ECOSYSTEM.md` (v4 Ed25519, webview2/Android).
> При сомнениях верен он и код в `product_core/`.

## Что это
- **slug / product_id:** `speech-therapy` / **7**; вариант **0 = speech**.
- **Архетип A (WebView). Основная платформа — Android-планшет** (engine `webview2` для
  Windows-dev/сборки; APK через `python -m build . --android`). `D:\Products\speech-therapy`.
- Три модуля (домашний экран → плитки), языки **RU + KZ**, тач-интерфейс:
  1. **Карточки звуков** — группы по проблемному звуку; буква + картинка (OpenMoji) +
     озвучка слова; свайп/стрелки, авто-озвучка.
  2. **Определи звук** — звучит слово, ребёнок выбирает звук (с/ш, р/л…); статистика.
  3. **Скороговорки** — текст с цветной подсветкой целевого звука; чтение вслух (+▶ образец).

## Технологии и факты ядра
- **Звук:** `js/audio.js` `SP.playWord(word,lang)` — играет вшитый клип
  `audio/<lang>_<slug>.(mp3|ogg)`; если файла нет — **`speechSynthesis`** (системный TTS
  планшета). Стоп-предыдущего. `SP.translit()` ОБЯЗАН совпадать с `tools/fetch_speech.py`
  (slug файла). `SP.emojiCode()` → имя файла OpenMoji.
- **Озвучка вшита (Azure Neural TTS):** RU и KZ запекаются `tools/fetch_speech.py` (Azure
  Cognitive Services, env `AZURE_SPEECH_KEY`/`AZURE_SPEECH_REGION`). Ударение RU — знак U+0301
  из карты `STRESS_RU` (Azure ru-RU реагирует). Azure **kk-KZ ударение НЕ перепозиционирует**
  (произносит по своей модели — финальный слог); проверено пробой. Рантайм-фолбэк — `speechSynthesis`.
- **Картинки:** OpenMoji (`content/images/<CODE>.svg`, единый стиль, CC BY-SA 4.0); карточка
  строит src из эмодзи; фолбэк — сам эмодзи символом.
- `_secret.py` (v4) — `python -m product_core.keygen embed 7` (⚠ `PYTHONIOENCODING=utf-8`).
- Android: `content/` → `assets/content/` (шифруется), отдаётся WebViewAssetLoader; mp3/ogg/svg
  работают офлайн. Путь сборки — ASCII (`D:\Products` ок).

## Структура контента
```
content/
├── index.html  app.css  app.js
├── assets/ fonts.css, fonts/ (Inter)        ├── images/ <CODE>.svg (OpenMoji)
├── audio/  <lang>_<slug>.mp3|ogg            ├── locales/i18n.js (window.I18N)
├── js/  audio.js(SP) · cards.js(Cards) · game.js(Game) · twisters.js(Twisters)
└── data/
    ├── sounds_ru.js / sounds_kz.js → SOUNDS_RU/KZ  (карточки: группы по звуку)
    ├── game_ru.js   / game_kz.js   → GAME_RU/KZ    (пары различения {word,ans})
    ├── twisters_ru.js / twisters_kz.js → TW_RU/KZ  ({text, sounds:[]})
    └── credits.js  → window.CREDITS (OpenMoji/Wikimedia/TTS)
```
Порядок в index.html: data/* → i18n → audio.js → **app.js** (window.APP) → cards/game/twisters.
`showView` при входе в модуль: первый раз `init()`, потом `relang()` (перерисовка под язык).

## Как добавить контент
- **Карточка:** объект в `sounds_<lang>.js`: `{word, emoji, pos:"н"/"с"/"к"}`. Бери слово,
  у которого ЕСТЬ эмодзи (→ картинка). После — `node tools/validate.js`, затем
  `python tools/fetch_images.py` (картинка) и `tools/fetch_speech.py` (озвучка).
- **Игра:** в `game_<lang>.js` блок `{a,b,items:[{word,ans}]}` (ans ∈ {a,b}).
- **Скороговорка:** в `twisters_<lang>.js` `{text, sounds:["с","ш"]}` (буквы для подсветки).

## Инструменты
- `node tools/validate.js` — поля + RU/KZ-паритет i18n + покрытие картинок/озвучки.
- `python tools/fetch_images.py` — OpenMoji по эмодзи (⚠ `PYTHONIOENCODING=utf-8`).
- `python tools/fetch_speech.py` — TTS озвучка RU/KZ (⚠ utf-8; Google не умеет kk).
- `python tools/fetch_kz_commons.py` — native KZ-озвучка с Wikimedia (где есть).

## Запуск и сборка
```bash
python main.py                       # Windows-окно (нужен pip install -e product-core)
python -m http.server -d content     # быстрый просмотр в браузере
node tools/validate.js
python -m build . --android          # APK для планшета (JDK17 + Android SDK)
```

## Definition of Done
- [x] 3 модуля + домашний экран, RU+KZ, тач-планшет;
- [x] карточки (OpenMoji + озвучка), группы по звукам RU/KZ;
- [x] игра на различение + статистика; скороговорки с подсветкой;
- [x] озвучка вшита (RU TTS, KZ native/fallback) + рантайм `speechSynthesis`; картинки 76/76;
- [x] `node tools/validate.js` → OK; консоль чистая; защита `_secret.py` v4;
- [x] `product_id=7`, вариант 0=speech в `ECOSYSTEM.md §7`;
- [ ] Android APK собрать и проверить на планшете (офлайн, звук+картинки+фолбэк).
```
