# -*- coding: utf-8 -*-
"""
Прямое скачивание ПРОВЕРЕННЫХ свободных файлов из Wikimedia Commons по точным
именам через Special:FilePath (CDN, в обход rate-limited API). Имена/лицензии
подтверждены предыдущими запусками fetch_audio.py. Дополняет content/audio/ и
content/data/credits.js (мерж, атрибуция сохраняется). Запуск: python tools/fetch_known.py
"""
import hashlib, json, os, re, time, urllib.parse, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIO = os.path.join(ROOT, "content", "audio")
CREDITS = os.path.join(ROOT, "content", "data", "credits.js")
HDR = {"User-Agent": "OiOrda-MusicEncyclopedia/1.0 (educational offline bundle)"}

# key, точное имя файла на Commons, лицензия, автор, подпись
FILES = [
  ("era_classical", "Mozart; Piano Concerto No. 27, 3. Allegro.ogg", "Public domain",
   "Wolfgang Amadeus Mozart", "Классицизм — В. А. Моцарт"),
  ("era_modern20", "Debussy-Children's Corner-Doctorial Etude, Piano pupil Jinghui Jin (Kim).ogg",
   "CC BY-SA 4.0", "Jason M. C., Han", "XX век — К. Дебюсси"),
  ("instr_sitar", "Sitar sample yaman.ogg", "CC BY-SA 3.0", "Tito Dutta", "Ситар"),
  ("instr_samba", "Extrait d'une Samba Funk jouée par une batucada.ogg", "CC BY 3.0",
   "association Pulsabatouk", "Самба"),
  ("instr_koto", "Koto performance.ogg", "CC BY 3.0", "Torsodog", "Кото"),
  ("instr_didgeridoo", "Didgeridoo sound.ogg", "CC BY-SA 4.0", "Cassa342", "Диджериду"),
]

def load_prior():
    try:
        m = re.search(r"window\.CREDITS\s*=\s*(\{.*\});", open(CREDITS, encoding="utf-8").read(), re.S)
        if m: return {it["key"]: it for it in json.loads(m.group(1)).get("items", [])}
    except Exception: pass
    return {}

def have(key):
    return any(os.path.exists(os.path.join(AUDIO, key + "." + e)) for e in ("mp3", "ogg", "wav"))

def upload_url(fn):
    # прямой URL медиа-CDN upload.wikimedia.org (отдельный кластер, не rate-limited как вики-хост)
    name = fn.replace(" ", "_")
    h = hashlib.md5(name.encode("utf-8")).hexdigest()
    return "https://upload.wikimedia.org/wikipedia/commons/%s/%s/%s" % (h[0], h[:2], urllib.parse.quote(name))

def download(fn, tries=4):
    url = upload_url(fn)
    for k in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=HDR), timeout=90).read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and k < tries - 1: time.sleep(5 * (k + 1)); continue
            raise
        except Exception:
            if k < tries - 1: time.sleep(4 * (k + 1)); continue
            raise

def main():
    os.makedirs(AUDIO, exist_ok=True)
    cred = load_prior()
    for key, fn, lic, author, label in FILES:
        if have(key):
            print("have", key); continue
        try:
            data = download(fn)
            if not data or len(data) < 5000: print("tiny", key); continue
            with open(os.path.join(AUDIO, key + ".ogg"), "wb") as f: f.write(data)
            page = "https://commons.wikimedia.org/wiki/File:" + urllib.parse.quote(fn.replace(" ", "_"))
            cred[key] = {"key":key, "titleRu":label, "titleKz":label,
                         "source":author + " — " + page, "license":lic}
            print("OK ", key, len(data))
        except Exception as e:
            print("FAIL", key, e)
    note_ru = ("Музыкальные фрагменты — из Wikimedia Commons под свободными лицензиями "
               "(Public Domain / CC0 / CC BY). Где записи нет, звук синтезируется программой.")
    note_kz = ("Музыкалық үзінділер — Wikimedia Commons-тан еркін лицензиялармен "
               "(Public Domain / CC0 / CC BY). Жазба болмаған жерде дыбыс синтезделеді.")
    items = list(cred.values())
    out = ("/* Сгенерировано tools/fetch_audio.py / fetch_known.py — только свободные лицензии. */\n"
           "window.CREDITS=" + json.dumps({"noteRu":note_ru, "noteKz":note_kz, "items":items},
                                          ensure_ascii=False, indent=1) + ";\n")
    with open(CREDITS, "w", encoding="utf-8") as f: f.write(out)
    print("\nВсего в credits:", len(items))

if __name__ == "__main__":
    main()
