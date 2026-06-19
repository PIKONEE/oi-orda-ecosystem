# -*- coding: utf-8 -*-
"""
Резервный источник аудио — Internet Archive (archive.org). Отдельный хост, не
блокирует ботов как Wikimedia. Берём ТОЛЬКО свободные элементы (licenseurl с
publicdomain/creativecommons). Дополняет content/audio/ и credits.js (мерж).
Проигрыватель сам обрезает до ~13 c. Запуск: python tools/fetch_ia.py
"""
import json, os, re, time, urllib.parse, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIO = os.path.join(ROOT, "content", "audio")
CREDITS = os.path.join(ROOT, "content", "data", "credits.js")
HDR = {"User-Agent": "OiOrda-MusicEncyclopedia/1.0 (educational offline bundle)"}
MIN_B, MAX_B = 40000, 6_500_000

def ok_license(url):
    """Принимаем только по-настоящему свободные: PD/CC0/CC BY/CC BY-SA. NC/ND — НЕТ."""
    u = (url or "").lower()
    if "publicdomain" in u or "/zero/" in u or "cc0" in u:
        return "Public domain / CC0"
    if "creativecommons" in u:
        if "-nc" in u or "-nd" in u or "/nc" in u or "/nd" in u: return None
        if "by-sa" in u: return "CC BY-SA"
        if "by" in u:    return "CC BY"
    return None

def get(url, tries=4):
    for k in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=HDR), timeout=60).read()
        except Exception:
            if k < tries - 1: time.sleep(2 * (k + 1)); continue
            raise

def search(q):
    url = ("https://archive.org/advancedsearch.php?q=" +
           urllib.parse.quote(q + " AND mediatype:(audio)") +
           "&fl[]=identifier&fl[]=licenseurl&fl[]=title&rows=18&output=json")
    d = json.loads(get(url))
    return d.get("response", {}).get("docs", [])

def pick_file(ident):
    meta = json.loads(get("https://archive.org/metadata/" + urllib.parse.quote(ident)))
    files = meta.get("files", [])
    cand = []
    for f in files:
        n = f.get("name", ""); fmt = (f.get("format", "") or "").lower()
        if not (n.lower().endswith(".mp3") or n.lower().endswith(".ogg")): continue
        try: sz = int(f.get("size", 0))
        except: sz = 0
        if sz < MIN_B or sz > MAX_B: continue
        cand.append((sz, n))
    cand.sort()
    return cand[0][1] if cand else None

def already(key):
    return any(os.path.exists(os.path.join(AUDIO, key + "." + e)) for e in ("mp3","ogg","wav"))

def load_prior():
    try:
        m = re.search(r"window\.CREDITS\s*=\s*(\{.*\});", open(CREDITS, encoding="utf-8").read(), re.S)
        if m: return {it["key"]: it for it in json.loads(m.group(1)).get("items", [])}
    except Exception: pass
    return {}

def fetch_one(key, query):
    for doc in search(query):
        licname = ok_license(doc.get("licenseurl", ""))
        if not licname: continue
        ident = doc.get("identifier")
        try:
            name = pick_file(ident)
            if not name: continue
            ext = ".mp3" if name.lower().endswith(".mp3") else ".ogg"
            url = "https://archive.org/download/" + urllib.parse.quote(ident) + "/" + urllib.parse.quote(name)
            data = get(url)
            if not data or len(data) < MIN_B or len(data) > MAX_B: continue
            with open(os.path.join(AUDIO, key + ext), "wb") as f: f.write(data)
            page = "https://archive.org/details/" + ident
            return {"key":key, "license":licname, "source":(doc.get("title") or ident) + " — " + page}
        except Exception:
            continue
    return None

TARGETS = [
  ("era_classical", "Mozart piano sonata", "Классицизм — В. А. Моцарт"),
  ("era_modern20", "Debussy", "XX век — К. Дебюсси"),
  ("era_renaissance", "Palestrina", "Возрождение — Палестрина"),
  ("instr_oud", "oud arabic", "Уд"),
  ("instr_flamenco", "flamenco guitar", "Фламенко"),
  ("instr_balalaika", "balalaika", "Балалайка"),
  ("instr_sitar", "sitar raga", "Ситар"),
  ("instr_tar", "Persian tar", "Тар"),
  ("instr_duduk", "duduk", "Дудук"),
  ("instr_samba", "samba bateria", "Самба"),
  ("instr_blues", "delta blues guitar", "Блюз"),
  ("instr_djembe", "djembe percussion", "Джембе"),
]

def main():
    os.makedirs(AUDIO, exist_ok=True)
    cred = load_prior()
    for key, q, label in TARGETS:
        if already(key): print("have", key); continue
        try:
            res = fetch_one(key, q)
        except Exception as e:
            res = None; print("err", key, e)
        if res:
            cred[key] = {"key":key, "titleRu":label, "titleKz":label,
                         "source":res["source"], "license":res["license"]}
            print("OK ", key, "->", res["license"])
        else:
            print("skip", key)
    note_ru = ("Музыкальные фрагменты — из Wikimedia Commons и Internet Archive под свободными "
               "лицензиями (Public Domain / CC0 / CC BY). Где записи нет, звук синтезируется программой.")
    note_kz = ("Музыкалық үзінділер — Wikimedia Commons пен Internet Archive-тен еркін лицензиялармен "
               "(Public Domain / CC0 / CC BY). Жазба болмаған жерде дыбыс синтезделеді.")
    items = list(cred.values())
    out = ("/* Сгенерировано fetch_audio.py / fetch_known.py / fetch_ia.py — только свободные лицензии. */\n"
           "window.CREDITS=" + json.dumps({"noteRu":note_ru, "noteKz":note_kz, "items":items},
                                          ensure_ascii=False, indent=1) + ";\n")
    with open(CREDITS, "w", encoding="utf-8") as f: f.write(out)
    print("\nВсего в credits:", len(items))

if __name__ == "__main__":
    main()
