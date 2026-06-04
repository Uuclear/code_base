# Download and extract PaddleOCR-json into ScanReport/tools/PaddleOCR-json/
# Release: https://github.com/hiroi-sora/PaddleOCR-json/releases

$ErrorActionPreference = "Stop"
$Version = "v1.4.1"
$Asset = "PaddleOCR-json_${Version}_windows_x64.7z"
$Url = "https://github.com/hiroi-sora/PaddleOCR-json/releases/download/$Version/$Asset"
$Tools = Join-Path $PSScriptRoot ".." "tools" | Resolve-Path -ErrorAction SilentlyContinue
if (-not $Tools) {
    $Tools = (Join-Path $PSScriptRoot ".." "tools")
    New-Item -ItemType Directory -Force -Path $Tools | Out-Null
    $Tools = (Resolve-Path $Tools).Path
}
$Archive = Join-Path $Tools $Asset
$Dest = Join-Path $Tools "PaddleOCR-json"

Write-Host "Downloading $Url ..."
Invoke-WebRequest -Uri $Url -OutFile $Archive -UseBasicParsing

$7z = @(
    "${env:ProgramFiles}\7-Zip\7z.exe",
    "${env:ProgramFiles(x86)}\7-Zip\7z.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $7z) {
    throw "7-Zip not found. Install 7-Zip (winget install 7zip.7zip) and retry."
}

$ExtractRoot = Join-Path $Tools "PaddleOCR-json_$($Version.TrimStart('v'))"
if (Test-Path $ExtractRoot) { Remove-Item $ExtractRoot -Recurse -Force }
& $7z x "-o$Tools" "-y" $Archive | Out-Host
if (Test-Path $Dest) { Remove-Item $Dest -Recurse -Force }
Rename-Item $ExtractRoot $Dest
Remove-Item $Archive -Force

$exe = Join-Path $Dest "PaddleOCR-json.exe"
if (-not (Test-Path $exe)) { throw "Missing $exe after extract." }
Write-Host "OK: $exe"
