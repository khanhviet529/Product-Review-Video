@echo off
chcp 65001 >nul
cd /d "%~dp0"
call tools\py.cmd tools\validate.py
call tools\py.cmd tools\build_panel.py
start "" control_panel.html
pause
