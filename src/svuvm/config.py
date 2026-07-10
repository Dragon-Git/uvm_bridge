import sys
import sysconfig
import platform
from pathlib import Path


def main():
    getvar = sysconfig.get_config_var
    ext_suffix = getvar("EXT_SUFFIX")
    so_name = "_svuvm" + ext_suffix

    so_file = Path(__file__).parent / so_name
    sv_file = Path(__file__).parent / "python_bridge_pkg.sv"

    libs = []
    ldflags = ""

    if platform.system() == 'Windows':
        # Windows: Python extension modules are DLLs, no special linker flags needed
        # The extension suffix on Windows is typically .pyd
        # For Verilator on Windows, we just need to provide the Python library path
        python_lib_dir = Path(sys.executable).parent / "libs"
        if python_lib_dir.exists():
            libs.append(f'-L"{python_lib_dir}"')
        # Add Python library name (e.g., python312.lib)
        python_lib = f'python{getvar("VERSION")}{sys.abiflags}.lib'
        libs.append(f'-l{python_lib}')
        ldflags = ' '.join(libs)
    elif platform.system() in ['Linux', 'Darwin']:
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
        # Other platforms: use generic method
        libs.append('-lpython' + getvar('VERSION') + sys.abiflags)
        libs.extend(getvar('LIBS').split() + getvar('SYSLIBS').split())
        if not getvar('Py_ENABLE_SHARED'):
            libs.insert(0, '-L' + getvar('LIBPL'))
        ldflags = ' '.join(libs)

    # Use proper quoting for Windows paths
    if platform.system() == 'Windows':
        sv_file_str = str(sv_file).replace('\\', '/')
        so_file_str = str(so_file).replace('\\', '/')
    else:
        sv_file_str = str(sv_file)
        so_file_str = str(so_file)

    print(f'{sv_file_str} {so_file_str} -LDFLAGS "{ldflags}"')


if __name__ == "__main__":
    main()