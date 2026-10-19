"""Остановки автобусов и станции ЛРТ из OpenStreetMap -> data/transit.json"""
import json, time, requests
BBOX = "51.03,71.30,51.22,71.55"
URLS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter", "https://overpass.private.coffee/api/interpreter"]
Q = {"bus": f'node["highway"="bus_stop"]({BBOX});',
     "lrt": f'nwr["railway"~"^(station|halt|tram_stop|stop)$"]({BBOX});nwr["station"~"light_rail|subway"]({BBOX});nwr["light_rail"="yes"]["public_transport"~"station|stop_position"]({BBOX});'}
out = {}
for kind, qq in Q.items():
    q = f"[out:json][timeout:60];({qq});out center tags;"
    for attempt in range(9):
        try:
            r = requests.post(URLS[attempt % 3], data={"data": q}, timeout=90, headers={"User-Agent": "astana-walk-guide-hackathon/1.0"})
            r.raise_for_status()
            els = r.json()["elements"]
            out[kind] = [dict(name=e.get("tags", {}).get("name:ru") or e.get("tags", {}).get("name") or "", lat=e.get("lat") or e["center"]["lat"], lon=e.get("lon") or e["center"]["lon"], tags=e.get("tags", {})) for e in els]
            print("ok", kind, len(els), flush=True); break
        except Exception as e:
            print("retry", kind, attempt, str(e)[:40], flush=True); time.sleep(10)
json.dump(out, open("data/transit.json", "w"), ensure_ascii=False)
