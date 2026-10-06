$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".build-venv\Scripts\python.exe")) {
    python -m venv .build-venv
}

& ".build-venv\Scripts\python.exe" -m pip install --disable-pip-version-check -U pip pyinstaller

# --console 避免 Python 3.14 无窗口包在图鉴抢焦点时 abort。
# 控制台 bootloader 默认是黑图标，改用 py.ico，资源管理器里仍是白色 Python 图标。
$basePrefix = & ".build-venv\Scripts\python.exe" -c "import sys; print(sys.base_prefix)"
$icon = Join-Path $basePrefix "DLLs\py.ico"
if (-not (Test-Path -LiteralPath $icon)) {
    $icon = Join-Path $basePrefix "pythonw.exe"
}
if (-not (Test-Path -LiteralPath $icon)) {
    throw "未找到 Python 图标（DLLs\\py.ico 或 pythonw.exe）"
}

& ".build-venv\Scripts\python.exe" -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --console `
    --noupx `
    --icon $icon `
    --name "杂交版卡组助手" `
    --distpath "." `
    --workpath ".build" `
    "pvz_deck_assistant.py"

Write-Host "构建完成：$PSScriptRoot\杂交版卡组助手.exe"
