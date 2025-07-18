import re
from sysconfig import get_config_var as getvar
from glob import glob
from setuptools import setup
from pybind11.setup_helpers import Pybind11Extension, build_ext
import pyslang
from pathlib import Path

exclude_func_list = [
    "call_py_func",
    "get_contxt",
    "base16_encode",
    "base16_decode",
    "wait_trigger_data",
    "wait_ptrigger_data",
    "get_trigger_data",
    "get_default_data",
    "set_default_data",
    "set_config_int_array_t",
    "get_config_int_array_t",
    "set_config_byte_array_t",
    "get_config_byte_array_t",
]

def get_sv_export(filename = "src/svuvm/python_bridge_pkg.sv"):
    tree = pyslang.SyntaxTree.fromFile(filename)
    root = tree.root

    # 创建输出路径对象
    target_file = Path(filename)

    # 收集DPI-C导出声明
    output_lines = ["    // Genarated by gen_export.py", "    // Do not edit this file manually"]
    for member in root.members[0].members:
        if member.kind == pyslang.SyntaxKind.TaskDeclaration:
            if member.prototype.name.identifier.value in exclude_func_list:
                continue
            output_lines.append(f'    export "DPI-C" task     {member.prototype.name};')
        elif member.kind == pyslang.SyntaxKind.FunctionDeclaration:
            if member.prototype.name.identifier.value in exclude_func_list:
                continue
            output_lines.append(f'    export "DPI-C" function {member.prototype.name};')

    # 读取原始文件内容
    if target_file.exists():
        content = target_file.read_text().splitlines()
    else:
        content = []

    # 查找标记位置
    begin_marker = "// EXPORT_DPIC_BEGIN"
    end_marker = "// EXPORT_DPIC_END"

    begin_idx = None
    end_idx = None

    for i, line in enumerate(content):
        if line.strip() == begin_marker:
            begin_idx = i
        elif line.strip() == end_marker:
            end_idx = i
            break

    # 替换标记之间内容
    if begin_idx is not None and end_idx is not None:
        # 保留标记前的内容 + 新生成内容 + 标记后的内容
        new_content = content[: begin_idx + 1] + output_lines + content[end_idx:]
    else:
        # 如果没有找到标记，则附加标记和内容
        new_content = content + [begin_marker] + output_lines + [end_marker]

    # 写回文件
    target_file.write_text("\n".join(new_content))

def get_cheader(filename = "src/svuvm/python_bridge_pkg.sv"):
    tree = pyslang.SyntaxTree.fromFile(filename)
    root = tree.root

    output_lines = ["    // Genarated by gen_export.py", "    // Do not edit this file manually"]
    for member in root.members[0].members:
        if member.kind == pyslang.SyntaxKind.TaskDeclaration:
            if member.prototype.name.identifier.value in exclude_func_list:
                continue
            prototype = str(member.prototype)
            prototype = (
                prototype.replace("task automatic", "void")
                .replace("output string", "char **")
                .replace("string", "const char *")
                .replace("output int", "int *")
                .replace("uvm_action", "int")
                .replace("bit", "bool")
                .replace("longint", "long long")
            )
            output_lines.append(f"{prototype};")
        elif member.kind == pyslang.SyntaxKind.FunctionDeclaration:
            if member.prototype.name.identifier.value in exclude_func_list:
                continue
            prototype = str(member.prototype)
            prototype = (
                prototype.replace("function automatic ", "")
                .replace("output string", "const char *")
                .replace("string", "const char *")
                .replace("output int", "int *")
                .replace("uvm_action", "int")
                .replace("bit", "bool")
                .replace("longint", "long long")
                .replace("config_const char *", "config_string")
            )
            output_lines.append(f"{prototype};")

    Path("inc/export_dpi.h").write_text("".join(output_lines))


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
        get_sv_export()
        get_cheader()
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
