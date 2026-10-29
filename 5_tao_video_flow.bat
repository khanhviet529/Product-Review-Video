@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Dung:  5_tao_video_flow.bat 02        -> xem ke hoach (khong ton tin dung)
rem        5_tao_video_flow.bat 02 --go   -> tao cac clip con thieu tren Flow + tai ve inbox\
call tools\py.cmd tools\flow\run_product.py %*
echo.
echo Neu da tai du clip: chay 3_nhap_video_va_xoa_logo.bat roi 4_ghep_video.bat %1
pause
