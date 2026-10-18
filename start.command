#!/bin/bash
# Запуск «Гида по Астане» на Mac / Linux: двойной клик (Mac) или  ./start.command
cd "$(dirname "$0")" || exit 1
PORT="${PORT:-8501}"
PY="$(command -v python3 || command -v python)"
if [ -z "$PY" ]; then
  echo "Не найден Python. Установите Python 3.10+ с https://www.python.org/downloads/ и запустите файл снова."; read -r -p "Нажмите Enter…" _; exit 1
fi
if [ ! -x ".venv-run/bin/python" ]; then
  echo "Первый запуск: создаю окружение (1–3 минуты, нужен интернет)…"
  "$PY" -m venv .venv-run || { echo "Не удалось создать окружение."; read -r -p "Нажмите Enter…" _; exit 1; }
fi
if ! .venv-run/bin/python -c "import streamlit, pydeck, requests" >/dev/null 2>&1; then
  echo "Устанавливаю зависимости…"
  .venv-run/bin/python -m pip install -q --upgrade pip
  .venv-run/bin/python -m pip install -q -r requirements.txt || { echo "Не удалось установить зависимости (проверьте интернет)."; read -r -p "Нажмите Enter…" _; exit 1; }
fi
LAN="$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}')"
echo ""
echo "  Сайт откроется на этом компьютере:  http://localhost:$PORT"
[ -n "$LAN" ] && echo "  С телефона в той же Wi-Fi сети:      http://$LAN:$PORT"
echo "  Остановить: Ctrl+C или закрыть это окно."
echo ""
if [ -z "$NO_BROWSER" ]; then
  ( sleep 4; (open "http://localhost:$PORT" || xdg-open "http://localhost:$PORT") >/dev/null 2>&1 ) &
fi
exec .venv-run/bin/python -m streamlit run app.py --server.headless true --server.address 0.0.0.0 --server.port "$PORT" --browser.gatherUsageStats false
