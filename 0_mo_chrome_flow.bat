@echo off
chcp 65001 >nul
rem Mo Chrome rieng (profile luu dang nhap Google) o cong 9222 de tool dieu khien Flow. Dang nhap Google 1 lan.
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="%~dp0tools\chrome_profile" --no-first-run "https://flow.google.com"
