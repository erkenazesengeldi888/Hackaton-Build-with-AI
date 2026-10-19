"""Сопоставляет data/ratings.csv (данные 2GIS, снятые вручную) с местами OSM по названию и адресу.
Адрес кандидата берётся из OSM или (если его нет) через обратное геокодирование Nominatim.
Результат: data/ratings_matched.json"""
import csv, difflib, json, re, time, requests

raw = json.load(open("data/osm_raw.json"))
rows = list(csv.DictReader(open("data/ratings.csv", encoding="utf-8")))
CACHE_P = "data/geocode_cache.json"
try:
    cache = json.load(open(CACHE_P))
except Exception:
    cache = {}
HINT = {  # регэксп по имени в OSM
    "ASAI": r"asai", "Leto": r"^(лето|leto)$", "Nana": r"nana", "Лапша China Town": r"china ?town", "Лапша Tokyo": r"tokyo",
    "Metis": r"metis", "Farш": r"farsh|фарш", "Pinta": r"пинта|pinta", "Golpas": r"golpas|голпас", "Brewery": r"brewery",
    "Malena": r"malena", "Proseccarna": r"prosecc", "Afra": r"^afra", "Национальный музей РК": r"национальный музей",
    "Ailand": r"ailand", "M.Art Gallery": r"m\.?art", "Aisha Art Gallery": r"aisha", "CoffeeLike": r"coffee ?like",
    "Gasteria": r"gasteria", "TLP Flowers&Coffee": r"tlp", "Canele": r"canele", "Лепим и варим": r"лепим",
    "CrepeCafe": r"crepe", "Degirmen": r"degirmen", "Drinkit": r"drinkit", "Starbucks": r"starbucks", "Book Cafe": r"book ?cafe",
    "Master Coffee": r"master ?coffee", "Chaplin Cinemas": r"chaplin", "Арман": r"арман", "Astana Musical": r"astana musical",
    "Астана Опера": r"астана опера", "Abu Dhabi Plaza": r"abu dhabi", "Mega Silk Way": r"^mega silk way$", "Ботанический сад": r"ботанич",
    "Хан Шатыр": r"хан шатыр", "Kal'bi meat house": r"kal.?bi", "Астана балет": r"астана балет|astana ballet", "Noble": r"noble", "Бату Донер": r"baty|бату", "Керуен": r"керуен|keruen", "Turandot": r"turandot", "Korean House": r"korean house", "Mokki": r"mokki|мокки", "La Belle": r"la belle", "Fire Drift": r"fire ?drift", "Kök Grand View": r"k[öo]k grand|grand view", "Точка Bistro": r"точка ?bistro|bistro",
}
TR = str.maketrans({"қ": "к", "ү": "у", "ұ": "у", "ө": "о", "ғ": "г", "ң": "н", "ә": "а", "і": "и", "һ": "х", "ё": "е"})
STOP = r"улица|көшесі|проспект|даңғылы|бульвар|шоссе|тас жолы|трц|астана|район|есиль|нура|сарайшык|алматы"


def street_num(s):
    s = s.lower().translate(TR)
    m = re.findall(r"(\d+(?:/\d+)?[а-я]?)", s)
    st = re.sub(STOP, " ", re.sub(r"\d+(?:/\d+)?[а-я]?", " ", s))
    return re.sub(r"[^а-яa-z ]", " ", st).split(), (m[-1] if m else "")


def rev(lat, lon):
    k = f"{lat:.5f},{lon:.5f}"
    if k not in cache:
        try:
            r = requests.get("https://nominatim.openstreetmap.org/reverse", timeout=20, headers={"User-Agent": "astana-walk-guide-hackathon/1.0"},
                             params={"lat": lat, "lon": lon, "format": "json", "zoom": 18, "accept-language": "ru"}).json()
            a = r.get("address", {})
            cache[k] = f"{a.get('road', '')} {a.get('house_number', '')}".strip()
        except Exception:
            cache[k] = ""
        time.sleep(1.1)
        json.dump(cache, open(CACHE_P, "w"), ensure_ascii=False)
    return cache[k]


def score(addr2gis, cand_addr):
    w1, n1 = street_num(addr2gis); w2, n2 = street_num(cand_addr)
    s = 0
    if n1 and n2 and n1 == n2:
        s += 2
    if any(difflib.SequenceMatcher(None, a, b).ratio() > 0.75 for a in w1 for b in w2):
        s += 1
    if "mega" in addr2gis.lower() and "mega" in cand_addr.lower():
        s += 2
    return s


out, report = {}, []
for r in rows:
    pat = re.compile(HINT[r["name"]], re.I)
    cands = []
    for e in raw:
        t = e.get("tags", {})
        nm = (t.get("name:ru") or t.get("name") or "")
        if not pat.search(nm) and not pat.search(t.get("name", "")):
            continue
        lat = e.get("lat") or e["center"]["lat"]; lon = e.get("lon") or e["center"]["lon"]
        a = " ".join(x for x in [t.get("addr:street"), t.get("addr:housenumber")] if x)
        cands.append((e, lat, lon, a))
    best = None
    for e, lat, lon, a in cands:
        sc = score(r["address_2gis"], a) if a else 0
        if (not a or sc < 2) and len(cands) <= 14:
            a2 = rev(lat, lon); sc = max(sc, score(r["address_2gis"], a2)); a = a or a2
        if best is None or sc > best[0]:
            best = (sc, e, lat, lon, a)
    single_ok = best and len(cands) == 1 and (best[0] >= 1 or not street_num(r['address_2gis'])[1])
    if best and (best[0] >= 2 or single_ok):
        out[f"{best[1]['type']}/{best[1]['id']}"] = r
        report.append(f"OK   {r['name']:22} -> OSM {best[1]['tags'].get('name')} | {best[4]} (score {best[0]}, кандидатов {len(cands)})")
    else:
        report.append(f"НЕТ  {r['name']:22} кандидатов {len(cands)}; лучший: {best[4] if best else '-'} score {best[0] if best else '-'}")
json.dump(out, open("data/ratings_matched.json", "w"), ensure_ascii=False, indent=1)
print("\n".join(report)); print(len(out), "из", len(rows))
