# Гид по Астане — ИИ-помощник по прогулкам (RAG)

Документация: [docs/PROJECT.md](docs/PROJECT.md) (концепция, RAG, этика, ограничения), [docs/TEST_SCENARIOS.md](docs/TEST_SCENARIOS.md) (тестовые сценарии).

## Запуск на любом компьютере (достаточно передать папку)
Нужен только Python 3.10+ и интернет при первом запуске.
- **Mac / Linux:** двойной клик по `start.command` (или в терминале `./start.command`).
- **Windows:** двойной клик по `start.bat`.

Скрипт сам создаёт окружение, ставит зависимости и открывает сайт на `http://localhost:8501`. С телефона в той же Wi-Fi сети сайт откроется по адресу, который скрипт покажет в окне (`http://<IP>:8501`). Первый запуск занимает 1–3 минуты, следующие — несколько секунд.
Папки `.venv` и `.venv-run` можно не передавать, они создаются заново.
**Windows:** если при установке Python не отметили «Add Python to PATH», `start.bat` подскажет. При первом запуске Windows может спросить про брандмауэр: нажмите «Разрешить доступ» (нужно только для открытия с телефона).

Вручную:
```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
export GEMINI_API_KEY=...        # необязательно: без ключа работает шаблонный ответ
.venv/bin/streamlit run app.py
```
Публикация в интернете: https://hackaton-build-with-ai.onrender.com

## Данные (автоматизированный сбор)
```
.venv/bin/python scripts/fetch_osm.py        # места из OpenStreetMap -> data/osm_raw.json
.venv/bin/python scripts/fetch_food.py       # еда и кофе (мелкими запросами)
.venv/bin/python scripts/fetch_dog.py        # отметки «с собакой», площадки для выгула
.venv/bin/python scripts/match_ratings.py    # сопоставление data/ratings.csv (2GIS, вручную) с OSM по адресу
.venv/bin/python scripts/force_unmatched.py  # привязка оставшихся строк / новые точки по адресу
.venv/bin/python scripts/build_pois.py       # сборка data/pois.json (только места с адресом)
DGIS_API_KEY=... .venv/bin/python scripts/enrich_2gis.py   # опционально: оценки из API 2GIS
```
