# -*- coding: utf-8 -*-
"""
Озвучка слов и скороговорок РЕАЛЬНЫМ нейросинтезом — Azure Cognitive Services (TTS).
Рендерит в content/audio/<lang>_<slug>.mp3; slug = translit() как в js/audio.js.

УДАРЕНИЕ:
  • Русский — управляется знаком U+0301 (комбинируемый акут) после ударной гласной.
    Берём из карты STRESS_RU (ниже) либо из поля say:"..." в данных. Проверено: Azure
    ru-RU реагирует (за́мок ≠ замо́к ≠ замок — разное аудио).
  • Казахский — Azure НЕ реагирует ни на знак ударения, ни на <phoneme> (проверено:
    а́лма == алма́ == алма, байт-в-байт). Голос kk-KZ произносит по своей модели
    (по правилу — ударение на последний слог). Поле say для kz можно использовать
    разве что для замены написания; саму позицию ударения переставить нельзя.

Что озвучивается:
  • слова карточек  — data/sounds_<lang>.js  → <lang>_<translit(word)>.mp3
  • слова игры      — data/game_<lang>.js    → <lang>_<translit(word)>.mp3
  • скороговорки    — data/twisters_<lang>.js → <lang>_tw<N>.mp3  (N — номер по порядку)

Текст для TTS = say из объекта данных → иначе STRESS_RU[word] (для ru) → иначе сам word.

Требуется: AZURE_SPEECH_KEY, AZURE_SPEECH_REGION (напр. eastus).
Запуск (⚠ PYTHONUTF8=1):
  python tools/fetch_speech.py            # озвучить недостающее
  python tools/fetch_speech.py --force    # перезаписать всё
  python tools/fetch_speech.py --only ru  # только русский
"""
import argparse
import os
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "content", "data")
AUD = os.path.join(ROOT, "content", "audio")

LOCALE = {"ru": "ru-RU", "kz": "kk-KZ"}
DEFAULT_VOICE = {"ru": "ru-RU-SvetlanaNeural", "kz": "kk-KZ-AigulNeural"}

AC = "́"  # combining acute accent

# Ударения для русского: знак "+" ставится СРАЗУ после ударной гласной,
# в коде "+" → U+0301 (комбинируемый акут). Azure ru-RU реагирует на него.
# Только многосложные; моносложные и слова с «ё» не нуждаются (ё всегда ударная).
# «замок» → «замо́к», потому что на карточке 🔒 (lock), а не крепость.
_STRESS_RU_RAW = {
    "рыба": "ры+ба", "ракета": "раке+та", "роза": "ро+за", "радуга": "ра+дуга",
    "корова": "коро+ва", "топор": "топо+р", "рука": "рука+", "баран": "бара+н",
    "ведро": "ведро+", "арбуз": "арбу+з", "крокодил": "крокоди+л", "комар": "кома+р",
    "луна": "луна+", "лампа": "ла+мпа", "лимон": "лимо+н", "лиса": "лиса+", "лошадь": "ло+шадь",
    "лодка": "ло+дка", "белка": "бе+лка", "яблоко": "я+блоко", "клубника": "клубни+ка",
    "облако": "о+блако", "ложка": "ло+жка", "вилка": "ви+лка", "пчела": "пчела+",
    "солнце": "со+лнце", "собака": "соба+ка", "сова": "сова+", "автобус": "авто+бус",
    "сумка": "су+мка", "снеговик": "снегови+к", "санки": "са+нки", "сосна": "сосна+",
    "носки": "носки+", "апельсин": "апельси+н", "маска": "ма+ска", "миска": "ми+ска",
    "шапка": "ша+пка", "кошка": "ко+шка", "машина": "маши+на", "груша": "гру+ша",
    "шуба": "шу+ба", "шорты": "шо+рты", "шахматы": "ша+хматы", "мишка": "ми+шка",
    "лягушка": "лягу+шка", "ромашка": "рома+шка", "вишня": "ви+шня", "карандаш": "каранда+ш",
    "замок": "замо+к", "заяц": "за+яц", "звезда": "звезда+", "зебра": "зе+бра", "коза": "коза+",
    "зубы": "зу+бы", "зеркало": "зе+ркало", "зонтик": "зо+нтик", "ваза": "ва+за",
    "гнездо": "гнездо+", "корзина": "корзи+на", "глаза": "глаза+",
    "жираф": "жира+ф", "ножницы": "но+жницы", "лыжи": "лы+жи", "снежинка": "снежи+нка",
    "пирожок": "пирожо+к", "баклажан": "баклажа+н",
    "цветок": "цвето+к", "яйцо": "яйцо+", "курица": "ку+рица", "кольцо": "кольцо+",
    "огурец": "огуре+ц", "овца": "овца+", "птица": "пти+ца", "гусеница": "гу+сеница",
    "лестница": "ле+стница", "перец": "пе+рец", "дворец": "дворе+ц",
    "часы": "часы+", "чашка": "ча+шка", "бабочка": "ба+бочка", "очки": "очки+",
    "чайник": "ча+йник", "червяк": "червя+к", "черепаха": "черепа+ха", "чеснок": "чесно+к",
    "чемодан": "чемода+н", "бочка": "бо+чка", "удочка": "у+дочка", "печенье": "пече+нье",
    "щенок": "щено+к", "ящик": "я+щик", "овощи": "о+вощи", "щука": "щу+ка", "ящерица": "я+щерица",
    "банан": "бана+н", "ботинки": "боти+нки", "букет": "буке+т", "бусы": "бу+сы",
    "банка": "ба+нка", "барабан": "бараба+н",
    "дерево": "де+рево", "диван": "дива+н", "дыня": "ды+ня", "дельфин": "дельфи+н",
    "дракон": "драко+н", "девочка": "де+вочка",
    "книга": "кни+га", "конфета": "конфе+та", "кенгуру": "кенгуру+", "кубик": "ку+бик",
    "корабль": "кора+бль",
    "гора": "гора+", "голубь": "го+лубь", "гитара": "гита+ра", "город": "го+род", "губы": "гу+бы",
    "молоко": "молоко+", "морковь": "морко+вь", "муравей": "мураве+й", "молоток": "молото+к",
    "мороженое": "моро+женое", "мясо": "мя+со",
    "паук": "пау+к", "петух": "пету+х", "пила": "пила+", "пирог": "пиро+г", "попугай": "попуга+й",
    "поезд": "по+езд", "пингвин": "пингви+н", "подарок": "пода+рок",
    "телефон": "телефо+н", "тыква": "ты+ква", "тарелка": "таре+лка", "туфли": "ту+фли",
    "термометр": "термо+метр", "тюльпан": "тюльпа+н",
    "помидор": "помидо+р", "ананас": "анана+с", "медвежонок": "медвежо+нок",
}
STRESS_RU = {w: f.replace("+", AC) for w, f in _STRESS_RU_RAW.items()}

# translit ДОЛЖЕН совпадать с TR в content/js/audio.js
TR = {"а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"e","ж":"zh","з":"z","и":"i",
      "й":"y","к":"k","л":"l","м":"m","н":"n","о":"o","п":"p","р":"r","с":"s","т":"t",
      "у":"u","ф":"f","х":"h","ц":"c","ч":"ch","ш":"sh","щ":"sch","ъ":"","ы":"y","ь":"",
      "э":"e","ю":"yu","я":"ya"," ":"_","-":"_",
      "ә":"ae","ғ":"gh","қ":"q","ң":"ng","ө":"oe","ұ":"uu","ү":"ue","һ":"hh","і":"ii"}


def translit(w):
    w = w.replace(AC, "")  # убрать знак ударения перед транслитерацией
    s = "".join(TR.get(c, "") for c in w.lower())
    return re.sub(r"_+", "_", s).strip("_")


def _read(fname):
    p = os.path.join(DATA, fname)
    return open(p, encoding="utf-8").read() if os.path.exists(p) else ""


def _say_of(obj_src, word):
    """Текст для TTS: say из объекта → STRESS_RU → сам word."""
    ms = re.search(r'say\s*:\s*"(.*?)"', obj_src)
    if ms:
        return ms.group(1)
    return STRESS_RU.get(word, word)


def entries(files):
    """Объекты с word:"..." → [(word, say_text)] в порядке появления, без дублей."""
    out, seen = [], set()
    for f in files:
        for obj in re.finditer(r"\{[^{}]*\}", _read(f)):
            s = obj.group(0)
            mw = re.search(r'word\s*:\s*"(.*?)"', s)
            if not mw:
                continue
            w = mw.group(1).strip()
            if not w or w in seen:
                continue
            seen.add(w)
            out.append((w, _say_of(s, w)))
    return out


def twisters(fname):
    """Скороговорки text:"..." → [(slug, say_text)] по порядку."""
    out = []
    for obj in re.finditer(r"\{[^{}]*\}", _read(fname)):
        s = obj.group(0)
        mt = re.search(r'text\s*:\s*"(.*?)"', s)
        if not mt:
            continue
        t = mt.group(1).strip()
        if not t:
            continue
        ms = re.search(r'say\s*:\s*"(.*?)"', s)
        out.append(("tw%d" % (len(out) + 1), ms.group(1) if ms else t))
    return out


def _ssml(text, locale, voice, rate):
    esc = (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
               .replace('"', "&quot;").replace("'", "&apos;"))
    return ("<speak version='1.0' xml:lang='%s'>"
            "<voice xml:lang='%s' name='%s'>"
            "<prosody rate='%s'>%s</prosody>"
            "</voice></speak>" % (locale, locale, voice, rate, esc))


def synth(text, locale, voice, rate, key, region, tries=4):
    url = "https://%s.tts.speech.microsoft.com/cognitiveservices/v1" % region
    body = _ssml(text, locale, voice, rate).encode("utf-8")
    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": "audio-48khz-96kbitrate-mono-mp3",
        "User-Agent": "oilab-speech-therapy",
    }
    for k in range(tries):
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=40) as r:
                data = r.read()
            if data[:3] == b"ID3" or len(data) > 1200:
                return data
            raise ValueError("ответ не похож на аудио (%d байт)" % len(data))
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", "ignore")[:200]
            except Exception:
                pass
            if e.code in (429, 503) and k < tries - 1:
                time.sleep(3 * (k + 1)); continue
            raise RuntimeError("HTTP %s %s" % (e.code, detail))
        except Exception:
            if k < tries - 1:
                time.sleep(2 * (k + 1)); continue
            raise
    return None


def main():
    ap = argparse.ArgumentParser(description="Azure Neural TTS → content/audio/*.mp3")
    ap.add_argument("--force", action="store_true", help="перезаписать существующие клипы")
    ap.add_argument("--only", choices=["ru", "kz"], help="только один язык")
    ap.add_argument("--voice-ru", default=os.environ.get("AZURE_VOICE_RU", DEFAULT_VOICE["ru"]))
    ap.add_argument("--voice-kz", default=os.environ.get("AZURE_VOICE_KZ", DEFAULT_VOICE["kz"]))
    ap.add_argument("--rate", default="-12%", help="темп речи")
    args = ap.parse_args()

    key = os.environ.get("AZURE_SPEECH_KEY", "").strip()
    region = os.environ.get("AZURE_SPEECH_REGION", "").strip()
    if not key or not region:
        sys.exit("❌ Нужны переменные окружения AZURE_SPEECH_KEY и AZURE_SPEECH_REGION.")

    voice = {"ru": args.voice_ru, "kz": args.voice_kz}
    langs = [args.only] if args.only else ["ru", "kz"]
    os.makedirs(AUD, exist_ok=True)

    jobs = []  # (lang, slug, tts_text)
    for lang in langs:
        for w, say in entries(["sounds_%s.js" % lang, "game_%s.js" % lang]):
            jobs.append((lang, translit(w), say))
        for slug, say in twisters("twisters_%s.js" % lang):
            jobs.append((lang, slug, say))

    print("Голоса: RU=%s  KZ=%s  | темп %s | заданий: %d"
          % (voice["ru"], voice["kz"], args.rate, len(jobs)))
    got = skip = err = 0
    for lang, slug, text in jobs:
        dst = os.path.join(AUD, "%s_%s.mp3" % (lang, slug))
        if not args.force and os.path.exists(dst) and os.path.getsize(dst) > 1000:
            skip += 1; continue
        try:
            data = synth(text, LOCALE[lang], voice[lang], args.rate, key, region)
            if not data:
                raise ValueError("пусто")
            with open(dst, "wb") as fh:
                fh.write(data)
            got += 1
            mark = " *" if text.replace(AC, "") != text else ""   # помечаем заданное ударение
            print("OK  %s  %-22s %s%s" % (lang, slug, text[:40], mark))
            time.sleep(0.25)
        except Exception as ex:
            err += 1
            print("ERR %s  %-22s %s" % (lang, slug, str(ex)[:80]))
            time.sleep(0.4)

    print("\nИтог: озвучено %d, пропущено(уже есть) %d, ошибок %d" % (got, skip, err))
    if err:
        sys.exit(1)


if __name__ == "__main__":
    main()
