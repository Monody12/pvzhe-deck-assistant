$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".build-venv\Scripts\python.exe")) {
    python -m venv .build-venv
}

& ".build-venv\Scripts\python.exe" -m pip install --disable-pip-version-check -U pip pyinstaller
# --console 避免 Python 3.14 无窗口包在图鉴抢焦点时 abort。控制台图标保持黑色。
& ".build-venv\Scripts\python.exe" -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --console `
    --noupx `
    --name "杂交版卡组助手" `
    --distpath "." `
    --workpath ".build" `
    "pvz_deck_assistant.py"

Write-Host "构建完成：$PSScriptRoot\杂交版卡组助手.exe"
