# -*- coding: utf-8 -*-
"""
Сборочный шаг: качает короткие аудио-демо из Wikimedia Commons СТРОГО под
свободными лицензиями (Public Domain / CC0 / CC BY / CC BY-SA) в content/audio/
и заполняет content/data/credits.js (атрибуция). Где не нашлось — синтез-фолбэк.
Один комбинированный запрос на ключ (generator=search + imageinfo) → меньше шансов
на 429. Длинные записи проигрыватель сам обрезает до ~13 c. Запуск:
    python tools/fetch_audio.py
"""
import json, os, re, time, urllib.parse, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIO = os.path.join(ROOT, "content", "audio")
CREDITS = os.path.join(ROOT, "content", "data", "credits.js")
API = "https://commons.wikimedia.org/w/api.php"
HDR = {"User-Agent": "OiOrda-MusicEncyclopedia/1.0 (educational offline bundle; contact: oi-orda)"}
MIN_BYTES, MAX_BYTES = 6000, 6_500_000
MIME_EXT = {"audio/ogg":"ogg", "application/ogg":"ogg", "audio/mpeg":"mp3", "audio/wav":"wav", "audio/x-wav":"wav"}
OK_LIC = re.compile(r"(public domain|cc0|cc[\s-]?by)", re.I)
BAD_LIC = re.compile(r"(non[\s-]?free|fair use|by-nc|by-nd)", re.I)

_last = [0.0]
def _throttle(gap=2.5):
    dt = time.time() - _last[0]
    if dt < gap: time.sleep(gap - dt)
    _last[0] = time.time()

def api(params, tries=8):
    params = dict(params); params.update({"format":"json", "action":"query", "maxlag":"5"})
    url = API + "?" + urllib.parse.urlencode(params)
    for k in range(tries):
        _throttle(3.0)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HDR), timeout=45) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and k < tries - 1:
                ra = e.headers.get("Retry-After")
                time.sleep(float(ra) if (ra and str(ra).isdigit()) else min(30, 5 * (k + 1))); continue
            raise
        except Exception:
            if k < tries - 1: time.sleep(min(30, 5 * (k + 1))); continue
            raise
    return {}

def load_prior():
    """Уже записанные источники — чтобы не терять атрибуцию при повторных запусках."""
    try:
        txt = open(CREDITS, encoding="utf-8").read()
        m = re.search(r"window\.CREDITS\s*=\s*(\{.*\});", txt, re.S)
        if m:
            return {it["key"]: it for it in json.loads(m.group(1)).get("items", [])}
    except Exception:
        pass
    return {}

def candidates(query):
    d = api({"generator":"search", "gsrsearch":query, "gsrnamespace":6, "gsrlimit":10,
             "prop":"imageinfo", "iiprop":"url|size|mime|extmetadata"})
    pages = list(d.get("query", {}).get("pages", {}).values())
    out = []
    for p in pages:
        ii = (p.get("imageinfo") or [None])[0]
        if ii: out.append((p.get("title", ""), ii))
    out.sort(key=lambda t: int(t[1].get("size", 9e9)))   # сначала короткие/маленькие
    return out

def license_of(ii):
    em = ii.get("extmetadata", {})
    txt = " ".join(str(em.get(k, {}).get("value", "")) for k in ("LicenseShortName","License","UsageTerms"))
    if BAD_LIC.search(txt): return None
    if OK_LIC.search(txt): return (em.get("LicenseShortName", {}).get("value") or "free").strip()
    return None

def author_of(ii):
    a = re.sub(r"<[^>]+>", "", ii.get("extmetadata", {}).get("Artist", {}).get("value", "")).strip()
    return (a[:80] or "Wikimedia Commons")

def already(key):
    return any(os.path.exists(os.path.join(AUDIO, key + "." + e)) for e in ("mp3","ogg","wav"))

def fetch_one(key, query, prior):
    if already(key):                       # файл есть → сохраняем прежнюю атрибуцию
        return prior.get(key)
    try: cands = candidates(query)
    except Exception: return None
    for title, ii in cands:
        try:
            ext = MIME_EXT.get(ii.get("mime", "")); sz = int(ii.get("size", 0))
            if not ext or sz < MIN_BYTES or sz > MAX_BYTES: continue
            lic = license_of(ii)
            if not lic: continue
            data = urllib.request.urlopen(urllib.request.Request(ii["url"], headers=HDR), timeout=90).read()
            if len(data) > MAX_BYTES: continue
            with open(os.path.join(AUDIO, key + "." + ext), "wb") as f: f.write(data)
            page = "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))
            return {"key":key, "titleRu":label(key), "titleKz":label(key),
                    "source":author_of(ii) + " — " + page, "license":lic}
        except Exception:
            continue
    return None

TARGETS = [
  # эпохи (самое важное — лента истории; для XX-авангарда/современности PD-записей нет → синтез)
  ("era_medieval","Gregorian chant Kyrie"), ("era_renaissance","Renaissance lute"),
  ("era_baroque","Bach harpsichord"), ("era_classical","Mozart piano sonata"),
  ("era_romantic","Chopin nocturne"), ("era_modern20","Debussy piano"),
  ("era_jazz","Dixieland jazz 1917"),
  # инструменты на карте
  ("instr_dombyra","dombra kazakh"), ("instr_sitar","sitar raga"), ("instr_djembe","djembe"),
  ("instr_samba","samba"), ("instr_oud","oud taqsim"), ("instr_saz","baglama saz"),
  ("instr_tar","tar Persian music"), ("instr_guzheng","guzheng"), ("instr_koto","koto"),
  ("instr_gayageum","gayageum"), ("instr_gamelan","gamelan"), ("instr_siku","siku panpipes"),
  ("instr_clave","son cubano"), ("instr_flamenco","flamenco guitar"),
  ("instr_balkanbrass","Balkan brass band"), ("instr_duduk","duduk"),
  ("instr_fiddle","Irish fiddle reel"), ("instr_balalaika","balalaika"),
  ("instr_hardanger","hardanger fiddle"), ("instr_blues","blues guitar"),
  ("instr_morinkhuur","morin khuur"), ("instr_didgeridoo","didgeridoo"), ("instr_ukulele","ukulele"),
]
LABELS = {
  "era_medieval":"Средневековье — григорианский хорал", "era_renaissance":"Возрождение — Палестрина",
  "era_baroque":"Барокко — И. С. Бах", "era_classical":"Классицизм — В. А. Моцарт",
  "era_romantic":"Романтизм — Ф. Шопен", "era_modern20":"XX век — К. Дебюсси",
  "era_jazz":"Джаз — ранние записи",
}

def label(key):
    return LABELS.get(key, key.replace("instr_","").replace("_"," ").title())

def main():
    os.makedirs(AUDIO, exist_ok=True)
    prior = load_prior()
    items, got = [], 0
    for key, q in TARGETS:
        it = fetch_one(key, q, prior)
        if it:
            got += 1; items.append(it); print("OK  ", key, "->", it.get("license"))
        else:
            print("skip", key, "(синтез-фолбэк)")
    note_ru = ("Музыкальные фрагменты — из Wikimedia Commons под свободными лицензиями "
               "(Public Domain / CC0 / CC BY). Где записи нет, звук синтезируется программой.")
    note_kz = ("Музыкалық үзінділер — Wikimedia Commons-тан еркін лицензиялармен "
               "(Public Domain / CC0 / CC BY). Жазба болмаған жерде дыбыс синтезделеді.")
    out = ("/* Автоматически сгенерировано tools/fetch_audio.py — только свободные лицензии. */\n"
           "window.CREDITS=" + json.dumps({"noteRu":note_ru, "noteKz":note_kz, "items":items},
                                          ensure_ascii=False, indent=1) + ";\n")
    with open(CREDITS, "w", encoding="utf-8") as f: f.write(out)
    print("\nИтог: вшито/есть %d из %d. credits.js обновлён." % (got, len(TARGETS)))

if __name__ == "__main__":
    main()
