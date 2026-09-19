@echo off
setlocal EnableExtensions
REM ============================================================
REM  IA Financeira — launcher Windows (duplo clique)
REM  Abre a GUI tkinter. Programa CLI: python -m ia_financeira
REM ============================================================

cd /d "%~dp0\.."

set "PYTHONPATH=%CD%\src"
set "PYEXE="

if exist "%CD%\.venv\Scripts\pythonw.exe" set "PYEXE=%CD%\.venv\Scripts\pythonw.exe"
if not defined PYEXE if exist "%CD%\.venv\Scripts\python.exe" set "PYEXE=%CD%\.venv\Scripts\python.exe"
if not defined PYEXE where pythonw >nul 2>&1 && set "PYEXE=pythonw"
if not defined PYEXE set "PYEXE=python"

echo.
echo  IA Financeira Local
echo  Repo: %CD%
echo  Entrada CLI:  python -m ia_financeira
echo  Entrada GUI:  python -m ia_financeira.gui
echo  Python:       %PYEXE%
echo.

REM Prefer GUI without console when using pythonw; fall back to console python.
"%PYEXE%" -m ia_financeira.gui
if errorlevel 1 (
  echo.
  echo  Falha ao abrir a GUI. Tentando com python console...
  if exist "%CD%\.venv\Scripts\python.exe" (
    "%CD%\.venv\Scripts\python.exe" -m ia_financeira.gui
  ) else (
    python -m ia_financeira.gui
  )
  if errorlevel 1 (
    echo.
    echo  ERRO: nao foi possivel iniciar. Crie o venv e instale deps:
    echo    python -m venv .venv
    echo    .venv\Scripts\activate
    echo    pip install -r requirements.txt
    pause
    exit /b 1
  )
)

endlocal
exit /b 0
