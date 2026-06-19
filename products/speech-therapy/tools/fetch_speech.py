# -*- coding: utf-8 -*-
"""
Озвучка слов (TTS) → content/audio/<lang>_<slug>.mp3. slug = translit() как в js/audio.js.
Источник: Google Translate TTS (демо; быстро, естественные голоса RU/KZ). Лимиты →
троттлинг+ретраи. Чего не докачали — в рантайме озвучит системный TTS планшета.
Запуск: python tools/fetch_speech.py
"""
import os, re, time, urllib.parse, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "content", "data")
AUD = os.path.join(ROOT, "content", "audio")
HDR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}
TL = {"ru": "ru", "kz": "kk"}

TR = {"а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"e","ж":"zh","з":"z","и":"i","й":"y","к":"k","л":"l","м":"m","н":"n","о":"o","п":"p","р":"r","с":"s","т":"t","у":"u","ф":"f","х":"h","ц":"c","ч":"ch","ш":"sh","щ":"sch","ъ":"","ы":"y","ь":"","э":"e","ю":"yu","я":"ya"," ":"_","-":"_","ә":"ae","ғ":"gh","қ":"q","ң":"ng","ө":"oe","ұ":"uu","ү":"ue","һ":"hh","і":"ii"}
def translit(w):
    s = "".join(TR.get(c, "") for c in w.lower())
    return re.sub(r"_+", "_", s).strip("_")

def words(files):
    out = []
    for f in files:
        txt = open(os.path.join(DATA, f), encoding="utf-8").read()
        for m in re.finditer(r'word:"(.*?)"', txt):
            if m.group(1) not in out: out.append(m.group(1))
    return out

def tts(word, lang, tries=4):
    url = ("https://translate.google.com/translate_tts?ie=UTF-8&client=tw-ob&ttsspeed=0.8&tl="
           + TL[lang] + "&q=" + urllib.parse.quote(word))
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HDR), timeout=30) as r:
                data = r.read()
            if data[:3] == b"ID3" or len(data) > 1500:  # похоже на mp3
                return data
            raise ValueError("not audio")
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and k < tries - 1: time.sleep(3 * (k + 1)); continue
            raise
        except Exception:
            if k < tries - 1: time.sleep(2 * (k + 1)); continue
            raise
    return None

def main():
    os.makedirs(AUD, exist_ok=True)
    jobs = [("ru", ["sounds_ru.js", "game_ru.js"]), ("kz", ["sounds_kz.js", "game_kz.js"])]
    got = skip = err = 0
    for lang, files in jobs:
        for w in words(files):
            dst = os.path.join(AUD, "%s_%s.mp3" % (lang, translit(w)))
            if os.path.exists(dst) and os.path.getsize(dst) > 1000:
                skip += 1; continue
            try:
                data = tts(w, lang)
                if not data: raise ValueError("empty")
                with open(dst, "wb") as fh: fh.write(data)
                got += 1; print("OK ", lang, w)
                time.sleep(0.5)
            except Exception as ex:
                err += 1; print("ERR", lang, w, str(ex)[:60])
                time.sleep(0.4)
    print("\nИтог: озвучено %d, есть %d, не удалось %d (рантайм-фолбэк speechSynthesis)" % (got, skip, err))

if __name__ == "__main__":
    main()
