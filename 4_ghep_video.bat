@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Dung:  4_ghep_video.bat 07      (mot san pham)   hoac   4_ghep_video.bat --all
call tools\py.cmd tools\assemble.py %*
pause
