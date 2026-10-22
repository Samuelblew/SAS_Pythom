@echo off
setlocal
cd /d "%~dp0Backend"

if not exist ".venv\Scripts\python.exe" (
  echo Criando ambiente Python...
  python -m venv .venv
)

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt

echo Iniciando a API Python e o Swagger em http://localhost:5203/swagger
start "Abrir Swagger" cmd /c "timeout /t 5 /nobreak >nul && start "" http://localhost:5203/swagger"

python -m uvicorn app.main:app --host 127.0.0.1 --port 5203
