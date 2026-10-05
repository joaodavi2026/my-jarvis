@echo off
rem JARVIS normal mode: make sure Ollama and the OpenJarvis server are up and open the web interface.
rem No claps, no jingle, no voice chat. For voice, run:  uv run jarvis chat --voice  (in the OpenJarvis folder)
setlocal
call "%~dp0jarvis-show.cmd" --activate-now --no-voice --no-jingle %*
