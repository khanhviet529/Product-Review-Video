@echo off
rem Python rieng cua du an (tools\..\.venv). Tao bang: setup.bat
if not exist "%~dp0..\.venv\Scripts\python.exe" (
  echo Chua co moi truong Python. Chay setup.bat truoc.
  exit /b 1
)
"%~dp0..\.venv\Scripts\python.exe" %*
