@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Xep video trong inbox\ vao dung san pham ===
call tools\py.cmd tools\import_inbox.py
echo.
echo === Xoa logo cac clip moi ===
call tools\py.cmd tools\clean_batch.py
call tools\py.cmd tools\build_panel.py
pause
