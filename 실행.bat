@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
if not exist "%PY%" set PY=python
"%PY%" 사진변환.py
echo.
echo 끝났어요. 아무 키나 누르면 창이 닫혀요.
pause >nul
