# -*- coding: utf-8 -*-
"""
Импорт аудио, подобранного пользователем вручную (папка Downloads\\mus), в
content/audio/<key>.mp3. Сопоставление — по содержанию имени файла (надёжно).
Проигрыватель сам берёт первые ~13 c с фейдами. Обновляет credits.js (мерж с
ранее вшитыми свободными записями Wikimedia). Запуск: python tools/import_user_audio.py
"""
import json, os, re, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIO = os.path.join(ROOT, "content", "audio")
CREDITS = os.path.join(ROOT, "content", "data", "credits.js")
SRC = r"C:\Users\Karasheff Kanat\Downloads\mus"

# key, токены для распознавания файла (lowercase), подпись RU, подпись KZ
MAP = [
  ("instr_dombyra",    ["adai","qurman","құрман","адай"],            "Домбра — Казахстан (кюй «Адай», Курмангазы)", "Домбыра — Қазақстан («Адай» күйі, Құрманғазы)"),
  ("instr_djembe",     ["djembe"],                                    "Джембе — Западная Африка (Гана)",            "Джембе — Батыс Африка (Гана)"),
  ("instr_oud",        ["oud"],                                       "Уд — Арабский мир (ОАЭ)",                    "Уд — Араб әлемі (БАӘ)"),
  ("instr_saz",        ["mihriban","bağlama","baglama","saz"],        "Саз / баглама — Турция",                     "Саз / баглама — Түркия"),
  ("instr_tar",        ["persian tar","delnavaz"],                    "Тар — Иран (Персия)",                        "Тар — Иран (Парсы)"),
  ("instr_guzheng",    ["guzheng"],                                   "Гучжэн — Китай",                             "Гучжэн — Қытай"),
  ("instr_gayageum",   ["gayageum"],                                  "Каягым — Корея",                             "Каягым — Корея"),
  ("instr_gamelan",    ["gamelan"],                                   "Гамелан — Индонезия (Бали)",                 "Гамелан — Индонезия (Бали)"),
  ("instr_siku",       ["siku","pan flute","andean"],                 "Сику (пан-флейта) — Анды",                   "Сику (пан-флейта) — Анд таулары"),
  ("instr_clave",      ["caribe","cuban","caribeñ","cariben"],        "Кубинская музыка (сон) — Куба",              "Куба музыкасы (сон) — Куба"),
  ("instr_flamenco",   ["flamenco","paco de lucia"],                  "Фламенко-гитара — Испания (Пако де Лусия)",  "Фламенко гитарасы — Испания (Пако де Лусия)"),
  ("instr_balkanbrass",["fanfara","streets of brass","brass durham"], "Духовой оркестр — Балканы",                  "Үрмелі оркестр — Балқан"),
  ("instr_duduk",      ["armenian","duduk"],                          "Дудук — Армения",                            "Дудук — Армения"),
  ("instr_fiddle",     ["irish"],                                     "Скрипка (фидл) — Ирландия",                  "Скрипка (фидл) — Ирландия"),
  ("instr_balalaika",  ["balalaika","troika"],                        "Балалайка — Россия («Тройка»)",              "Балалайка — Ресей («Тройка»)"),
  ("instr_hardanger",  ["hardanger"],                                 "Хардангер-фидл — Норвегия",                  "Хардангер-фидл — Норвегия"),
  ("instr_blues",      ["blues","resonator"],                         "Блюз-гитара — США",                          "Блюз гитарасы — АҚШ"),
  ("instr_morinkhuur", ["morin"],                                     "Морин хуур — Монголия",                      "Морин хуур — Моңғолия"),
  ("instr_ukulele",    ["ukulele"],                                   "Укулеле — Гавайи",                           "Укулеле — Гавайи"),
]

def load_prior():
    try:
        m = re.search(r"window\.CREDITS\s*=\s*(\{.*\});", open(CREDITS, encoding="utf-8").read(), re.S)
        if m: return {it["key"]: it for it in json.loads(m.group(1)).get("items", [])}
    except Exception: pass
    return {}

def main():
    os.makedirs(AUDIO, exist_ok=True)
    files = os.listdir(SRC)
    cred = load_prior()
    used = set(); matched = 0
    for key, tokens, ru, kz in MAP:
        hit = None
        for f in files:
            if f in used: continue
            low = f.lower()
            if any(tok.lower() in low for tok in tokens):
                hit = f; break
        if not hit:
            print("!! не найден файл для", key); continue
        used.add(hit); matched += 1
        # удалить прежние варианты (синтез-фолбэк отсутствует как файл, но на всякий случай)
        for e in ("ogg","wav"):
            p = os.path.join(AUDIO, key + "." + e)
            if os.path.exists(p): os.remove(p)
        shutil.copyfile(os.path.join(SRC, hit), os.path.join(AUDIO, key + ".mp3"))
        cred[key] = {"key":key, "titleRu":ru, "titleKz":kz,
                     "source": os.path.splitext(hit)[0][:90], "license":"учебный фрагмент (≤13 c)"}
        print("OK ", key, "<-", hit[:50])

    note_ru = ("Классические эпохи и ряд инструментов — из Wikimedia Commons под свободными лицензиями "
               "(Public Domain / CC). Остальные инструменты — короткие учебные отрывки (до 13 сек.) из "
               "записей исполнителей, права принадлежат их авторам; использованы в образовательных целях.")
    note_kz = ("Классикалық дәуірлер мен бірқатар аспап — Wikimedia Commons-тан еркін лицензиялармен "
               "(Public Domain / CC). Қалған аспаптар — орындаушылар жазбаларынан алынған қысқа оқу үзінділері "
               "(13 сек. дейін), құқықтары авторларына тиесілі; білім беру мақсатында қолданылған.")
    items = list(cred.values())
    out = ("/* credits: Wikimedia (свободные) + учебные отрывки (import_user_audio.py). */\n"
           "window.CREDITS=" + json.dumps({"noteRu":note_ru, "noteKz":note_kz, "items":items},
                                          ensure_ascii=False, indent=1) + ";\n")
    with open(CREDITS, "w", encoding="utf-8") as f: f.write(out)
    print("\nИмпортировано %d из %d. Всего в credits: %d" % (matched, len(MAP), len(items)))

if __name__ == "__main__":
    main()
