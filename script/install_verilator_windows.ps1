$ErrorActionPreference = "Stop"

$WorkDir = "D:\a\verilator"
$InstallDir = "D:\a\verilator\install"
$WinFlexBisonDir = "D:\a\winflexbison"

if (-not (Test-Path $WorkDir)) {
    New-Item -ItemType Directory -Path $WorkDir -Force | Out-Null
}

# Locate the MSVC developer environment up front; editbin/dumpbin below need it
# on both the cached and freshly-built paths.
$vsInstallPath = & "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe" -all -products * -latest -property installationPath
$vsInstallPath = $vsInstallPath.Trim()
Write-Host "Found Visual Studio at: $vsInstallPath"

$vcvarsPath = Join-Path $vsInstallPath "Common7\Tools\vsdevcmd.bat"
if (-not (Test-Path $vcvarsPath)) {
    $vcvarsPath = Join-Path $vsInstallPath "VC\Auxiliary\Build\vcvars64.bat"
}
Write-Host "Using vcvars: $vcvarsPath"

# Verilator recurses deeply over the AST and MSVC's default 1 MB stack overflows
# on large designs (e.g. uvm_pkg.sv), surfacing as an access violation. On Linux
# the verilator Perl wrapper runs `ulimit -s unlimited`; there is no such step on
# Windows, so force a large stack reserve on the installed binaries via editbin,
# then print the resulting value so the CI log shows what actually took effect.
function Set-VerilatorStack {
    $stackReserve = 536870912  # 512 MB
    foreach ($exeName in @("verilator_bin.exe", "verilator_bin_dbg.exe")) {
        $exe = Join-Path $InstallDir "bin\$exeName"
        if (Test-Path $exe) {
            Write-Host "Setting stack reserve on $exeName to $stackReserve"
            & cmd /c """$vcvarsPath"" && editbin /STACK:$stackReserve ""$exe"""
            if ($LASTEXITCODE -ne 0) {
                Write-Error "editbin /STACK failed for $exeName"
                exit 1
            }
            & cmd /c """$vcvarsPath"" && dumpbin /headers ""$exe"" | findstr /C:""size of stack reserve"""
        }
    }
}

$installMarker = Join-Path $InstallDir "bin\verilator_bin.exe"
if (Test-Path $installMarker) {
    Write-Host "Verilator already built, skipping compile/install steps"
    # Skip Set-VerilatorStack on cache hit -- the binary was already patched by
    # editbin during the original build.  Running editbin a second time on a
    # cached binary corrupts the PE header ("inappropriate file type or format").
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

Write-Host "Configuring verilator with CMake + Ninja (Debug)..."
& cmd /c """$vcvarsPath"" && cmake .. -G Ninja -DCMAKE_BUILD_TYPE=Debug -DCMAKE_INSTALL_PREFIX=""$InstallDir"" -DFLEX_EXECUTABLE=""$WinFlexBisonDir\flex.exe"" -DBISON_EXECUTABLE=""$WinFlexBisonDir\bison.exe"""

if ($LASTEXITCODE -ne 0) {
    Write-Error "cmake configuration failed"
    exit 1
}

Write-Host "Building verilator (Debug)..."
& cmd /c """$vcvarsPath"" && cmake --build . --config Debug"
if ($LASTEXITCODE -ne 0) {
    Write-Error "cmake build failed"
    exit 1
}

Write-Host "Installing verilator (Debug)..."
& cmd /c """$vcvarsPath"" && cmake --install . --prefix ""$InstallDir"" --config Debug"
if ($LASTEXITCODE -ne 0) {
    Write-Error "cmake install failed"
    exit 1
}

# Temporarily disabled: Set-VerilatorStack
# editbin /STACK appears to corrupt the Debug binary's PE header on GitHub
# Windows runners, causing "inappropriate file type or format" when the Perl
# wrapper tries to launch verilator_bin_dbg.exe.  First verify the binary
# works without the stack-reserve tweak; if the crash is a genuine stack
# overflow we can re-enable with a safer approach later.
# Set-VerilatorStack

$env:VERILATOR_ROOT = $InstallDir
$env:PATH = "$InstallDir\bin;$env:PATH"
Write-Host "Verilator installed to $InstallDir"