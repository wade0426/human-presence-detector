<#
.SYNOPSIS
    以 PyInstaller 打包人體辨識休息提醒系統為 Windows onedir 應用程式。

.DESCRIPTION
    1) 確認 PyInstaller 已安裝（缺則依 requirements-build.txt 安裝）。
    2) 依 human_presence_detector.spec 打包（--noconfirm --clean）。
    3) 把 config.yaml 與 data/（model、assets）補到輸出資料夾，供程式以 CWD
       相對路徑讀取（程式啟動時會把工作目錄切到 exe 所在資料夾）。
    產物：dist/HumanPresenceDetector/，整包壓縮即可發佈。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File packaging\build.ps1
#>
[CmdletBinding()]
param(
    # 略過安裝 PyInstaller 的檢查（CI 已預先備妥環境時使用）。
    [switch]$SkipInstall
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$appName = 'HumanPresenceDetector'
$spec = Join-Path $PSScriptRoot 'human_presence_detector.spec'
$dist = Join-Path $root (Join-Path 'dist' $appName)

Push-Location $root
try {
    Write-Host "==> 專案根目錄：$root" -ForegroundColor Cyan

    if (-not $SkipInstall) {
        python -c "import PyInstaller" 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Host '==> 安裝 PyInstaller…' -ForegroundColor Cyan
            python -m pip install -r (Join-Path $PSScriptRoot 'requirements-build.txt')
            if ($LASTEXITCODE -ne 0) { throw 'PyInstaller 安裝失敗。' }
        }
    }

    Write-Host '==> 執行 PyInstaller…' -ForegroundColor Cyan
    python -m PyInstaller $spec --noconfirm --clean --distpath (Join-Path $root 'dist') --workpath (Join-Path $root 'build')
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller 打包失敗。' }

    if (-not (Test-Path $dist)) { throw "找不到輸出資料夾：$dist" }

    Write-Host '==> 補上 config.yaml 與 data/（供 CWD 相對路徑讀取）…' -ForegroundColor Cyan
    Copy-Item (Join-Path $PSScriptRoot 'config.dist.yaml') (Join-Path $dist 'config.yaml') -Force

    $distAssets = Join-Path $dist 'data\assets'
    $distModel = Join-Path $dist 'data\model'
    New-Item -ItemType Directory -Force -Path $distAssets | Out-Null
    New-Item -ItemType Directory -Force -Path $distModel | Out-Null

    Copy-Item (Join-Path $root 'data\assets\*') $distAssets -Recurse -Force
    Copy-Item (Join-Path $root 'data\model\yolov8n.pt') $distModel -Force

    Write-Host ''
    Write-Host "✓ 打包完成：$dist" -ForegroundColor Green
    Write-Host "  直接執行 $appName.exe，或整包壓縮後發佈。" -ForegroundColor Green
    Write-Host '  首次使用請依實機調整 config.yaml 的 source 與 presence.roi。' -ForegroundColor Green
}
finally {
    Pop-Location
}
