# -*- coding: utf-8 -*-
# Точные исторические границы из historical-basemaps (историки, public) →
# content/data/territories.js. Территория показывается ТОЛЬКО когда было казахское
# государство: Казахское ханство/жузы (1530/1700/1715) и совр. Казахстан (2000).
# Датасет относит западную степь к "Nogai Horde" даже после распада Ногайской орды
# (~1634), хотя там кочевал Младший жуз, а ханство при Касыме доходило до р. Урал.
# Поэтому западную часть (восточнее Волги) присоединяем к ханским контурам.
import json, urllib.request
from shapely.geometry import shape, mapping, box
from shapely.ops import unary_union

RAW = "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/{}"
HDR = {"User-Agent": "Mozilla/5.0"}
_cache = {}

def get(fn):
    if fn not in _cache:
        _cache[fn] = json.loads(urllib.request.urlopen(
            urllib.request.Request(RAW.format(fn), headers=HDR), timeout=90).read())
    return _cache[fn]

def name_of(p):
    for k in ("NAME", "name", "SUBJECTO"):
        if p.get(k): return p[k]
    return ""

def geom_of(fn, polity):
    for ft in get(fn)["features"]:
        if name_of(ft.get("properties", {})).strip().lower() == polity.lower():
            return shape(ft["geometry"])
    return None

# западная степь Младшего жуза: восточнее Волги (~47.5°E), до Арала/Урала
WEST_BOX = box(47.5, 43.5, 61.0, 53.0)

def kazakh(fn):
    """Quazaq Khanate данного года + западная степь (бывш. ногайская) = реальные земли казахов."""
    q = geom_of(fn, "Quazaq Khanate")
    nog = geom_of(fn, "Nogai Horde")
    parts = [q]
    if nog is not None:
        parts.append(nog.intersection(WEST_BOX))
    g = unary_union([p for p in parts if p and not p.is_empty])
    return g.simplify(0.06, preserve_topology=True).buffer(0)

def round_geom(geom, nd=2):
    gj = mapping(geom)
    def rnd(c):
        if isinstance(c[0], (int, float)):
            return [round(c[0], nd), round(c[1], nd)]
        return [rnd(x) for x in c]
    gj = {"type": gj["type"], "coordinates": rnd(gj["coordinates"])}
    return gj

def npts(gj):
    n = [0]
    def w(c):
        if c and isinstance(c[0], (int, float)): n[0] += 1
        else:
            for x in c: w(x)
    w(gj["coordinates"]); return n[0]

def bbox(gj):
    xs, ys = [], []
    def w(c):
        if isinstance(c[0], (int, float)): xs.append(c[0]); ys.append(c[1])
        else:
            for x in c: w(x)
    w(gj["coordinates"]); return [round(min(xs),1),round(min(ys),1),round(max(xs),1),round(max(ys),1)]

jobs = [
    ("khanate_early", lambda: kazakh("world_1530.geojson"), "Казахское ханство (XVI в., при Касыме)"),
    ("khanate_peak",  lambda: kazakh("world_1700.geojson"), "Казахское ханство (расцвет, при Тауке)"),
    ("zhuzes",        lambda: kazakh("world_1715.geojson"), "Земли трёх казахских жузов (XVIII в.)"),
    ("modern",        lambda: geom_of("world_2000.geojson", "Kazakhstan").simplify(0.02, True),
                      "Республика Казахстан"),
]
TERR = {}
for key, fn, name in jobs:
    g = fn()
    if g is None or g.is_empty:
        print("!! пусто:", key); continue
    gj = round_geom(g, 2)
    TERR[key] = {"name": name, "geometry": gj}
    print(f"{key:13s} pts={npts(gj):4d} bbox={bbox(gj)}")

out = "window.TERRITORIES=" + json.dumps(TERR, ensure_ascii=False, separators=(",", ":")) + ";\n"
with open(r"D:\Products\interactive-map\content\data\territories.js", "w", encoding="utf-8") as f:
    f.write(out)
print("WROTE territories.js (%d bytes) keys=%s" % (len(out), list(TERR)))
