@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
if "%PORT%"=="" set PORT=8501
set "PY="
py -3 -c "import sys" >nul 2>nul && set "PY=py -3"
if not defined PY python -c "import sys" >nul 2>nul && set "PY=python"
if not defined PY (
  echo Python not found / Не найден Python.
  echo Install Python 3.10+ from https://www.python.org/downloads/  and tick "Add Python to PATH".
  echo Установите Python 3.10+ с https://www.python.org/downloads/ и отметьте "Add Python to PATH", затем запустите файл снова.
  pause
  exit /b 1
)
%PY% -c "import sys;sys.exit(0 if sys.version_info>=(3,10) else 1)"
if errorlevel 1 (
  echo Нужен Python 3.10 или новее / Python 3.10+ is required.
  pause
  exit /b 1
)
if not exist ".venv-run\Scripts\python.exe" (
  echo Первый запуск: создаю окружение, 1-3 минуты, нужен интернет...
  %PY% -m venv .venv-run
  if errorlevel 1 (
    echo Не удалось создать окружение.
    pause
    exit /b 1
  )
)
".venv-run\Scripts\python.exe" -c "import streamlit, pydeck, requests" >nul 2>nul
if errorlevel 1 (
  echo Устанавливаю зависимости...
  ".venv-run\Scripts\python.exe" -m pip install -q --upgrade pip
  ".venv-run\Scripts\python.exe" -m pip install -q -r requirements.txt
  if errorlevel 1 (
    echo Не удалось установить зависимости. Проверьте интернет.
    pause
    exit /b 1
  )
)
echo.
echo   Сайт откроется на этом компьютере:  http://localhost:%PORT%
echo   Если Windows спросит про брандмауэр, нажмите "Разрешить доступ" (нужно только для телефона в той же Wi-Fi).
echo   Остановить: закрыть это окно.
echo.
if "%NO_BROWSER%"=="" start "" /b cmd /c "timeout /t 5 >nul & start http://localhost:%PORT%"
".venv-run\Scripts\python.exe" -m streamlit run app.py --server.headless true --server.address 0.0.0.0 --server.port %PORT% --browser.gatherUsageStats false
if errorlevel 1 pause
