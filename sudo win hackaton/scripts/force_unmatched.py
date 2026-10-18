"""Для строк ratings.csv без точного совпадения адреса: привязывает оценку к ближайшему по смыслу заведению OSM
(с пометкой, что это оценка другого филиала) или создаёт точку по геокоду адреса. Дополняет data/ratings_matched.json."""
import csv, json, re, time, requests
from math import radians, sin, cos, asin, sqrt

raw = json.load(open("data/osm_raw.json"))
matched = json.load(open("data/ratings_matched.json"))
rows = {r["name"]: r for r in csv.DictReader(open("data/ratings.csv", encoding="utf-8"))}
exec(open("scripts/match_ratings.py").read().split("TR = ")[0].split("HINT = ")[1].join(["HINT = ", ""])) if False else None
import importlib.util, sys
src = open("scripts/match_ratings.py").read()
HINT = eval(src[src.index("HINT = ") + 7: src.index("TR = ")])
done = {r["name"] for r in matched.values()}
MEGA = (51.0890, 71.4030)


def hav(a, b, c, d):
    p1, p2 = radians(a), radians(c)
    return 12742 * asin(sqrt(sin((p2 - p1) / 2) ** 2 + cos(p1) * cos(p2) * sin(radians(d - b) / 2) ** 2))


GC = "data/geocode_cache2.json"
try:
    _gc = json.load(open(GC))
except Exception:
    _gc = {}


def geocode(q):
    if q in _gc:
        return tuple(_gc[q]) if _gc[q] else None
    for attempt in range(4):
        try:
            r = requests.get("https://nominatim.openstreetmap.org/search", timeout=30, headers={"User-Agent": "astana-walk-guide-hackathon/1.0"},
                             params={"q": q, "format": "json", "limit": 1, "accept-language": "ru"}).json()
            time.sleep(1.1)
            _gc[q] = [float(r[0]["lat"]), float(r[0]["lon"])] if r else None
            json.dump(_gc, open(GC, "w"))
            return tuple(_gc[q]) if _gc[q] else None
        except Exception:
            time.sleep(5)
    return None


def center(e):
    return e.get("lat") or e["center"]["lat"], e.get("lon") or e["center"]["lon"]


kalbi = next((center(e) for k, v in matched.items() if v["name"] == "Kal'bi meat house" for e in raw if f"{e['type']}/{e['id']}" == k), MEGA)
ANCHOR = {"Starbucks": MEGA, "Master Coffee": MEGA, "Chaplin Cinemas": MEGA, "Farш": MEGA, "Golpas": kalbi,
          "CoffeeLike": geocode("улица Шамши Калдаякова 44 Астана"), "Pinta": geocode("улица Акмешит 9/1 Астана")}
extra, log = [], []
for name, r in rows.items():
    if name in done:
        continue
    pat = re.compile(HINT[name], re.I)
    cands = [e for e in raw if pat.search(e.get("tags", {}).get("name", ""))]
    anc = ANCHOR.get(name)
    if cands and anc:
        e = min(cands, key=lambda e: hav(*anc, *center(e)))
        matched[f"{e['type']}/{e['id']}"] = dict(r, branch_note="1")
        log.append(f"привязано (другой филиал): {name} -> OSM {e['tags'].get('name')} в {hav(*anc, *center(e)):.2f} км от адреса 2GIS")
    elif not cands:
        GEO = {"Mokki": "улица Достык 16 Астана", "La Belle": "проспект Женис 3 Астана", "Kök Grand View": "улица Кунаева 29/1 Астана", "Fire Drift": "улица Сыганак 17Б Астана", "Точка Bistro": "улица Бейбитшилик 5 Астана"}
        q = GEO.get(name) or "улица " + re.sub(r"\(.*?\)", "", r["address_2gis"]).replace(", ", " ").strip() + " Астана"
        g = (51.0926174, 71.4095028) if name == "Afra" else geocode(q)  # Afra: геокод только до улицы, положение приблизительное
        if g:
            extra.append(dict(row=r, lat=g[0], lon=g[1]))
            log.append(f"новая точка по адресу: {name} {g}")
        else:
            log.append(f"ПРОПУЩЕНО (нет координат): {name}")
json.dump(matched, open("data/ratings_matched.json", "w"), ensure_ascii=False, indent=1)
json.dump(extra, open("data/ratings_extra_places.json", "w"), ensure_ascii=False, indent=1)
print("\n".join(log))
