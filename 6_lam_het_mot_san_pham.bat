@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Dung:  6_lam_het_mot_san_pham.bat 24          -> xem ke hoach (khong ton tin dung)
rem        6_lam_het_mot_san_pham.bat 24 --go     -> tao clip tren Flow, tai ve, xoa logo, ghep thanh video trong final\
call tools\py.cmd tools\make_video.py %*
pause
