# Скачивает физические тайлы Esri для ВСЕГО мира (z2,z3) — чтобы карта не была
# обрезана прямоугольником. Сохраняет в content/tiles/{z}/{x}/{y}.jpg (Leaflet xyz).
import os, urllib.request
base = r"D:\Products\interactive-map\content\tiles"
url  = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Physical_Map/MapServer/tile/{z}/{y}/{x}"
hdr  = {"User-Agent": "Mozilla/5.0"}
got = skip = err = 0
for z in (2, 3):
    n = 2 ** z
    for x in range(n):
        for y in range(n):
            d = os.path.join(base, str(z), str(x))
            os.makedirs(d, exist_ok=True)
            fp = os.path.join(d, str(y) + ".jpg")
            if os.path.exists(fp) and os.path.getsize(fp) > 0:
                skip += 1; continue
            try:
                req = urllib.request.Request(url.format(z=z, y=y, x=x), headers=hdr)
                data = urllib.request.urlopen(req, timeout=30).read()
                with open(fp, "wb") as f:
                    f.write(data)
                got += 1
            except Exception as e:
                err += 1
                print("ERR", z, x, y, e)
print("DONE got=%d skip=%d err=%d" % (got, skip, err))
