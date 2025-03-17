import re
from sysconfig import get_config_var as getvar
from glob import glob
from setuptools import setup
from pybind11.setup_helpers import Pybind11Extension, build_ext


class CustomExtension(Pybind11Extension):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "-fvisibility=hidden" in self.extra_compile_args:
            self.extra_compile_args.remove("-fvisibility=hidden")


class custom_build_ext(build_ext):  # noqa: N801
    """Customized build_ext that remove some compile flags."""

    def build_extensions(self) -> None:
        """Build extensions, remove some compile flags."""

        if "-bundle" in self.compiler.linker_so:
            self.compiler.linker_so.remove("-bundle")
            self.compiler.linker_so.append("-dynamiclib")
        if "-bundle" in self.compiler.linker_so_cxx:
            self.compiler.linker_so_cxx.remove("-bundle")
            self.compiler.linker_so_cxx.append("-dynamiclib")
        self.compiler.library_dirs.append(getvar("LIBDIR"))
        super().build_extensions()

    def run(self):
        with open("inc/vpi_user.h", "r") as file:
            content = file.read()
        with open("inc/sv_vpi_user.h", "r") as file:
            content += file.read()
        pattern = re.compile(r"#define\s+(vpi\w+|cb\w+)\s+(\d+)")
        matches = pattern.findall(content)
        vpi_attr = [f'vpi.attr("{match[0]}") = {match[0]};' for match in matches]
        with open("inc/vpi_attr.h", "w") as file:
            file.write("\n".join(vpi_attr))
        build_ext.run(self)


ext_modules = [
    CustomExtension(
        "svuvm.svuvm",
        sorted(glob("src/svuvm/*.cpp")),
        include_dirs=["inc"],
        extra_link_args=[
            "-fPIC",
            f"-lpython{getvar('VERSION')}",
        ],
    ),
]

setup(cmdclass={"build_ext": custom_build_ext}, ext_modules=ext_modules)
