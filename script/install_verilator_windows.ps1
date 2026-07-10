$ErrorActionPreference = "Stop"

$WorkDir = "D:\a\verilator"
$InstallDir = "D:\a\verilator\install"
$WinFlexBisonDir = "D:\a\winflexbison"

if (-not (Test-Path $WorkDir)) {
    New-Item -ItemType Directory -Path $WorkDir -Force | Out-Null
}

$installMarker = Join-Path $InstallDir "bin\verilator_bin.exe"
if (Test-Path $installMarker) {
    Write-Host "Verilator already built, skipping compile/install steps"
    $env:VERILATOR_ROOT = $InstallDir
    $env:PATH = "$InstallDir\bin;$env:PATH"
    exit 0
}

if (-not (Test-Path $WinFlexBisonDir)) {
    Write-Host "Downloading winflexbison..."
    $zipUrl = "https://github.com/lexxmark/winflexbison/releases/download/v2.5.25/win_flex_bison-2.5.25.zip"
    $zipPath = Join-Path $WorkDir "winflexbison.zip"
    Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath -UseBasicParsing
    Expand-Archive -Path $zipPath -DestinationPath $WinFlexBisonDir -Force
    Remove-Item $zipPath -Force

    $flexExe = Join-Path $WinFlexBisonDir "win_flex.exe"
    $bisonExe = Join-Path $WinFlexBisonDir "win_bison.exe"
    Copy-Item $flexExe (Join-Path $WinFlexBisonDir "flex.exe") -Force
    Copy-Item $bisonExe (Join-Path $WinFlexBisonDir "bison.exe") -Force
}

$env:WIN_FLEX_BISON = $WinFlexBisonDir
$env:PATH = "$WinFlexBisonDir;$env:PATH"

$vsInstallPath = & "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe" -all -products * -latest -property installationPath
$vsInstallPath = $vsInstallPath.Trim()
Write-Host "Found Visual Studio at: $vsInstallPath"

$vcvarsPath = Join-Path $vsInstallPath "Common7\Tools\vsdevcmd.bat"
if (-not (Test-Path $vcvarsPath)) {
    $vcvarsPath = Join-Path $vsInstallPath "VC\Auxiliary\Build\vcvars64.bat"
}
Write-Host "Using vcvars: $vcvarsPath"

Set-Location $WorkDir

if (-not (Test-Path "verilator\.git")) {
    Write-Host "Cloning verilator..."
    git clone --depth 1 https://github.com/verilator/verilator.git
}

Set-Location verilator

$buildDir = Join-Path $WorkDir "verilator\build"
if (-not (Test-Path $buildDir)) {
    New-Item -ItemType Directory -Path $buildDir -Force | Out-Null
}

Set-Location $buildDir

Write-Host "Configuring verilator with CMake + Ninja..."
& cmd /c """$vcvarsPath"" && cmake .. -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=""$InstallDir"" -DFLEX_EXECUTABLE=""$WinFlexBisonDir\flex.exe"" -DBISON_EXECUTABLE=""$WinFlexBisonDir\bison.exe"""

if ($LASTEXITCODE -ne 0) {
    Write-Error "cmake configuration failed"
    exit 1
}

Write-Host "Building verilator..."
& cmd /c """$vcvarsPath"" && cmake --build . --config Release"
if ($LASTEXITCODE -ne 0) {
    Write-Error "cmake build failed"
    exit 1
}

Write-Host "Installing verilator..."
& cmd /c """$vcvarsPath"" && cmake --install . --prefix ""$InstallDir"""
if ($LASTEXITCODE -ne 0) {
    Write-Error "cmake install failed"
    exit 1
}

$env:VERILATOR_ROOT = $InstallDir
$env:PATH = "$InstallDir\bin;$env:PATH"
Write-Host "Verilator installed to $InstallDir"
