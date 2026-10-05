@echo off
rem JARVIS show mode: wait for two claps, then jingle + services + web interface + voice chat.
rem Options are passed through, e.g.:  jarvis-show.cmd --list-devices   |   --calibrate   |   --activate-now
rem Environment variables (optional): JARVIS_MIC (device index or name), JARVIS_CLAP_THRESH (higher = less sensitive),
rem JARVIS_OPENJARVIS_DIR (default: ..\..\jarvis), JARVIS_JINGLE (path to a custom jingle).
setlocal
if not defined UV_PROJECT_ENVIRONMENT set "UV_PROJECT_ENVIRONMENT=%USERPROFILE%\.venvs\openjarvis"
set "PY=%UV_PROJECT_ENVIRONMENT%\Scripts\python.exe"
if not exist "%PY%" (
  echo Python environment not found: %PY%
  echo See JARVIS-WINDOWS.md ^(installation^).
  exit /b 1
)
set "PYTHONPATH=%~dp0;%PYTHONPATH%"
"%PY%" -m jarvis_show %*
