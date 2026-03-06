import sys 
import sysconfig 
import platform
from pathlib import Path 


getvar = sysconfig.get_config_var 
so_name = "svuvm" + getvar("EXT_SUFFIX") 


so_file = Path(__file__).parent / so_name 
sv_file = Path(__file__).parent / "python_bridge_pkg.sv" 


libs = [] 
# Handle Python library linking differently for Linux and macOS
if platform.system() in ['Linux', 'Darwin']:
    # On Linux and macOS, use python3-config to get proper linker flags
    import subprocess
    try:
        # Use python3-config command directly
        result = subprocess.run(
            ['python3-config', '--ldflags', '--embed'],
            capture_output=True,
            text=True,
            check=True
        )
        ldflags = result.stdout.strip()
    except subprocess.CalledProcessError:
        # Fallback to original method if python3-config fails
        libs.append('-lpython' + getvar('VERSION') + sys.abiflags)
        libs.extend(getvar('LIBS').split() + getvar('SYSLIBS').split())
        if not getvar('Py_ENABLE_SHARED'):
            libs.insert(0, '-L' + getvar('LIBPL'))
        ldflags = ' '.join(libs)
else:
    # Original method for Windows and other systems
    libs.append('-lpython' + getvar('VERSION') + sys.abiflags)
    libs.extend(getvar('LIBS').split() + getvar('SYSLIBS').split())
    if not getvar('Py_ENABLE_SHARED'):
        libs.insert(0, '-L' + getvar('LIBPL'))
    ldflags = ' '.join(libs)

print(f'{sv_file} {so_file} -LDFLAGS "{ldflags}"')