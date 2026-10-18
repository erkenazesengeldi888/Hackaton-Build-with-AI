import requests
import sys
sys.path.insert(0, ".")
from rag import DAYS, parse_hours
"""data/osm_raw.json -> data/pois.json (только реальные заведения из OSM, без выдуманных оценок/меню)."""
import json, re

raw = json.load(open("data/osm_raw.json"))
MATCHED = json.load(open("data/ratings_matched.json"))  # osm_key -> строка ratings.csv (данные 2GIS)

# (категория, группа, описательные теги категории, лимит)
CAT = {
    ("amenity", "cafe"): ("кофейня", "Еда и кофе", "кофе,десерты,посидеть", 70),
    ("amenity", "restaurant"): ("ресторан", "Еда и кофе", "еда,обед,ужин,посидеть", 60),
    ("amenity", "fast_food"): ("фастфуд", "Еда и кофе", "еда,быстро,перекус", 20),
    ("amenity", "food_court"): ("фудкорт", "Еда и кофе", "еда,быстро,крытый", 10),
    ("amenity", "bar"): ("бар", "Потусить", "бар,потусить,вечер,напитки,компания,друзья", 30),
    ("amenity", "pub"): ("бар", "Потусить", "паб,пиво,потусить,вечер,компания,друзья", 30),
    ("amenity", "nightclub"): ("клуб", "Потусить", "клуб,танцы,ночь,вечеринка,потусить,музыка", 25),
    ("amenity", "karaoke_box"): ("караоке", "Потусить", "караоке,петь,потусить,компания,друзья,вечер", 15),
    ("amenity", "cinema"): ("кино", "Культура", "кино,фильм,крытый,дождь,вечер", 15),
    ("amenity", "theatre"): ("театр", "Культура", "театр,спектакль,вечер,культура,крытый", 15),
    ("amenity", "arts_centre"): ("арт-пространство", "Культура", "арт,выставка,культура,крытый,творчество", 15),
    ("tourism", "museum"): ("музей", "Культура", "музей,история,культура,крытый,дождь", 25),
    ("tourism", "gallery"): ("галерея", "Культура", "галерея,арт,выставка,культура,крытый", 15),
    ("tourism", "attraction"): ("достопримечательность", "Прогулка", "достопримечательность,фото,осмотр,прогулка", 40),
    ("tourism", "viewpoint"): ("смотровая", "Прогулка", "смотровая,вид,фото,закат,прогулка", 15),
    ("leisure", "park"): ("парк", "Прогулка", "парк,зелень,прогулка,отдых", 40),
    ("leisure", "garden"): ("парк", "Прогулка", "сад,зелень,прогулка,природа", 10),
    ("tourism", "zoo"): ("развлечения", "Развлечения", "зоопарк,семья,дети,животные,прогулка", 5),
    ("tourism", "theme_park"): ("развлечения", "Развлечения", "аттракционы,семья,дети,развлечение", 10),
    ("tourism", "aquarium"): ("развлечения", "Развлечения", "аквариум,океанариум,семья,дети,крытый,дождь", 5),
    ("leisure", "bowling_alley"): ("боулинг", "Потусить", "боулинг,потусить,компания,друзья,игры,крытый", 10),
    ("leisure", "escape_game"): ("квесты", "Потусить", "квест,потусить,компания,друзья,игры,крытый", 10),
    ("leisure", "amusement_arcade"): ("игровой клуб", "Потусить", "игры,аркады,потусить,компания,крытый", 10),
    ("leisure", "water_park"): ("развлечения", "Развлечения", "аквапарк,вода,семья,дети,крытый", 5),
    ("leisure", "dog_park"): ("площадка для собак", "Прогулка", "собаки,с собакой,выгул,площадка для собак,прогулка,парк", 5),
    ("shop", "mall"): ("тц", "Шопинг", "тц,шопинг,крытый,дождь,еда,кино", 25),
}
CUISINE = {"kazakh": "казахская", "italian": "итальянская", "japanese": "японская", "sushi": "суши", "pizza": "пицца",
           "burger": "бургеры", "coffee_shop": "кофе", "turkish": "турецкая", "uzbek": "узбекская", "chinese": "китайская",
           "korean": "корейская", "georgian": "грузинская", "asian": "азиатская", "american": "американская",
           "french": "французская", "russian": "русская", "steak_house": "стейки", "seafood": "морепродукты"}


def merge_day(osm, override):
    """Часы из 2GIS на один день недели («Sa 12:00-04:00») поверх недельного графика OSM (если он есть)."""
    m = re.match(r"(Mo|Tu|We|Th|Fr|Sa|Su) (\d\d:\d\d)-(\d\d:\d\d)$", override)
    per = {d: [] for d in range(7)}
    for days, a, b in (parse_hours(osm) if osm else None) or []:
        for d in days:
            per[d].append((f"{a // 60:02d}:{a % 60:02d}", f"{b // 60:02d}:{b % 60:02d}"))
    per[DAYS.index(m[1])] = [(m[2], m[3])]
    parts, d = [], 0
    while d < 7:
        if not per[d]:
            d += 1; continue
        e = d
        while e + 1 < 7 and per[e + 1] == per[d]:
            e += 1
        rng = ", ".join(f"{a}-{b}" for a, b in per[d])
        parts.append(f"{DAYS[d]}{'-' + DAYS[e] if e > d else ''} {rng}")
        d = e + 1
    return "; ".join(parts)


def hours(oh):
    if not oh:
        return "уточнить"
    if oh.strip() == "24/7":
        return "круглосуточно"
    m = re.fullmatch(r"(?:Mo-Su\s+)?(\d\d:\d\d)-(\d\d:\d\d)", oh.strip())
    return f"{m[1]}-{m[2]}" if m else oh.strip()


MANUAL_TAGS = {"Mokki": "вид,вид на город,панорама,высокий этаж",  # по фото 2GIS и подтверждению команды
               "Точка Bistro": "с собакой,собаки,кофе",  # можно с собакой — по данным команды
               "Бату Донер": "шаурма,донер,быстро,круглосуточно"}  # круглосуточно — по карточке 2GIS
by_cat, seen = {}, set()
for e in raw:
    t = e.get("tags", {})
    key = next(((k, t[k]) for k in ("amenity", "tourism", "leisure", "shop") if (k, t.get(k)) in CAT), None)
    lat = e.get("lat") or e.get("center", {}).get("lat")
    lon = e.get("lon") or e.get("center", {}).get("lon")
    if not key or lat is None:
        continue
    name = t.get("name:ru") or t.get("name") or "Площадка для выгула собак"
    if re.match(r"(проспект|улица|бульвар|шоссе|көшесі)\b", name.strip(), re.I):
        continue  # это название улицы, а не заведения
    if (name.lower(), round(lat, 3), round(lon, 3)) in seen:
        continue
    seen.add((name.lower(), round(lat, 3), round(lon, 3)))
    cat, group, ctags, limit = CAT[key]
    tags = [x for x in ctags.split(",")]
    if t.get("cuisine"):
        tags += [CUISINE.get(c.strip(), c.strip()) for c in t["cuisine"].split(";")][:3]
    if t.get("internet_access") in ("wlan", "yes", "wifi"):
        tags.append("wifi")
    if t.get("outdoor_seating") == "yes":
        tags.append("веранда")
    if t.get("outdoor_seating") == "yes":
        tags.append("терраса")
    if t.get("dog") in ("yes", "leashed", "outside"):
        tags.append("с собакой")  # явная отметка в OSM
    if t.get("wheelchair") == "yes":
        tags.append("доступно для колясок")
    if t.get("takeaway") in ("yes", "only"):
        tags.append("с собой")
    if t.get("live_music") == "yes":
        tags.append("живая музыка")
    addr = " ".join(x for x in [t.get("addr:street"), t.get("addr:housenumber")] if x)
    if cat == "площадка для собак" and not addr:  # адрес по ближайшей улице (обратное геокодирование)
        try:
            j = requests.get("https://nominatim.openstreetmap.org/reverse", timeout=25, headers={"User-Agent": "astana-walk-guide-hackathon/1.0"},
                             params={"lat": lat, "lon": lon, "format": "json", "zoom": 17, "accept-language": "ru"}).json()
            road = j.get("address", {}).get("road", "")
            addr = f"рядом с улицей {road}" if road else "левобережье Астаны"
        except Exception:
            addr = "левобережье Астаны"
    rt = MATCHED.get(f"{e['type']}/{e['id']}")
    if rt and rt["name"] == "Ailand":  # семейный центр с аквариумом: в помещении, не «достопримечательность на улице»
        cat, group = "развлечения", "Развлечения"
        tags = [x for x in "аттракционы,семья,дети,аквариум,крытый,развлечения".split(",")]
    if rt and rt["name"] in MANUAL_TAGS:
        tags += MANUAL_TAGS[rt["name"]].split(",")
    if rt:
        name = rt["name"]
        addr = addr or rt["address_2gis"]
    richness = 999 if rt else sum(k in t for k in ("opening_hours", "website", "contact:website", "phone", "contact:phone",
                                    "cuisine", "addr:street", "brand", "name:ru"))
    desc = f"{cat.capitalize()}" + (f", {addr}" if addr else "") + (f". Кухня: {', '.join(tags[-3:])}." if t.get("cuisine") else ".")
    hours_src = "2GIS" if (rt and rt["hours"]) else ("OSM" if t.get("opening_hours") else "")
    if rt and rt["hours"]:
        t = dict(t, opening_hours=merge_day(t.get("opening_hours"), rt["hours"]) if re.match(r"(Mo|Tu|We|Th|Fr|Sa|Su) ", rt["hours"]) else rt["hours"])
    by_cat.setdefault(cat, []).append((richness, dict(
        name=name, lat=lat, lon=lon, category=cat, group=group, tags=list(dict.fromkeys(tags)), description=desc,
        price="", hours=hours(t.get("opening_hours")), hours_source=hours_src, address=addr,
        website=t.get("website") or t.get("contact:website") or "", phone=t.get("phone") or t.get("contact:phone") or "",
        rating=float(rt["rating"]) if rt else None, service=float(rt["rating"]) if rt else None,
        reviews=int(rt["ratings_count"]) if rt else 0, menu=[], verified=True,
        rating_source=(f"2GIS, оценок: {rt['ratings_count']}, проверено {rt['checked']}" + (
            f". Оценка филиала по адресу «{rt['address_2gis']}», у этого филиала может отличаться" if rt.get("branch_note") else "")) if rt else "",
        twogis_url=f"https://2gis.kz/astana/search/{name}" if rt else "", source=f"OpenStreetMap {e['type']}/{e['id']}",
        _limit=limit)))

out = []
for cat, items in by_cat.items():
    items.sort(key=lambda x: -x[0])
    out += [i[1] for i in items[: items[0][1]["_limit"]]]
EXTRA = {"Mokki": ("ресторан", "Еда и кофе", "ресторан,вид,вид на город,панорама,высокий этаж,посидеть,вечер"),
         "La Belle": ("ресторан", "Еда и кофе", "ресторан,ужин,посидеть,вечер"),
         "Fire Drift": ("развлечения", "Развлечения", "адреналин,картинг,дрифт,аттракционы,компания,друзья,скорость,дети"),
         "Kök Grand View": ("ресторан", "Еда и кофе", "ресторан,вид,вид на город,панорама,высокий этаж,вечер,посидеть"),
         "Точка Bistro": ("ресторан", "Еда и кофе", "кафе,завтрак,обед,посидеть,с собакой,собаки"),  # «с собакой» — по данным команды
         "Астана балет": ("театр", "Культура", "театр,балет,спектакль,вечер,культура,крытый"),
         "Afra": ("бар", "Потусить", "ресто-бар,бар,потусить,вечер,музыка,диджей"),
         "Proseccarna": ("ресторан", "Еда и кофе", "ресто-бар,еда,бар,посидеть,вечер"),
         "M.Art Gallery": ("галерея", "Культура", "галерея,арт,выставка,культура,крытый"),
         "Aisha Art Gallery": ("галерея", "Культура", "галерея,арт,выставка,культура,крытый")}
for x in json.load(open("data/ratings_extra_places.json")):
    r = x["row"]; cat, group, ctags = EXTRA[r["name"]]
    out.append(dict(name=r["name"], lat=x["lat"], lon=x["lon"], category=cat, group=group, tags=ctags.split(","),
                    description=f"{r['category_2gis']}, {r['address_2gis']}.", price="", hours=r["hours"] or "уточнить", hours_source="2GIS" if r["hours"] else "",
                    address=r["address_2gis"], website="", phone="", rating=float(r["rating"]), service=float(r["rating"]),
                    reviews=int(r["ratings_count"]), menu=[], verified=True,
                    rating_source=f"2GIS, оценок: {r['ratings_count']}, проверено {r['checked']}. Точка поставлена по адресу, положение приблизительное",
                    twogis_url=f"https://2gis.kz/astana/search/{r['name']}", source="2GIS (вручную) + геокод адреса"))
# Добавочные теги по моему суждению о месте (не из 2GIS): что подходит для прогулки на закате. Правится вручную.
WALK = {"Ботанический сад": "прогулка,закат,фото,зелень,природа", "Хан Шатыр": "прогулка,закат,фото",
        "Национальный музей РК": "прогулка,закат,фото,площадь", "Астана Опера": "прогулка,фото,вечер"}
for p in out:
    if p["name"] in WALK:
        p["tags"] = list(dict.fromkeys(p["tags"] + WALK[p["name"]].split(",")))
# Категории мест, присланных командой, берём по рубрике 2GIS (так их видит пользователь), а не по тегу OSM.
CAT2GIS = {"ресторан": "ресторан", "рестораны": "ресторан", "кафе": "кофейня", "кофейни": "кофейня", "кофейня": "кофейня",
           "городское кафе": "кофейня", "пельменная": "кофейня", "цветы": "кофейня",
           "ресторан быстрого питания": "фастфуд", "гриль-бар": "бар", "бар": "бар", "ресто-бар": "бар", "ресто бар": "бар",
           "кулинария": "кулинария", "кинотеатр": "кино", "театр": "театр", "государственный театр": "театр",
           "театр оперы и балета": "театр", "музеи": "музей", "галерея": "галерея", "художественные выставки": "галерея",
           "центр семейного отдыха": "развлечения", "дрифт-картинг центр": "развлечения", "трц": "тц", "парки": "парк"}
GROUP_OF = {"ресторан": "Еда и кофе", "кофейня": "Еда и кофе", "фастфуд": "Еда и кофе", "кулинария": "Еда и кофе", "бар": "Потусить",
            "кино": "Культура", "театр": "Культура", "музей": "Культура", "галерея": "Культура", "развлечения": "Развлечения",
            "тц": "Шопинг", "парк": "Прогулка"}
BASE = {v[0]: v[2].split(",") for v in CAT.values()}
BASE["кулинария"] = "кулинария,еда,с собой,готовые блюда".split(",")
import csv as _csv
C2G = {r["name"]: r["category_2gis"] for r in _csv.DictReader(open("data/ratings.csv", encoding="utf-8"))}
for p in out:
    if p.get("rating") and p["name"] in C2G:
        new = CAT2GIS.get(C2G[p["name"]].strip().lower())
        if new and new != p["category"]:
            old = BASE.get(p["category"], [])
            p["tags"] = list(dict.fromkeys(BASE.get(new, []) + [t for t in p["tags"] if t not in old]))
            p["category"], p["group"] = new, GROUP_OF[new]
# Места, подходящие для праздника (день рождения): ресторан/бар/развлечения с вечерним форматом и компанией — по моему суждению о формате, не данные 2GIS
BIRTHDAY = ["Kök Grand View", "Mokki", "Fire Drift", "Ailand", "Afra", "Brewery", "Proseccarna", "La Belle", "Metis", "Nana", "ASAI",
            "Pinta", "Malena", "Canele", "Book Cafe"]
for p in out:
    if p["name"] in BIRTHDAY:
        p["tags"] = list(dict.fromkeys(p["tags"] + ["праздник", "день рождения", "компания"]))
EXCLUDE = {'Спорт-бар "Мундиаль", БК FairPlay'}  # убрано по просьбе команды
out = [p for p in out if p["name"] not in EXCLUDE]
ADDR_FIX = {"Матильда": "улица Брусиловского 5"}  # замена «Мундиаль»: бар из OSM, адрес определён по координатам (обратное геокодирование)
for p in out:
    if p["name"] in ADDR_FIX and not p["address"].strip():
        p["address"] = ADDR_FIX[p["name"]]
        p["description"] = f"Бар, {p['address']}."
FLOORS = {"Kök Grand View": 21, "Mokki": 3}  # этаж из карточки 2GIS: чем выше, тем лучше обзор
for p in out:
    p["floor"] = FLOORS.get(p["name"])
for i, p in enumerate(out, 1):
    p.pop("_limit", None); p["id"] = i
json.dump(out, open("data/pois_all.json", "w"), ensure_ascii=False, indent=1)  # полный набор, с местами без адреса
total = len(out)
out = [p for p in out if p["address"].strip()]  # места без адреса из выдачи убираем
json.dump(out, open("data/pois.json", "w"), ensure_ascii=False, indent=1)
print(f"всего {total}, с адресом оставлено {len(out)}, удалено без адреса {total - len(out)}")
from collections import Counter
print(len(out), dict(Counter(p["category"] for p in out)))
