@echo off
chcp 65001 >nul
cd /d "%~dp0"
call tools\py.cmd tools\find_images.py %*
call tools\py.cmd tools\build_panel.py
pause
