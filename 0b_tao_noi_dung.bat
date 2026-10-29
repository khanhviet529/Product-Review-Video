@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Dung:  0b_tao_noi_dung.bat 01              -> sinh research.json + script.json cho san pham 01
rem        0b_tao_noi_dung.bat 01 --all-steps  -> sinh + build prompts + tai anh + cap nhat bang
rem        0b_tao_noi_dung.bat --todo --all-steps -> xu ly moi san pham chua co noi dung
rem        0b_tao_noi_dung.bat --force 01 --all-steps -> ghi de neu da co
call tools\py.cmd tools\generate_content.py %*
echo.
echo Buoc tiep: chay 1_tao_bang_dieu_khien.bat de xem ket qua
pause
