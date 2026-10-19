"""Геометрия путей ЛРТ из OpenStreetMap (railway=light_rail) -> data/lrt_track.json: список линий [[lon, lat], ...]."""
import json, time, requests
BBOX = "51.03,71.30,51.22,71.58"
URLS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter", "https://overpass.private.coffee/api/interpreter"]
q = f'[out:json][timeout:60];way["railway"="light_rail"]({BBOX});out geom;'
for attempt in range(9):
    try:
        r = requests.post(URLS[attempt % 3], data={"data": q}, timeout=90, headers={"User-Agent": "astana-walk-guide-hackathon/1.0"})
        r.raise_for_status()
        ways = [[[p["lon"], p["lat"]] for p in e["geometry"]] for e in r.json()["elements"] if e.get("geometry")]
        json.dump(ways, open("data/lrt_track.json", "w"))
        print("ok ways:", len(ways), "points:", sum(len(w) for w in ways)); break
    except Exception as e:
        print("retry", attempt, str(e)[:50], flush=True); time.sleep(10)
