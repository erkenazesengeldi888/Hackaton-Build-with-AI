"""Маршруты по реальным дорогам: OSRM (OpenStreetMap). Пешком и на авто, с пошаговыми подсказками."""
import json
from pathlib import Path

import requests

from rag import WALK_KMH, haversine_km

SERVERS = {"foot": "https://routing.openstreetmap.de/routed-foot", "car": "https://routing.openstreetmap.de/routed-car",
           "scooter": "https://routing.openstreetmap.de/routed-bike"}  # самокат считаем по велопрофилю (~15 км/ч)
MODES = {"foot": "Пешком", "scooter": "Самокат", "bus": "Автобус", "lrt": "ЛРТ", "car": "На авто"}
try:
    TRANSIT = json.loads((Path(__file__).parent / "data" / "transit.json").read_text(encoding="utf-8"))
except Exception:
    TRANSIT = {}
if TRANSIT.get("lrt"):  # только станции ЛРТ (Tarlan Astana), без дублей платформ и железной дороги
    _seen, _lrt = set(), []
    for _s in TRANSIT["lrt"]:
        if _s["tags"].get("light_rail") == "yes" and _s["name"] and _s["name"] not in _seen:
            _seen.add(_s["name"]); _lrt.append(_s)
    TRANSIT["lrt"] = _lrt
TRANSIT_SPEED = {"bus": 18.0, "lrt": 30.0}   # км/ч, с учётом остановок
TRANSIT_WAIT = {"bus": 8, "lrt": 7}          # мин ожидания (оценка)
MAX_STOP_WALK_KM = {"bus": 1.2, "lrt": 3.0}
MOD = {"left": "налево", "right": "направо", "slight left": "левее", "slight right": "правее",
       "sharp left": "резко налево", "sharp right": "резко направо", "straight": "прямо", "uturn": "развернитесь"}
SIDE = {"left": "слева", "right": "справа"}


def step_text(s):
    m, name = s["maneuver"], s.get("name") or ""
    t, mod = m["type"], m.get("modifier", "")
    on = f" по «{name}»" if name else ""
    if t == "arrive":
        return "Вы на месте" + (f", цель {SIDE[mod]}" if mod in SIDE else "")
    if t == "depart":
        return "Начните движение" + on
    if t in ("roundabout", "rotary", "roundabout turn"):
        return f"На кольце сверните на {m['exit']}-й съезд{on}" if m.get("exit") else f"Проедьте кольцо{on}"
    if t == "uturn" or mod == "uturn":
        return "Развернитесь" + on
    if t in ("continue", "new name") or mod == "straight":
        return "Продолжайте прямо" + on
    if t == "merge":
        return "Перестройтесь" + on
    if t == "fork":
        return f"На развилке держитесь {MOD.get(mod, 'прямо')}{on}"
    if t in ("on ramp", "off ramp"):
        return f"Съезд {MOD.get(mod, '')}{on}".strip()
    if t == "end of road":
        return f"В конце дороги поверните {MOD.get(mod, '')}{on}".strip()
    return f"Поверните {MOD.get(mod, 'прямо')}{on}"


def fmt_dist(m):
    return f"{m / 1000:.1f} км" if m >= 1000 else f"{round(m / 10) * 10} м"


def _nearest(kind, lat, lon):
    stops = [s for s in TRANSIT.get(kind, []) if s.get("name")] or TRANSIT.get(kind, [])
    if not stops:
        return None, None
    best = min(stops, key=lambda s: haversine_km(lat, lon, s["lat"], s["lon"]))
    return best, haversine_km(lat, lon, best["lat"], best["lon"])


def _osrm(profile, a, b):
    """Геометрия по дорогам между двумя точками (lat, lon): (path[[lon, lat]], метры, секунды). При сбое — прямая линия."""
    try:
        r = requests.get(f"{SERVERS[profile]}/route/v1/driving/{a[1]},{a[0]};{b[1]},{b[0]}",
                         params={"overview": "full", "geometries": "geojson"}, timeout=20,
                         headers={"User-Agent": "astana-walk-guide-hackathon/1.0"})
        r.raise_for_status()
        rt = r.json()["routes"][0]
        return rt["geometry"]["coordinates"], rt["distance"], rt["duration"]
    except Exception:
        d = haversine_km(*a, *b) * 1000 * 1.3
        return [[a[1], a[0]], [b[1], b[0]]], d, d / 1000 / (WALK_KMH if profile == "foot" else 25.0) * 3600


_TRACK = None


def _track_graph():
    """Граф путей ЛРТ из OSM: {узел: [(сосед, метры)]} и словарь координат."""
    global _TRACK
    if _TRACK is None:
        graph, xy = {}, {}
        try:
            for way in json.loads((Path(__file__).parent / "data" / "lrt_track.json").read_text(encoding="utf-8")):
                prev = None
                for lon, lat in way:
                    k = (round(lat, 5), round(lon, 5)); xy[k] = (lat, lon)
                    if prev is not None and prev != k:
                        d = haversine_km(*prev, *k) * 1000
                        graph.setdefault(prev, []).append((k, d)); graph.setdefault(k, []).append((prev, d))
                    prev = k
            # два параллельных пути (по одному на направление) соединяем между собой: станция может стоять на любом из них
            keys = list(graph)
            for i, k1 in enumerate(keys):
                for k2 in keys[i + 1:]:
                    if abs(k1[0] - k2[0]) < 0.0003 and abs(k1[1] - k2[1]) < 0.0004:
                        d = haversine_km(*k1, *k2) * 1000
                        if 0 < d < 25 and all(n != k2 for n, _ in graph[k1]):
                            graph[k1].append((k2, d * 3)); graph[k2].append((k1, d * 3))
        except Exception:
            pass
        _TRACK = (graph, xy)
    return _TRACK


def lrt_track_path(a, b):
    """Путь по рельсам ЛРТ между двумя точками (lat, lon): (path[[lon, lat]], метры) или None, если данных нет / пути нет."""
    import heapq
    graph, xy = _track_graph()
    if not graph:
        return None
    snap = lambda p: min(graph, key=lambda k: (k[0] - p[0]) ** 2 + (k[1] - p[1]) ** 2)
    src, dst = snap(a), snap(b)
    dist, prev, heap = {src: 0}, {}, [(0, src)]
    while heap:
        d, u = heapq.heappop(heap)
        if u == dst:
            break
        if d > dist.get(u, 1e18):
            continue
        for v, w in graph[u]:
            nd = d + w
            if nd < dist.get(v, 1e18):
                dist[v], prev[v] = nd, u
                heapq.heappush(heap, (nd, v))
    if dst not in dist:
        return None
    node, path = dst, [dst]
    while node != src:
        node = prev[node]; path.append(node)
    path.reverse()
    return [[xy[k][1], xy[k][0]] for k in path], dist[dst]


def _lrt_chain():
    """Станции ЛРТ по порядку вдоль линии (цепочка от самой южной по ближайшему соседу)."""
    st = list(TRANSIT.get("lrt", []))
    if not st:
        return []
    cur = min(st, key=lambda s: s["lat"])
    chain = [cur]; st.remove(cur)
    while st:
        cur = min(st, key=lambda s: haversine_km(cur["lat"], cur["lon"], s["lat"], s["lon"]))
        if haversine_km(chain[-1]["lat"], chain[-1]["lon"], cur["lat"], cur["lon"]) > 0.15:  # дубли станций в OSM пропускаем
            chain.append(cur)
        st.remove(cur)
    return chain


def nearest_stop(kind, lat, lon):
    """Ближайшая остановка/станция: (название, расстояние в метрах) или None."""
    st_, d = _nearest(kind, lat, lon)
    return (st_["name"] or "остановка", round(d * 1000)) if st_ else None


def transit_route(mode, pts):
    """Автобус / ЛРТ: пешком до остановки + поездка + пешком. Геометрия: пешие участки по тротуарам, автобус по дорогам,
    ЛРТ по станциям линии. Время — оценка по остановкам OSM, без расписания и номеров маршрутов."""
    label = "автобусе" if mode == "bus" else "ЛРТ"
    stop_word = "станции" if mode == "lrt" else "остановки"
    legs, segments, stops, notes = [], [], [], set()
    chain = _lrt_chain() if mode == "lrt" else []
    for a, b in zip(pts, pts[1:]):
        direct = haversine_km(*a, *b)
        s1, d1 = _nearest(mode, *a)
        s2, d2 = _nearest(mode, *b)
        if direct < 0.8 or not s1 or not s2 or d1 > 8 or d2 > 8 or s1 is s2:
            path, d, dur = _osrm("foot", a, b)
            if direct < 0.8:
                txt = "Близко: проще дойти пешком"
                notes.add("Для коротких участков советуем идти пешком.")
            else:
                txt = f"Рядом нет {'станции ЛРТ' if mode == 'lrt' else 'остановки'} в наших данных — показан пеший путь; проверьте маршрут в 2GIS"
                notes.add(f"Для части участков нет данных о {'станциях ЛРТ' if mode == 'lrt' else 'остановках'}.")
            legs.append(dict(distance=d, duration=dur, steps=[dict(text=txt, distance=d), dict(text="Вы на месте", distance=0)]))
            segments.append(dict(kind="walk", path=path))
            continue
        if max(d1, d2) > MAX_STOP_WALK_KM[mode]:
            notes.add(f"Ближайшая {'станция ЛРТ' if mode == 'lrt' else 'остановка'} далеко от одного из концов ({max(d1, d2):.1f} км пешком): "
                      f"{'ЛРТ' if mode == 'lrt' else 'автобус'} сюда не доходит, дальше удобнее другой транспорт.")
        w1_path, w1_d, w1_t = _osrm("foot", a, (s1["lat"], s1["lon"]))
        w2_path, w2_d, w2_t = _osrm("foot", (s2["lat"], s2["lon"]), b)
        if mode == "lrt" and chain:
            names = [c["name"] for c in chain]
            i, j = names.index(s1["name"]), names.index(s2["name"])
            seq = chain[i:j + 1] if i <= j else chain[j:i + 1][::-1]
            ride_path = [[c["lon"], c["lat"]] for c in seq]
            ride_d = sum(haversine_km(x["lat"], x["lon"], y["lat"], y["lon"]) for x, y in zip(seq, seq[1:])) * 1000 * 1.1
            track = lrt_track_path((s1["lat"], s1["lon"]), (s2["lat"], s2["lon"]))  # реальная геометрия путей
            if track:
                ride_path, ride_d = track[0], track[1]
            ride_min = (len(seq) - 1) * 2.3 + TRANSIT_WAIT["lrt"]
            for k, c in enumerate(seq):
                stops.append(dict(name=c["name"], lat=c["lat"], lon=c["lon"], kind="lrt", major=k in (0, len(seq) - 1)))
        else:
            ride_path, ride_d, _ = _osrm("car", (s1["lat"], s1["lon"]), (s2["lat"], s2["lon"]))
            ride_min = ride_d / 1000 / TRANSIT_SPEED["bus"] * 60 + TRANSIT_WAIT["bus"]
            for s in (s1, s2):
                stops.append(dict(name=s["name"] or "остановка", lat=s["lat"], lon=s["lon"], kind="bus", major=True))
        segments += [dict(kind="walk", path=w1_path), dict(kind=mode, path=ride_path), dict(kind="walk", path=w2_path)]
        steps = [dict(text=f"Дойдите до {stop_word} «{s1['name'] or 'без названия'}»", distance=w1_d),
                 dict(text=f"Проедьте на {label} до «{s2['name'] or 'без названия'}» (~{round(ride_min)} мин с ожиданием; {'номер и ' if mode == 'bus' else ''}расписание — в 2GIS)", distance=ride_d),
                 dict(text="Дойдите до места", distance=w2_d), dict(text="Вы на месте", distance=0)]
        legs.append(dict(distance=w1_d + ride_d + w2_d, duration=w1_t + ride_min * 60 + w2_t, steps=steps))
    note = ("Время — оценка по остановкам OpenStreetMap, без расписания и номеров маршрутов. Точный маршрут — в 2GIS или Google Maps. "
            + " ".join(sorted(notes))).strip()
    full = [pt for sg in segments for pt in sg["path"]]
    return dict(distance=sum(l["distance"] for l in legs), duration=sum(l["duration"] for l in legs), path=full, legs=legs,
                approx=True, note=note, segments=segments, stops=stops)


def get_route(mode, pts):
    if mode in ("bus", "lrt"):
        return transit_route(mode, pts)
    """pts: [(lat, lon), ...] (старт + остановки). -> dict(distance, duration, path[[lon,lat]], legs[{distance, duration, steps}], approx)"""
    coords = ";".join(f"{lo},{la}" for la, lo in pts)
    try:
        r = requests.get(f"{SERVERS[mode]}/route/v1/driving/{coords}",
                         params={"overview": "full", "geometries": "geojson", "steps": "true"}, timeout=25,
                         headers={"User-Agent": "astana-walk-guide-hackathon/1.0"})
        r.raise_for_status()
        rt = r.json()["routes"][0]
        legs = [dict(distance=l["distance"], duration=l["duration"],
                     steps=[dict(text=step_text(s), distance=s["distance"], loc=s["maneuver"]["location"], bearing=s["maneuver"].get("bearing_after")) for s in l["steps"]]) for l in rt["legs"]]
        return dict(distance=rt["distance"], duration=rt["duration"], path=rt["geometry"]["coordinates"],
                    legs=legs, approx=False,
                    note="Самокат: маршрут по велопрофилю OpenStreetMap (~15 км/ч); правила проезда на самокатах уточняйте." if mode == "scooter" else "")
    except Exception:
        # сервис недоступен: прямая линия и грубая оценка — честно помечаем approx
        speed = {"foot": WALK_KMH, "scooter": 15.0}.get(mode, 30.0)
        legs, path, dist = [], [[pts[0][1], pts[0][0]]], 0
        for a, b in zip(pts, pts[1:]):
            d = haversine_km(*a, *b) * 1000 * 1.3
            legs.append(dict(distance=d, duration=d / 1000 / speed * 3600, steps=[]))
            path.append([b[1], b[0]]); dist += d
        return dict(distance=dist, duration=sum(l["duration"] for l in legs), path=path, legs=legs, approx=True)


def order_nearest(start, places):
    """Жадный порядок обхода: всегда к ближайшей следующей точке."""
    left, cur, out = list(places), start, []
    while left:
        nxt = min(left, key=lambda p: haversine_km(cur[0], cur[1], p["lat"], p["lon"]))
        left.remove(nxt); out.append(nxt); cur = (nxt["lat"], nxt["lon"])
    return out


def nav_links(pts, mode):
    """Ссылки для запуска навигации в Google Maps / 2GIS. pts: [(lat, lon)...]"""
    g_mode = {"foot": "walking", "scooter": "bicycling", "bus": "transit", "lrt": "transit"}.get(mode, "driving")
    way = "|".join(f"{la},{lo}" for la, lo in pts[1:-1])
    g = (f"https://www.google.com/maps/dir/?api=1&origin={pts[0][0]},{pts[0][1]}"
         f"&destination={pts[-1][0]},{pts[-1][1]}&travelmode={g_mode}" + (f"&waypoints={way}" if way else ""))
    d = "https://2gis.kz/astana/directions/points/" + "|".join(f"{lo},{la}" for la, lo in pts)
    return g, d


def places_along(paths, pois, exclude_ids=(), max_m=40):
    """Заведения, мимо которых проходит маршрут: [(название, метров от начала пути)] по порядку. paths — список линий [[lon, lat], ...]."""
    import math
    out, offset = {}, 0.0
    for path in paths:
        if len(path) < 2:
            continue
        lat0 = path[0][1]
        kx, ky = 111320 * math.cos(math.radians(lat0)), 110540
        pts = [((lo) * kx, la * ky) for lo, la in path]
        cum = [0.0]
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            cum.append(cum[-1] + math.hypot(x2 - x1, y2 - y1))
        for p in pois:
            if p["id"] in exclude_ids:
                continue
            px, py = p["lon"] * kx, p["lat"] * ky
            best = None
            for i in range(len(pts) - 1):
                (x1, y1), (x2, y2) = pts[i], pts[i + 1]
                dx, dy = x2 - x1, y2 - y1
                L2 = dx * dx + dy * dy
                u = 0 if L2 == 0 else max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / L2))
                d = math.hypot(px - (x1 + u * dx), py - (y1 + u * dy))
                if d <= max_m and (best is None or d < best[0]):
                    best = (d, offset + cum[i] + u * math.sqrt(L2))
            if best and (p["name"] not in out or best[1] < out[p["name"]]):
                out[p["name"]] = best[1]
        offset += cum[-1]
    return sorted(out.items(), key=lambda kv: kv[1])


def clean_steps(leg, min_m=50, limit=6):
    """Короткий список шагов маршрута: без мелких поворотов и служебных строк."""
    steps = [s for s in leg["steps"] if s["distance"] >= min_m or s["text"].startswith("Дойдите") or s["text"].startswith("Проедьте")]
    steps = [s for s in steps if not s["text"].startswith("Начните")]
    return steps[:limit]


def compass(deg):
    """Угол (градусы от севера) -> «на север», «на северо-восток» и т.д."""
    names = ["север", "северо-восток", "восток", "юго-восток", "юг", "юго-запад", "запад", "северо-запад"]
    return "на " + names[int((deg % 360) / 45 + 0.5) % 8]
