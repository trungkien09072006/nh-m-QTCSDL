@echo off
title NovaPath AI Learning Platform
cd /d "%~dp0"
set "PATH=C:\Users\PC\.tools\node-v20.18.0-win-x64;%PATH%"
if not defined SQL_SERVER set "SQL_SERVER=."
echo ========================================================
echo   KHOI DONG HE THONG NOVAPATH (AI LEARNING PLATFORM)
echo ========================================================
echo [1/2] Dang chuan hoa toan bo tieng Viet Unicode trong Database...
python scripts\fix_vietnamese_encoding.py
echo [2/2] Dang bat he thong Web va Ung dung...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-novapath.ps1
pause
