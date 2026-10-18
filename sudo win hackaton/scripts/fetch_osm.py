"""Тянет реальные заведения Астаны из OpenStreetMap (Overpass API) -> data/osm_raw.json"""
import json, sys, time, requests

BBOX = "51.03,71.30,51.22,71.55"  # юг,запад,север,восток
PARTS = [
    f'nwr["amenity"~"^(cafe|restaurant|fast_food|food_court)$"]["name"]({BBOX});',
    f'nwr["amenity"~"^(bar|pub|nightclub|karaoke_box|cinema|theatre|arts_centre)$"]["name"]({BBOX});',
    f'nwr["tourism"~"^(museum|attraction|viewpoint|gallery|zoo|theme_park|aquarium)$"]["name"]({BBOX});',
    f'nwr["leisure"~"^(park|garden|bowling_alley|escape_game|amusement_arcade|water_park)$"]["name"]({BBOX});'
    f'nwr["shop"="mall"]["name"]({BBOX});',
]
URLS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter",
        "https://overpass.private.coffee/api/interpreter"]
seen, out = set(), []
for part in PARTS:
    q = f"[out:json][timeout:60];({part});out center tags;"
    for attempt in range(7):
        url = URLS[attempt % len(URLS)]
        try:
            r = requests.post(url, data={"data": q}, timeout=90, headers={"User-Agent": "astana-walk-guide-hackathon/1.0"})
            r.raise_for_status()
            els = r.json()["elements"]
            for e in els:
                if (e["type"], e["id"]) not in seen:
                    seen.add((e["type"], e["id"])); out.append(e)
            print("ok", len(els), url); break
        except Exception as e:
            print("retry", attempt, url, str(e)[:60]); time.sleep(12)
    else:
        print("SKIPPED part:", part[:60])
json.dump(out, open("data/osm_raw.json", "w"), ensure_ascii=False)
print("total", len(out))
