# -*- coding: utf-8 -*-
"""
Качает картинки OpenMoji (единый стиль, CC BY-SA 4.0) для всех эмодзи из карточек
в content/images/<CODE>.svg. CODE = кодпоинты эмодзи (без FE0F), HEX, через '-'.
Запуск: python tools/fetch_images.py
"""
import os, re, time, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "content", "data")
IMG = os.path.join(ROOT, "content", "images")
RAW = "https://raw.githubusercontent.com/hfg-gmuend/openmoji/master/color/svg/{}.svg"
HDR = {"User-Agent": "OiOrda-SpeechTherapy/1.0 (educational)"}

def emojis():
    out = set()
    for f in ("sounds_ru.js", "sounds_kz.js"):
        txt = open(os.path.join(DATA, f), encoding="utf-8").read()
        for m in re.finditer(r'emoji:"(.*?)"', txt):
            out.add(m.group(1))
    return out

def code(e):
    return "-".join("%X" % ord(c) for c in e if ord(c) != 0xFE0F)

def main():
    os.makedirs(IMG, exist_ok=True)
    got = skip = err = 0
    for e in sorted(emojis()):
        c = code(e); dst = os.path.join(IMG, c + ".svg")
        if os.path.exists(dst) and os.path.getsize(dst) > 100:
            skip += 1; continue
        try:
            data = urllib.request.urlopen(urllib.request.Request(RAW.format(c), headers=HDR), timeout=40).read()
            if len(data) < 100: raise ValueError("too small")
            with open(dst, "wb") as fh: fh.write(data)
            got += 1; print("OK ", e, c)
            time.sleep(0.15)
        except Exception as ex:
            err += 1; print("ERR", e, c, ex)
    print("\nИтог: скачано %d, есть %d, ошибок %d" % (got, skip, err))

if __name__ == "__main__":
    main()
