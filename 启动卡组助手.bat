@echo off
chcp 65001 >nul
cd /d "%~dp0"

tasklist /FI "IMAGENAME eq PlantsVsZombies.exe" 2>nul | find /I "PlantsVsZombies.exe" >nul
if errorlevel 1 (
    if exist "pvzHE-Launcher.exe" (
        start "" "pvzHE-Launcher.exe"
    )
)

if exist "杂交版卡组助手.exe" (
    start "" "杂交版卡组助手.exe"
    exit /b 0
)

where python >nul 2>nul
if errorlevel 1 (
    echo 未找到 Python，也未找到打包后的“杂交版卡组助手.exe”。
    echo 请到 GitHub Releases 下载完整文件。
    pause
    exit /b 1
)

start "" pythonw "pvz_deck_assistant.py"
