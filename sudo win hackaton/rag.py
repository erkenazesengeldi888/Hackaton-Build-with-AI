"""RAG core: geo filter -> TF-IDF retrieval -> LLM generation (Gemini) with offline fallback."""
import json, math, os, re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

POIS = json.loads((Path(__file__).parent / "data" / "pois.json").read_text(encoding="utf-8"))
WALK_KMH = 4.5
TZ = timezone(timedelta(hours=5))  # Астана, UTC+5

# Небольшой словарь синонимов, чтобы запрос «тихо с розеткой» находил теги.
SYN = {
    "розетк": ["розетки", "работа"], "работат": ["розетки", "wifi", "работа"],
    "тих": ["тихо"], "спокойн": ["тихо"], "дожд": ["крытый", "музей"], "холод": ["крытый"],
    "кофе": ["кофе", "кофейня"], "поесть": ["еда"], "обед": ["еда"], "ужин": ["еда"],
    "дет": ["дети", "семья"],
    "террас": ["терраса", "веранда"], "веранд": ["веранда", "терраса"], "панорам": ["панорама", "вид"],
    "адренал": ["адреналин", "картинг", "дрифт", "аттракционы"], "экстрим": ["адреналин", "аттракционы"],
    "драйв": ["адреналин", "картинг"], "скорост": ["адреналин", "картинг", "дрифт"], "картинг": ["картинг", "дрифт"],
    "собак": ["собаки", "выгул", "парк", "прогулка"], "питомц": ["собаки", "парк"],
    "турист": ["достопримечательность", "музей", "фото", "прогулка"], "посмотр": ["достопримечательность", "музей", "фото"],
    "осмотр": ["достопримечательность", "музей", "фото"], "ночн": ["ночь", "клуб", "бар", "потусить", "вечер"],
    "ночью": ["ночь", "клуб", "бар", "потусить"], "необычн": ["развлечения", "арт", "квест", "галерея"],
    "актив": ["развлечения", "адреналин", "игры"], "ребен": ["дети", "семья", "развлечения", "музей"],
    "ребён": ["дети", "семья", "развлечения", "музей"], "площадк": ["парк", "развлечения"], "интерактив": ["музей", "развлечения"],
    "коляск": ["колясок", "доступно"], "ограниченн": ["колясок", "доступно"], "инвалид": ["колясок", "доступно"],
    "праздн": ["праздник", "день рождения", "компания"], "рожден": ["праздник", "день рождения", "компания"],
    "отпраздн": ["праздник", "день рождения", "компания"], "юбил": ["праздник", "компания"], "доступн": ["колясок", "доступно"],
    "потус": ["потусить", "бар", "клуб", "компания"], "тусов": ["потусить", "бар", "клуб"],
    "тусит": ["потусить", "бар", "клуб"], "друз": ["друзья", "компания", "потусить"],
    "вечеринк": ["вечеринка", "клуб", "танцы"], "танц": ["танцы", "клуб"], "пиво": ["пиво", "паб", "бар"],
    "выпит": ["бар", "напитки"], "кино": ["кино", "фильм"], "фильм": ["кино", "фильм"],
    "караок": ["караоке"], "боулинг": ["боулинг"], "квест": ["квест"], "игр": ["игры", "потусить"],
    "театр": ["театр"], "выставк": ["выставка", "галерея", "арт"], "купит": ["шопинг", "тц"],
    "шопинг": ["шопинг", "тц"], "парк": ["парк"], "гулят": ["прогулка", "парк"], "прогул": ["прогулка", "парк"], "закат": ["закат", "вид"], "фото": ["фото"], "вид": ["вид", "смотровая"],
}


REVIEWS = Path(__file__).parent / "data" / "reviews.json"
SERVICE_W = ("официант", "обслуж", "персонал", "сервис", "бариста", "администратор", "подач", "ждал", "ждать",
             "вежлив", "хам", "груб", "встрет", "кассир", "менеджер", "сотрудник")
POS_W = ("отлич", "прекрасн", "вежлив", "быстр", "приятн", "внимательн", "любезн", "дружелюбн", "супер", "класс",
         "рекоменд", "чисто", "уютн", "хорош", "замечательн", "улыб", "помог")
NEG_W = ("плох", "ужасн", "долго", "хам", "груб", "медленн", "грязн", "невкусн", "обман", "игнор", "хуже",
         "отвратит", "разочаров", "холодн", "неприятн", "не рекоменд", "очеред", "ждал")


def load_reviews():
    try:
        return json.loads(REVIEWS.read_text(encoding="utf-8"))
    except Exception:
        return []


def add_review(place_id, stars_, text):
    items = load_reviews()
    items.append(dict(place_id=place_id, stars=int(stars_), text=text.strip(), ts=datetime.now(TZ).isoformat(timespec="minutes")))
    REVIEWS.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")


def sentiment(text):
    """Грубый лексический анализ тональности про сервис -> (-1..1 | None, использованные предложения)."""
    sents = [x for x in re.split(r"[.!?\n]+", text.lower()) if x.strip()]
    rel = [x for x in sents if any(w in x for w in SERVICE_W)]
    pos = neg = 0
    for x in rel:
        n = sum(w in x for w in NEG_W)
        p = sum(w in x for w in POS_W) - (1 if "не рекоменд" in x else 0)
        # «не быстро / не вежливо» — отрицание переворачивает позитив
        flip = len(re.findall(r"\bне\s+(?:очень\s+)?(?:%s)" % "|".join(POS_W), x))
        pos += max(p - flip, 0); neg += n + flip
    if not rel or pos + neg == 0:
        return None, rel
    return (pos - neg) / (pos + neg), rel


def place_stats():
    """id -> dict(rating, service, reviews, items) по отзывам пользователей."""
    by = {}
    for r in load_reviews():
        by.setdefault(r["place_id"], []).append(r)
    out = {}
    for pid, rs in by.items():
        rating = sum(r["stars"] for r in rs) / len(rs)
        sv = [sentiment(r["text"])[0] for r in rs]
        sv = [3 + 2 * x for x in sv if x is not None]
        service = sum(sv) / len(sv) if sv else rating  # нет слов про сервис — берём звёзды
        out[pid] = dict(rating=round(rating, 1), service=round(service, 1), reviews=len(rs), items=rs)
    return out


def stem(w):
    return w[:5]


def tokens(text):
    return [stem(w) for w in re.findall(r"[a-zа-яё0-9]+", text.lower()) if len(w) > 2]


START_NAMES = r"mega silk way|мега силк вей|мега silk way|байтерек|хан шатыр|expo|экспо(?: 2017)?|набережн\w*"


def clean_query(query):
    """Убираем из запроса название точки, где стоит пользователь, чтобы оно не 'находило' места внутри этого здания."""
    return re.sub(START_NAMES, " ", query, flags=re.I)


def expand(query):
    extra = []
    for t in re.findall(r"[a-zа-яё0-9]+", query.lower()):
        for k, v in SYN.items():
            if t.startswith(k):
                extra += v
    return tokens(query + " " + " ".join(extra))


def doc_text(p):
    return " ".join([p["name"], p["category"], " ".join(p["tags"]) * 2, p["description"]])


DOCS = [Counter(tokens(doc_text(p))) for p in POIS]
DF = Counter(t for d in DOCS for t in d)
N = len(DOCS)


def haversine_km(a, b, c, d):
    r = 6371
    p1, p2 = math.radians(a), math.radians(c)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(d - b) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


DAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
DAY_RU = dict(Mo="пн", Tu="вт", We="ср", Th="чт", Fr="пт", Sa="сб", Su="вс", PH="праздники")
_DAY = "(?:Mo|Tu|We|Th|Fr|Sa|Su)"


def _mins(t):
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def parse_hours(raw):
    """OSM opening_hours (частые формы) -> [(дни, начало, конец)] или None, если не разобрали."""
    raw = re.sub(r"\bPH\b", "", raw).replace(" - ", "-").replace("–", "-").strip(" ,;")
    raw = re.sub(rf"({_DAY}),\s*(?=\d)", r"\1 ", raw)  # «Mo-Su, 10:00…» (после удаления PH)
    rules = [x.strip(" ,") for x in re.split(rf";|(?<=\d),\s*(?={_DAY}\b)", raw) if x.strip(" ,")]
    out = []
    for rule in rules:
        m = re.fullmatch(rf"((?:{_DAY}(?:-{_DAY})?)(?:\s*,\s*{_DAY}(?:-{_DAY})?)*)?\s*(\d{{1,2}}:\d\d\s*-\s*\d{{1,2}}:\d\d(?:\s*,\s*\d{{1,2}}:\d\d\s*-\s*\d{{1,2}}:\d\d)*)", rule)
        if not m:
            return None
        days = set()
        for part in (m[1] or "Mo-Su").split(","):
            part = part.strip()
            if "-" in part:
                s, e = (DAYS.index(x) for x in part.split("-"))
                days |= {(s + k) % 7 for k in range(((e - s) % 7) + 1)}
            else:
                days.add(DAYS.index(part))
        for rng in m[2].split(","):
            s, e = rng.replace(" ", "").split("-")
            out.append((days, _mins(s), _mins(e)))
    return out or None


def hours_ru(hours):
    """Человекочитаемая строка часов работы."""
    if not hours or hours.startswith("уточнить"):
        return "часы не указаны"
    if hours == "круглосуточно":
        return "круглосуточно"
    t = re.sub(r"\b(Mo|Tu|We|Th|Fr|Sa|Su|PH)\b", lambda m: DAY_RU[m[1]], hours.replace("24:00", "00:00"))
    t = re.sub(r"\s*-\s*", "–", t).replace("–", "–").replace(";", "; ")
    t = re.sub(r"(?<=[а-я])–(?=[а-я])", "–", t)
    return re.sub(r"\s+", " ", t.replace(",пн", ", пн")).strip()


def open_late(hours, now):
    """Работает ли место сегодня допоздна (до 23:30 и позже, в том числе через полночь). None — часы неизвестны."""
    if hours == "круглосуточно":
        return True
    if not hours or hours.startswith("уточнить"):
        return None
    rules = parse_hours(hours.replace("24:00", "00:00"))
    if not rules:
        return None
    today = now.weekday()
    return any(today in days and (b <= a or b >= 23 * 60 + 30) for days, a, b in rules) or False


def open_status(hours, now):
    """-> (True|False|None, текст). None = неизвестно."""
    text = hours_ru(hours)
    if hours == "круглосуточно":
        return True, text
    rules = None if (not hours or hours.startswith("уточнить")) else parse_hours(hours.replace("24:00", "00:00"))
    if not rules:
        return None, text
    today, cur = now.weekday(), now.hour * 60 + now.minute
    covered = set().union(*(days for days, _, _ in rules))
    ok = False
    for days, a, b in rules:
        if a < b:
            ok |= today in days and a <= cur < b
        else:  # окно через полночь
            ok |= (today in days and cur >= a) or (((today - 1) % 7) in days and cur < b)
    if not ok and today not in covered:
        return None, text  # на сегодняшний день недели часов в данных нет
    return ok, text


def quality(p):
    """Оценка заведения по рейтингу и сервису -> (балл 0-5 | None, ярлык, цвет)."""
    if p.get("rating") is None:
        return None, "нет оценок", "gray"
    q = 0.6 * p["rating"] + 0.4 * (p.get("service") or p["rating"])
    if q >= 4.3:
        return round(q, 1), "Хороший сервис", "green"
    if q >= 3.5:
        return round(q, 1), "Средний сервис", "orange"
    return round(q, 1), "Плохой сервис", "red"


def _inside(p, here):
    """Адрес заведения совпадает с адресом точки старта (оно в том же здании) — расстояние 0."""
    addr = (p.get("address") or "").lower()
    return bool(here) and any(k in addr for k in here)


def merge_stats(p0, stats):
    """Базовая оценка (2GIS, если есть) + отзывы пользователей, взвешенно по числу отзывов."""
    p, u = dict(p0), stats.get(p0["id"])
    p["user_reviews"] = u["items"] if u else []
    if u:
        n0, n1 = p0.get("reviews") or 0, u["reviews"]
        if p0.get("rating") and n0:
            p["rating"] = round((p0["rating"] * n0 + u["rating"] * n1) / (n0 + n1), 1)
            p["service"] = round(((p0.get("service") or p0["rating"]) * n0 + u["service"] * n1) / (n0 + n1), 1)
        else:
            p["rating"], p["service"] = u["rating"], u["service"]
        p["reviews"] = n0 + n1
    return p


def get_place(pid, lat, lon, now=None, here=()):
    """Одно место в том же формате, что выдаёт retrieve (для клика по карте)."""
    now = now or datetime.now(TZ)
    p0 = next(p for p in POIS if p["id"] == pid)
    p = merge_stats(p0, place_stats())
    dist = 0.0 if _inside(p, here) else haversine_km(lat, lon, p["lat"], p["lon"])
    qual, label, color = quality(p)
    is_open, status = open_status(p["hours"], now)
    return dict(p, dist_km=round(dist, 2), walk_min=max(1, round(dist / WALK_KMH * 60)), score=0, rel=0, criteria=[],
                open=is_open, status=status, quality=qual, quality_label=label, quality_color=color)


def retrieve(query, lat, lon, radius_km=2.0, k=5, now=None, categories=None, min_rating=0.0, groups=None, only_rated=False, group=1, here=(), weather_bad=False, nodist=False):
    now = now or datetime.now(TZ)
    query = clean_query(query)
    q = expand(query)
    out, stats = [], place_stats()
    intent = intent_categories(query) if not categories and " или " not in query.lower() else set()
    dog = bool(re.search(r"собак|питомц", query.lower()))
    for p0, d in zip(POIS, DOCS):
        p = merge_stats(p0, stats)
        if groups and p["group"] not in groups:
            continue
        if categories and p["category"] not in categories:
            continue
        if min_rating and (p.get("rating") or 0) < min_rating:
            continue
        dist = 0.0 if _inside(p, here) else haversine_km(lat, lon, p["lat"], p["lon"])  # заведение по адресу в этом здании
        if dist > radius_km:
            continue
        rel = sum((1 + math.log(d[t])) * math.log(1 + N / DF[t]) for t in set(q) if t in d) / math.sqrt(sum(d.values()))
        if q and rel < 0.15:
            continue  # нерелевантное не показываем
        qual, label, color = quality(p)
        is_open, status = open_status(p["hours"], now)
        if intent and p["category"] not in intent:
            continue  # в запросе прямо назван тип места («ресторан», «кофейня»…)
        if dog and not (_has(p, "с собакой") or p["category"] in OUTDOOR or _has(p, "терраса", "веранда")):
            continue  # с собакой: в помещения без отметки не предлагаем
        crit = assess(query, p)
        confirmed = any(c[1] is True and c[0] != "популярность" for c in crit)
        if only_rated and not p.get("rating") and not confirmed:
            continue  # без оценки скрываем, но не прячем место, у которого подтверждён критерий запроса
        pop = math.log10((p.get("reviews") or 0) + 1) / 5  # 0..1 по числу оценок
        asked_pop = any(c[0] == "популярность" for c in crit)
        # итог: релевантность + качество + близость + популярность; закрытые понижаем
        final = min(rel, 1.5) / 1.5 * 0.55 + ((qual or 3.5) / 5) * 0.3 + (0.075 if nodist else 0.15 / (1 + dist * 2)) + (0.35 if asked_pop else 0.08) * pop
        final += 0.3 * sum(1 for c in crit if c[1] is True and c[0] != "популярность")  # подтверждённые критерии запроса
        if any(c[0] == "красивый вид" and c[1] is True for c in crit) and p.get("floor"):
            final += 0.015 * min(p["floor"], 25)  # чем выше этаж, тем лучше обзор
        if group >= 3 and p["category"] in ("ресторан", "бар", "развлечения", "кино", "боулинг", "квесты", "тц"):
            final += 0.05  # для компании: места с большими залами и активностями
        if (now.hour >= 17 or now.hour < 4) and open_late(p["hours"], now):
            final += 0.04  # вечером и ночью выше места, которые работают допоздна
        if is_open is False:
            final *= 0.4
        if weather_bad and p["category"] in OUTDOOR:
            final *= 0.35  # плохая погода: уличные места ниже, тёплые выше
        out.append(dict(p, dist_km=round(dist, 2), walk_min=max(1, round(dist / WALK_KMH * 60)),
                        score=final, rel=rel, open=is_open, status=status, criteria=crit,
                        quality=qual, quality_label=label, quality_color=color))
    out.sort(key=lambda x: -x["score"])
    return out[:k]


STAY = {"кофейня": 30, "ресторан": 60, "фастфуд": 25, "бар": 60, "клуб": 120, "кино": 120, "театр": 120, "музей": 75,
        "галерея": 40, "арт-пространство": 45, "тц": 45, "парк": 40, "достопримечательность": 25, "смотровая": 25,
        "развлечения": 75, "кулинария": 15, "боулинг": 75, "квесты": 60, "игровой клуб": 60, "площадка для собак": 30}
ACTION = {
    "кофейня": "Возьмите кофе и десерт; для работы спросите про розетки и wi-fi.",
    "ресторан": "Забронируйте стол заранее; просите место у окна или на террасе, если они есть.",
    "фастфуд": "Быстрый перекус; в час пик возможна очередь.",
    "кулинария": "Готовые блюда с собой; ассортимент и часы уточните на месте.",
    "бар": "Уточните бронь и живую музыку.",
    "клуб": "Проверьте афишу, дресс-код и возраст.",
    "кино": "Выберите сеанс и возьмите билеты заранее.",
    "театр": "Посмотрите афишу и возьмите билеты заранее.",
    "музей": "Пройдите основную экспозицию; проверьте часы и выходные дни.",
    "галерея": "Осмотрите текущую выставку; уточните часы.",
    "тц": "Прогулка по галереям, кофе или кино; хороший вариант в плохую погоду.",
    "парк": "Неспешная прогулка по аллеям, хорошо для фото.",
    "достопримечательность": "Осмотр и фото; проверьте часы.",
    "развлечения": "Выберите активность; для адреналиновых форматов бронируйте заранее и уточните ограничения по возрасту и росту.",
    "площадка для собак": "Выгул с питомцем: поводок и пакеты.",
}


def _has(p, *tags):
    return bool(set(p["tags"]) & set(tags))


# понятия запроса: (регэксп по тексту, название, проверка -> True | False | None[нет данных])
def _popular(p):
    if not p.get("rating"):
        return None
    return p["rating"] >= 4.5 and (p.get("reviews") or 0) >= 500


CONCEPTS = [
    (r"вид|панорам|смотров", "красивый вид", lambda p: True if _has(p, "вид", "вид на город", "панорама", "смотровая", "высокий этаж") else None),
    (r"террас|веранд", "терраса или веранда", lambda p: True if _has(p, "терраса", "веранда") else None),
    (r"популярн|востребован|самый лучший", "популярность", _popular),
    (r"адренал|экстрим|драйв|скорост|картинг", "адреналин", lambda p: True if _has(p, "адреналин", "картинг", "дрифт") else None),
    (r"собак|питомц|пес\b|пёс", "можно с собакой", lambda p: True if _has(p, "с собакой", "площадка для собак", "собаки") else None),
    (r"коляск|инвалид|ограниченн|доступн", "доступность для колясок", lambda p: True if _has(p, "доступно для колясок") else None),
    (r"праздн|день рожден|дня рожден|юбил|отпраздн", "праздник", lambda p: True if _has(p, "праздник") else None),
    (r"тих|спокойн", "тихое место", lambda p: True if _has(p, "тихо") else None),
    (r"розетк", "розетки", lambda p: True if _has(p, "розетки") else None),
]


INTENT_CATS = [(r"ресторан", {"ресторан"}), (r"\bкафе\b", {"кофейня", "ресторан"}), (r"кофейн", {"кофейня"}), (r"музе", {"музей"}), (r"кинотеатр|сходить в кино", {"кино"}),
               (r"\bбар\b|паб", {"бар"})]
OUTDOOR = {"парк", "достопримечательность", "смотровая", "площадка для собак"}


def intent_categories(query):
    cats = set()
    for pat, cs in INTENT_CATS:
        if re.search(pat, query.lower()):
            cats |= cs
    return cats


def concepts_in(query):
    return [(lab, fn) for pat, lab, fn in CONCEPTS if re.search(pat, query.lower())]


def assess(query, p):
    """Критерии запроса для места: [(название, True|False|None, короткое пояснение)]."""
    out = []
    for lab, fn in concepts_in(query):
        v = fn(p)
        if lab == "популярность":
            if not p.get("rating"):
                note = "нет данных об оценках"
            elif v:
                note = f"{p['rating']} из 5, {p['reviews']} оценок"
            else:
                note = f"{p['rating']} из 5, но оценок всего {p['reviews']}"
        elif v:
            note = {"красивый вид": (f"вид на город с {p['floor']}-го этажа" if p.get("floor") else "вид на город"),
                    "терраса или веранда": "есть терраса или веранда", "адреналин": "картинг и дрифт",
                    "можно с собакой": "собаки разрешены", "доступность для колясок": "доступно для колясок",
                    "тихое место": "тихое место", "розетки": "есть розетки", "праздник": "подходит для праздника"}.get(lab, "подтверждено")
        else:
            note = "нет данных"
        out.append((lab, v, note))
    return out


def data_src(c):
    if str(c.get("source", "")).startswith("OpenStreetMap"):
        return "OpenStreetMap" + (" + оценка 2GIS" if c.get("rating") else "")
    return "2GIS, положение по адресу приблизительное"


def has_hours(p):
    return bool(p.get("hours")) and not str(p["hours"]).startswith("уточнить")


def hours_note(p):
    """Часы работы для показа: сами часы; если данных нет — только вероятность (без утверждений «открыто»)."""
    if has_hours(p):
        return p["status"], ""
    return "Часы не указаны", "вероятность неизвестна"


def hours_confidence(p):
    return {"2GIS": "высокая (2GIS)", "OSM": "средняя (OpenStreetMap)"}.get(p.get("hours_source", ""), "нет данных")


SYSTEM = """Ты — локальный гид по Астане. Отвечай на языке запроса пользователя, кратко и конкретно.
ПРАВИЛА:
1. Используй ТОЛЬКО места из блока «КОНТЕКСТ». Не придумывай места, адреса, цены, меню, розетки, террасы, разрешение для собак.
2. Дай 1–3 пункта. Каждый пункт — три короткие строки (до 100 символов каждая): «Почему» (только факты из контекста, помечай «данные POI»), «Время» (на месте и с дорогой), «Что делать» (живая конкретная идея, помечай «идея», это не данные). Формат:
   • Название (расстояние)
   • Данные POI: какие критерии запроса подтверждены данными, а какие нет («данных нет» — так и скажи).
   • Идея: конкретное действие; это сгенерированная идея, не данные из базы.
   • Данные: источник (OSM / 2GIS) и часы работы, если они есть.
3. Не пиши «открыто/закрыто сейчас» и не упоминай уверенность. Просто назови часы работы. Если часов нет — напиши, что часы не указаны и вероятность, что место работает, неизвестна.
4. Если ни одно место не подтверждает критерий запроса — прямо скажи, что в базе такого подтверждения нет, и предложи ближайшие варианты с оговоркой.
5. Если у пользователя достаточно времени, предложи мини-маршрут из 2–3 мест (без указания минут).
6. Если в группе 3 человека и больше — добавь совет для компании (бронь заранее, вместимость; для 10+ человек советуй звонить заранее).
7. Рейтинга может не быть — не выдумывай его."""


def build_prompt(query, minutes, ctx, now, group=1):
    lines = []
    for c in ctx:
        crit = "; ".join(f"{lab}: {'ДА' if v else 'НЕТ ДАННЫХ' if v is None else 'НЕТ'} ({note})" for lab, v, note in c.get("criteria", []))
        lines.append(f"- {c['name']} [{c['category']}] адрес: {c['address'] or 'нет'}; теги: {', '.join(c['tags'])}; {c['description']} "
                     f"Рейтинг: {c['rating'] or 'нет'} ({c['reviews']} оценок, источник {('2GIS' if c['rating'] else '—')}). "
                     f"{c['dist_km']} км от пользователя. "
                     f"Часы: {hours_note(c)[0]}{(' — ' + hours_note(c)[1]) if hours_note(c)[1] else ''}. Критерии запроса: {crit or '—'}.")
    return (f"Сейчас {now:%H:%M}, у пользователя {minutes} мин, человек в компании: {group}.\nЗапрос: {query}\n\n"
            "КОНТЕКСТ:\n" + "\n".join(lines))


def generate(query, minutes, ctx, now=None, group=1, anywhere=False):
    """Возвращает (текст, режим): режим «llm» — текст написал Gemini по найденным местам, «offline» — собран шаблонами."""
    now = now or datetime.now(TZ)
    key = os.getenv("GEMINI_API_KEY")
    if not ctx:
        return "В радиусе поиска нет подходящих мест в базе. Увеличьте радиус или уберите фильтры.", "offline"
    if key:
        try:
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')}:generateContent",
                headers={"x-goog-api-key": key}, timeout=30,
                json={"systemInstruction": {"parts": [{"text": SYSTEM}]},
                      "contents": [{"role": "user", "parts": [{"text": build_prompt(query, minutes, ctx, now, group)}]}],
                      "generationConfig": {"temperature": 0.4}})
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"], "llm"
        except Exception:
            return offline(query, ctx, minutes, group, anywhere), "offline"
    return offline(query, ctx, minutes, group, anywhere), "offline"


SCEN_IDEA = {
    "праздник": "Забронируйте стол и предупредите о празднике: спросите про торт, свечи, украшение.",
    "можно с собакой": "Возьмите поводок, пакеты и воду; правила для собак уточните на входе.",
    "доступность для колясок": "Место отмечено как доступное для колясок — спокойный визит без лишних препятствий.",
    "адреналин": "Бронируйте заезды заранее; уточните ограничения по возрасту и росту.",
    "красивый вид": "Приходите за ~30 минут до заката, просите стол у окна.",
}


SHORT_DO = {
    "кофейня": "Кофе и десерт; для работы — розетки и wi-fi", "ресторан": "Ужин у окна; бронь заранее", "бар": "Коктейли и музыка; уточните бронь",
    "клуб": "Ночь с музыкой: афиша и дресс-код", "кино": "Вечерний сеанс; билеты заранее", "театр": "Спектакль; афиша и билеты заранее",
    "музей": "Экспозиция за час; проверьте выходные", "галерея": "Выставка и тишина; уточните часы", "тц": "Прогулка, кофе и кино под одной крышей",
    "парк": "Неспешная прогулка и фото", "развлечения": "Активность на выбор; бронь и ограничения", "фастфуд": "Быстрый перекус",
    "кулинария": "Готовая еда с собой", "площадка для собак": "Выгул: поводок и пакеты", "достопримечательность": "Осмотр и фото",
}
SCEN_DO = {
    "красивый вид": "Столик у окна к закату — кадр с панорамой города",
    "адреналин": "Заезд на время: скорость, виражи и адреналин",
    "можно с собакой": "Весёлая прогулка вдвоём: новые места и запахи для хвостатого",
    "доступность для колясок": "Спокойный визит: место отмечено как доступное",
    "праздник": "Бронь на компанию, торт и свечи — предупредите заранее",
}


DOG_DO = {  # «что делать» с питомцем — по типу места
    "кофейня": "Кофе вдвоём с хвостатым: займите столик и дайте другу передохнуть у ваших ног",
    "ресторан": "Ужин вместе с питомцем: займите столик поудобнее и дайте другу передохнуть у ног",
    "площадка для собак": "Пусть набегается и подружится с другими собаками, а вы отдохнёте на скамейке",
    "парк": "Неспешная прогулка по аллеям: пусть хвостатый исследует новые запахи",
    "достопримечательность": "Неспешная прогулка по аллеям: пусть хвостатый исследует новые запахи",
}
FUN_DO = [  # «что делать» в развлекательных местах — по тематике места (теги), без еды и десертов
    (("картинг", "дрифт", "скорость"), "Заезд на время: газ в пол и вираж на скорости — кто быстрее, тот чемпион"),
    (("аквариум", "аттракционы"), "Аквариум, горки и аттракционы — день для всей семьи"),
    (("боулинг",), "Партия в боулинг: страйк решает всё"),
    (("квесты", "квест"), "Командный квест: загадки и побег на время"),
]


def fun_do(c):
    tags = set(c.get("tags") or [])
    for keys, text in FUN_DO:
        if tags & set(keys):
            return text
    return "Активность на выбор; бронь и ограничения"


BD_DO = {"ресторан": "Стол на компанию, торт и свечи — предупредите заранее", "бар": "Зал или столы для гостей, музыка и тосты",
         "развлечения": "Праздник в движении: заезды и аттракционы", "кофейня": "Сладкий стол: торт, пирожные и кофе для всех"}


def offline(query, ctx, minutes, group=1, anywhere=False):
    """Короткий ответ без LLM: у каждого места «Почему» (данные POI), «Время» и «Что делать» (идея)."""
    out, shown = [], []
    for c in ctx:
        if any(haversine_km(c["lat"], c["lon"], s["lat"], s["lon"]) < 0.12 for s in shown):
            continue  # то же здание — второй раз не предлагаем
        shown.append(c)
        if len(shown) == 3:
            break
    wanted = [lab for lab, _ in concepts_in(query) if lab != "популярность"]
    if wanted and not any(v is True for c in shown for lab, v, _ in c["criteria"] if lab != "популярность"):
        out.append("<div class='meta'>Подтверждённого места нет — ниже ближайшие варианты, проверьте перед визитом.</div>")
    scen_do = next((SCEN_DO[lab] for lab, _ in concepts_in(query) if lab in SCEN_DO), None)
    for n, c in enumerate(shown, 1):
        yes = [note for lab, v, note in c["criteria"] if v and lab != "популярность"]
        pop = [note for lab, v, note in c["criteria"] if lab == "популярность" and c.get("rating")]
        if c.get("rating") and not pop:
            pop = [f"{c['rating']} из 5, {c['reviews']} оценок"]
        no = [lab for lab, v, _ in c["criteria"] if v is None and lab != "популярность"]
        why = "; ".join(yes + pop) or "подходит по описанию"
        stay = STAY.get(c["category"], 45)
        total = 2 * c["walk_min"] + stay
        verdict = "успеваете" if total <= minutes else "не хватит времени"
        do = (BD_DO.get(c["category"]) if "праздник" in [lab for lab, _ in concepts_in(query)] else None) or scen_do or SHORT_DO.get(c["category"], "Загляните и оцените на месте")
        if any(lab == "можно с собакой" for lab, _ in concepts_in(query)) and c["category"] in DOG_DO:
            do = DOG_DO[c["category"]]
        if c["category"] == "развлечения":  # по тематике места, а не общий текст про еду и десерты
            do = fun_do(c)
        out.append(
            "<div class='rec'>"
            f"<div class='rec-h'>{n}. {c['name']}" + ("" if anywhere else f" <span>{c['dist_km']} км · {c['walk_min']} мин пешком</span>") + "</div>"
            f"<div class='kv'><span class='k'>Почему</span><span>{why[0].upper() + why[1:]}"
            + (f"<i class='nd'> · нет данных: {', '.join(no)}</i>" if no else "") + " <small class='src data'>данные POI</small></span></div>"
            f"<div class='kv'><span class='k'>Время</span><span>~{stay} мин на месте" + ("" if anywhere else f" · с дорогой {total} из {minutes} мин — {verdict}") + "</span></div>"
            f"<div class='kv'><span class='k'>Что делать</span><span>{do} <small class='src idea'>идея</small></span></div>"
            "</div>")
    if group >= 3:
        out.append(f"<div class='meta'>Для компании из {group}: " + "бронируйте заранее." + "</div>")
    return "\n".join(out)


def llm_text(prompt, system=None):
    """Короткий запрос к Gemini; None, если ключа нет или сервис недоступен."""
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    try:
        body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.6}}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')}:generateContent",
                          headers={"x-goog-api-key": key}, timeout=30, json=body)
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        return None
