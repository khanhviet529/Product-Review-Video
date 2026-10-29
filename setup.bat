@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Cai dat 1 lan: tao .venv rieng va cai thu vien. Can: Python (hoac uv), FFmpeg trong PATH, Google Chrome.
where uv >nul 2>nul && (uv venv .venv && uv pip install --python .venv\Scripts\python.exe -r requirements.txt) || (py -m venv .venv && .venv\Scripts\python.exe -m pip install -r requirements.txt)
echo.
echo Xong. Tiep theo: 0_mo_chrome_flow.bat (dang nhap Google), roi 6_lam_het_mot_san_pham.bat 24
pause
