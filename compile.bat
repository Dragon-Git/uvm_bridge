@echo off
REM Windows build script for svuvm
REM Requires: Python, CMake, Visual Studio or MinGW, Verilator (optional for simulation)

setlocal enabledelayedexpansion

REM Get Python extension suffix
for /f "delims=" %%i in ('python -c "import sysconfig; print(sysconfig.get_config_var('EXT_SUFFIX'))"') do set EXT_SUFFIX=%%i

REM Set paths
set SVUVM_SO=_svuvm%EXT_SUFFIX%
set PYTHON_PATH=%~dp0src\svuvm
set UVM_PATH=%~dp0uvm-verilator\src

REM Check if Verilator is available
where verilator >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Verilator found, building with simulation support...
    
    REM Get number of processors
    for /f "delims=" %%i in ('wmic cpu get NumberOfCores /value ^| find "="') do set NPROC=%%i
    set NPROC=%NPROC:NumberOfCores=%
    
    REM Build with Verilator
    verilator -j %NPROC% --vpi --binary -top top -Mdir build --output-groups %NPROC% ^
        +incdir+%UVM_PATH% %UVM_PATH%\uvm_pkg.sv ^
        -Wno-lint -Wno-style -Wno-SYMRSVDWORD -Wno-IGNOREDRETURN -Wno-CONSTRAINTIGN -Wno-ZERODLY ^
        %UVM_PATH%\dpi\uvm_dpi.cc ^
        -CFLAGS "-I%UVM_PATH%\dpi -I%~dp0inc -DVERILATOR" ^
        -LDFLAGS "-lpython%PYTHON_VERSION%"
    
    REM Run simulation
    if exist build\Vtop.exe (
        build\Vtop.exe +UVM_TESTNAME=base_test +UVM_NO_RELNOTES +UVM_OBJECTION_TRACE
    )
) else (
    echo Verilator not found, skipping simulation build.
    echo To build Python package only, run: pip install .
)

endlocal