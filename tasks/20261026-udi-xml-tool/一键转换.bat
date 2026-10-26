@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

REM --- 有拖入的文件则直接处理，否则进入交互 ---
python run.py %*
set RC=%ERRORLEVEL%

if "%RC%"=="0" echo.
pause
exit /b %RC%
