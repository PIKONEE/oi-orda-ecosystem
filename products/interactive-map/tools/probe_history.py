# Инспектирует historical-basemaps: какие годы есть и какая держава покрывает
# ключевые точки Казахстана в каждый период. Помогает выбрать точные границы.
import json, urllib.request

API = "https://api.github.com/repos/aourednik/historical-basemaps/contents/geojson"
RAW = "https://raw.githubusercontent.com/aourednik/historical-basemaps/master/geojson/{}"
HDR = {"User-Agent": "Mozilla/5.0"}

def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=HDR), timeout=60).read()

# 1) список доступных годов
files = json.loads(get(API))
years = sorted(f["name"] for f in files if f["name"].startswith("world_") and f["name"].endswith(".geojson"))
print("AVAILABLE:", ", ".join(y.replace("world_", "").replace(".geojson", "") for y in years))

def pip(pt, ring):
    x, y = pt; inside = False; n = len(ring); j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]; xj, yj = ring[j][0], ring[j][1]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi):
            inside = not inside
        j = i
    return inside

def contains(geom, pt):
    if not geom: return False
    t = geom.get("type"); c = geom.get("coordinates")
    polys = [c] if t == "Polygon" else (c if t == "MultiPolygon" else [])
    for poly in polys:
        if poly and pip(pt, poly[0]):
            if not any(pip(pt, poly[k]) for k in range(1, len(poly))):
                return True
    return False

POINTS = {
    "центр(48,68)": (68.0, 48.0), "Алматы/Жетысу(43.2,76.9)": (76.9, 43.2),
    "запад(49,52)": (52.0, 49.0), "Оренбург(51.8,55.1)": (55.1, 51.8),
    "Сырдария-юг(43.3,68.3)": (68.3, 43.3), "север(53,69)": (69.0, 53.0),
    "восток(48,82)": (82.0, 48.0),
}
CHECK = ["world_1530.geojson","world_1700.geojson","world_1715.geojson","world_1783.geojson",
         "world_1815.geojson","world_1880.geojson","world_1900.geojson","world_1920.geojson",
         "world_1938.geojson","world_1960.geojson","world_2000.geojson"]
for fn in CHECK:
    if fn not in set(years):
        print("\n==", fn, "-- НЕТ"); continue
    try:
        fc = json.loads(get(RAW.format(fn)))
    except Exception as e:
        print("\n==", fn, "ERR", e); continue
    print("\n==", fn)
    for label, pt in POINTS.items():
        hit = "—"
        for ft in fc.get("features", []):
            if contains(ft.get("geometry"), pt):
                p = ft.get("properties", {})
                hit = p.get("NAME") or p.get("name") or p.get("SUBJECTO") or "?"
                break
        print(f"   {label:24s} -> {hit}")
