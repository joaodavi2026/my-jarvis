@echo off
rem JARVIS show mode: wait for two claps, then jingle + services + web interface + voice chat.
rem Options: --monitor / --calibrate / --dry-run / --list-devices / --activate-now / --keep-listening / --quiet
rem Environment (optional): JARVIS_MIC (device index or name), JARVIS_CLAP_THRESH (higher = less sensitive),
rem JARVIS_OPENJARVIS_DIR (default: two folders up, jarvis), JARVIS_JINGLE (path to a custom jingle).
setlocal
chcp 65001 >nul
set PYTHONUNBUFFERED=1
if not defined UV_PROJECT_ENVIRONMENT set "UV_PROJECT_ENVIRONMENT=%USERPROFILE%\.venvs\openjarvis"
set "PY=%UV_PROJECT_ENVIRONMENT%\Scripts\python.exe"
if not exist "%PY%" (
  echo [JARVIS] ERRO: ambiente Python nao encontrado: %PY%
  echo [JARVIS] Defina UV_PROJECT_ENVIRONMENT ou veja docs\JARVIS-WINDOWS.md
  pause
  exit /b 1
)
set "PYTHONPATH=%~dp0;%PYTHONPATH%"
"%PY%" -m jarvis_show %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo [JARVIS] terminou com codigo %RC%
  pause
)
exit /b %RC%
