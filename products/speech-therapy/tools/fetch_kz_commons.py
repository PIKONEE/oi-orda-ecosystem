# -*- coding: utf-8 -*-
"""
Казахская озвучка из Wikimedia Commons (native-записи Kk-<слово>.ogg, свободные),
т.к. Google TTS не поддерживает kk. Качаем напрямую через медиа-CDN
upload.wikimedia.org (md5-путь) — в обход rate-limited API. Чего нет → рантайм TTS.
Запуск: python tools/fetch_kz_commons.py
"""
import hashlib, os, re, time, urllib.parse, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "content", "data")
AUD = os.path.join(ROOT, "content", "audio")
HDR = {"User-Agent": "OiOrda-SpeechTherapy/1.0 (educational)"}
TR = {"а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"e","ж":"zh","з":"z","и":"i","й":"y","к":"k","л":"l","м":"m","н":"n","о":"o","п":"p","р":"r","с":"s","т":"t","у":"u","ф":"f","х":"h","ц":"c","ч":"ch","ш":"sh","щ":"sch","ъ":"","ы":"y","ь":"","э":"e","ю":"yu","я":"ya"," ":"_","-":"_","ә":"ae","ғ":"gh","қ":"q","ң":"ng","ө":"oe","ұ":"uu","ү":"ue","һ":"hh","і":"ii"}
def translit(w): return re.sub(r"_+","_","".join(TR.get(c,"") for c in w.lower())).strip("_")

def words():
    out = []
    for f in ("sounds_kz.js", "game_kz.js"):
        for m in re.finditer(r'word:"(.*?)"', open(os.path.join(DATA, f), encoding="utf-8").read()):
            if m.group(1) not in out: out.append(m.group(1))
    return out

def upload_url(fn):
    name = fn.replace(" ", "_")
    h = hashlib.md5(name.encode("utf-8")).hexdigest()
    return "https://upload.wikimedia.org/wikipedia/commons/%s/%s/%s" % (h[0], h[:2], urllib.parse.quote(name))

def grab(fn, tries=3):
    for k in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(upload_url(fn), headers=HDR), timeout=40).read()
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            if e.code in (429, 503) and k < tries - 1: time.sleep(4 * (k + 1)); continue
            return None
        except Exception:
            if k < tries - 1: time.sleep(3 * (k + 1)); continue
            return None
    return None

def main():
    os.makedirs(AUD, exist_ok=True)
    got = miss = 0
    for w in words():
        dst = os.path.join(AUD, "kz_" + translit(w) + ".ogg")
        if os.path.exists(dst) and os.path.getsize(dst) > 1000: continue
        data = None
        for fn in ("Kk-%s.ogg" % w, "Kk-%s.ogg" % (w[:1].upper() + w[1:])):  # вариант с заглавной
            data = grab(fn)
            if data and len(data) > 1000: break
            time.sleep(0.4)
        if data and len(data) > 1000:
            with open(dst, "wb") as fh: fh.write(data); got += 1; print("OK ", w)
        else:
            miss += 1; print("--  нет:", w)
    print("\nИтог: KZ native озвучено %d, нет %d (рантайм-фолбэк speechSynthesis)" % (got, miss))

if __name__ == "__main__":
    main()
