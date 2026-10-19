"""Докачивает еду/кофе мелкими запросами и добавляет в data/osm_raw.json"""
import json, time, requests
BBOX = "51.03,71.30,51.22,71.55"
URLS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter",
        "https://overpass.private.coffee/api/interpreter"]
raw = json.load(open("data/osm_raw.json"))
seen = {(e["type"], e["id"]) for e in raw}
for amen in ["cafe", "restaurant", "fast_food", "food_court"]:
    q = f'[out:json][timeout:60];nwr["amenity"="{amen}"]["name"]({BBOX});out center tags;'
    for attempt in range(9):
        try:
            r = requests.post(URLS[attempt % 3], data={"data": q}, timeout=90, headers={"User-Agent": "astana-walk-guide-hackathon/1.0"})
            r.raise_for_status()
            els = [e for e in r.json()["elements"] if (e["type"], e["id"]) not in seen]
            raw += els; seen |= {(e["type"], e["id"]) for e in els}
            print("ok", amen, len(els), flush=True); break
        except Exception as e:
            print("retry", amen, attempt, str(e)[:40], flush=True); time.sleep(10)
    json.dump(raw, open("data/osm_raw.json", "w"), ensure_ascii=False)
print("total", len(raw))
