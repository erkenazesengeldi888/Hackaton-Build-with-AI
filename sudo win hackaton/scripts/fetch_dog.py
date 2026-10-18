"""Места, где разрешены собаки (OSM dog=yes/leashed/outside) и площадки для выгула. Добавляет в data/osm_raw.json"""
import json, time, requests
BBOX = "51.03,71.30,51.22,71.55"
URLS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter", "https://overpass.private.coffee/api/interpreter"]
QUERIES = [f'nwr["dog"~"^(yes|leashed|outside)$"]["name"]({BBOX});', f'nwr["leisure"="dog_park"]({BBOX});']
raw = json.load(open("data/osm_raw.json")); have = {(e["type"], e["id"]): e for e in raw}
for qq in QUERIES:
    q = f"[out:json][timeout:60];({qq});out center tags;"
    for attempt in range(9):
        try:
            r = requests.post(URLS[attempt % 3], data={"data": q}, timeout=90, headers={"User-Agent": "astana-walk-guide-hackathon/1.0"})
            r.raise_for_status()
            els = r.json()["elements"]
            for e in els:
                k = (e["type"], e["id"])
                if k in have: have[k]["tags"] = e["tags"]  # обновим теги (dog)
                else: raw.append(e); have[k] = e
            print("ok", len(els), qq[:40], flush=True); break
        except Exception as e:
            print("retry", attempt, str(e)[:40], flush=True); time.sleep(10)
json.dump(raw, open("data/osm_raw.json", "w"), ensure_ascii=False)
print("total", len(raw))
