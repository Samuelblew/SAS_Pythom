@echo off
setlocal
cd /d "%~dp0"

echo Iniciando a API Python em http://localhost:5203
start "IAS API" cmd /k "cd /d "%~dp0Backend" && if not exist .venv\Scripts\python.exe python -m venv .venv && call .venv\Scripts\activate.bat && python -m pip install -r requirements.txt && python -m uvicorn app.main:app --host 127.0.0.1 --port 5203"

echo Iniciando o site em http://localhost:5173
start "IAS Web" cmd /k "cd /d "%~dp0Frontend" && npm run dev"

echo Aguardando a API e o site subirem...
timeout /t 8 /nobreak >nul
start "" "http://localhost:5173"

echo.
echo API:  http://localhost:5203
echo Site: http://localhost:5173
echo Feche as janelas "IAS API" e "IAS Web" para encerrar.
pause
