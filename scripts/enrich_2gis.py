"""Подтягивает рейтинги 2GIS в data/pois.json. Нужен ключ: https://dev.2gis.com (Places API).
Запуск:  DGIS_API_KEY=... .venv/bin/python scripts/enrich_2gis.py
Кэш ответов: data/2gis_cache.json — повторный запуск продолжает с места остановки."""
import difflib, json, os, sys, time
from pathlib import Path
import requests

KEY = os.getenv("DGIS_API_KEY") or sys.exit("Задайте DGIS_API_KEY")
POIS = Path("data/pois.json"); CACHE = Path("data/2gis_cache.json")
pois = json.loads(POIS.read_text(encoding="utf-8"))
cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}


def hav(a, b, c, d):
    from math import radians, sin, cos, asin, sqrt
    p1, p2 = radians(a), radians(c)
    return 12742 * asin(sqrt(sin((p2 - p1) / 2) ** 2 + cos(p1) * cos(p2) * sin(radians(d - b) / 2) ** 2))


hit = 0
for i, p in enumerate(pois):
    k = str(p["id"])
    if k not in cache:
        try:
            r = requests.get("https://catalog.api.2gis.com/3.0/items", timeout=20, params={
                "q": p["name"], "point": f"{p['lon']},{p['lat']}", "radius": 300, "type": "branch",
                "fields": "items.point,items.reviews", "key": KEY})
            r.raise_for_status()
            cache[k] = r.json().get("result", {}).get("items", [])
        except Exception as e:
            print("ошибка", p["name"], e); continue
        time.sleep(0.12)
        if i % 20 == 0:
            CACHE.write_text(json.dumps(cache, ensure_ascii=False))
    best = None
    for it in cache[k]:
        pt = it.get("point") or {}
        name_sim = difflib.SequenceMatcher(None, p["name"].lower(), it.get("name", "").lower()).ratio()
        d = hav(p["lat"], p["lon"], pt.get("lat", 0), pt.get("lon", 0)) * 1000
        if name_sim >= 0.5 and d <= 250 and (best is None or name_sim > best[0]):
            best = (name_sim, it)
    if best:
        rv = best[1].get("reviews") or {}
        if rv.get("general_rating"):
            p["rating"] = round(float(rv["general_rating"]), 1)
            p["service"] = p["rating"]  # 2GIS отдаёт только общую оценку; сервис = общая оценка
            p["reviews"] = int(rv.get("general_review_count") or 0)
            p["twogis_url"] = f"https://2gis.kz/astana/firm/{best[1]['id'].split('_')[0]}"
            hit += 1
CACHE.write_text(json.dumps(cache, ensure_ascii=False))
POIS.write_text(json.dumps(pois, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"оценки найдены для {hit} из {len(pois)} мест")
