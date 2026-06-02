@echo off
REM ============================================
REM   Iniciar o projeto Nexy
REM ============================================
cd /d "%~dp0"

echo Iniciando o servidor Nexy...
echo.

REM Verifica se a venv existe; se nao, cria e instala dependencias
if not exist ".venv\Scripts\python.exe" (
    echo [1/2] Criando ambiente virtual e instalando dependencias...
    py -m venv .venv
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install Flask Flask-SocketIO requests mysql-connector-python Werkzeug pyngrok python-dotenv
)

echo [2/2] Subindo o servidor em http://127.0.0.1:5000/
echo.

REM Abre o navegador apos alguns segundos (em paralelo)
start "" cmd /c "timeout /t 3 >nul & start http://127.0.0.1:5000/"

REM Roda o servidor (Ctrl+C para parar)
".venv\Scripts\python.exe" backend\app.py

pause
