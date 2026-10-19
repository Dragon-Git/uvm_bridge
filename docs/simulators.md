# 仿真器接入

桥接层与仿真器无关。`python_bridge_pkg.sv` 只使用标准 DPI-C 的 `import` / `export`，`inc/` 下是
通用的 VPI 与 svdpi 头文件，不针对任何工具做条件编译。三条接入路径的差别仅在于桥接层以何种方式
进入构建：Verilator 与 VCS 在编译期纳入，xezim 在运行期加载。

| 仿真器 | 完整 API | CI 覆盖 |
|--------|---------|---------|
| Verilator | 否，会消耗仿真时间的 task 被编译掉 | 每次推送 |
| xezim | 是 | 每次推送 |
| VCS | 是 | 无（无 license） |

CI 只覆盖 Verilator 与 xezim 两条路径。VCS 按下文接入，未纳入自动化验证。UVM 版本矩阵见
[uvm-version-compatibility.md](uvm-version-compatibility.md)。

**三条路径共同的前提是 UVM 1.2 及以上。** 1.0 与 1.1 系列的 DPI 源文件布局早于 1.2，桥接层的
DPI 适配层无法在其上编译；选用 VCS 内置 UVM 时尤须注意，它的版本通常低于此下限。

## 公共部分

### 命令行的三样内容

`python -m svuvm.config` 输出三项：桥接的 SV 包、已编译的扩展模块、Python 链接参数。

```console
$ python -m svuvm.config
/path/to/svuvm/python_bridge_pkg.sv /path/to/svuvm/_svuvm.cpython-312-x86_64-linux-gnu.so -LDFLAGS "-L/usr/lib -lpython3.12 -ldl -lm"
```

第三项的值内部含空格并由双引号包围，因此**不能**直接以命令替换的方式传入仿真器：

```bash
vcs $(python -m svuvm.config) top.sv    # 错误
```

命令替换的结果只经过分词，不重新解析引号，`-LDFLAGS` 会收到 `"-L/usr/lib`、`-lpython3.12`、
`-ldl`、`-lm"` 四个残缺参数（`"` 成为字面字符），链接阶段失败。先赋值再展开同样不行：

```bash
SVUVM_ARGS=$(python -m svuvm.config)
vcs $SVUVM_ARGS top.sv                  # 同样错误
```

正确做法是用 `eval` 把输出解析为**数组**，再以数组展开传入。这样引号被重新解析，且不会影响命令
其余部分的引号：

```bash
eval "SVUVM_ARGS=($(python -m svuvm.config))"
vcs "${SVUVM_ARGS[@]}" top.sv           # 正确
```

上述三条写法已在本机以等价命令逐条验证。注意数组语法需要 bash。

仓库自身的 `test/*/Makefile` 不受此影响：GNU make 先把 `$(shell ...)` 的结果展开进配方行，再由
shell 解析整行，此时引号仍按常规规则处理。

### 测试模块的可见性

测试模块所在目录必须在 `PYTHONPATH` 上。`py_func` 以测试类型名导入同名的 `.py`，而该目录不会
自动进入 `sys.path`；缺失时的表现为

```
ModuleNotFoundError: No module named '<测试名>'
```

下文示例假定 `top.sv` 与 `<测试名>.py` 位于同一目录，即当前目录。

## Verilator

```bash
git clone --depth 1 --branch uvm-2020-3.2 \
  https://github.com/chipsalliance/uvm-verilator.git
mkdir -p build

eval "SVUVM_ARGS=($(python -m svuvm.config))"

verilator -j "$(nproc)" --vpi --binary -top top -Mdir build \
  +incdir+"$PWD/uvm-verilator/src" "$PWD/uvm-verilator/src/uvm_pkg.sv" \
  "${SVUVM_ARGS[@]}" "$PWD/top.sv" \
  "$PWD/uvm-verilator/src/dpi/uvm_dpi.cc" \
  -CFLAGS "-I$PWD/uvm-verilator/src/dpi -I$PWD/inc -DVERILATOR"

PYTHONPATH=$PWD ./build/Vtop +UVM_TESTNAME=example_test
```

两处需要注意。

**UVM 源码必须使用带 Verilator 后端的版本。** 上游 UVM 自 2020-3.2 起才提供 Verilator 的 HDL
后端，更早的版本在 `uvm_hdl.c` 中因缺少后端直接报错。上例取上游 2020-3.2；
`Dragon-Git/uvm-verilator` fork 在此基础上额外支持更早的版本。

**`-DVERILATOR` 会关闭一组接口。** 导出的 DPI task 不允许消耗仿真时间，桥接层据此在
`` `ifdef VERILATOR `` 下编译掉下列接口：

`write_reg`、`read_reg`、`check_reg`、`mirror_reg`、`start_seq` 的后台形式、`wait_on`、
`wait_off`、`wait_trigger`、`wait_ptrigger`、`barrier_wait`、`wait_unit`、`run_test_wrap`。

这些调用既不报错也不执行任何动作，一次未生效的寄存器操作只有在覆盖率未达标时才会暴露。需要
总线访问时应改用 xezim 或 VCS。

## xezim

xezim 以解释方式执行，无需预编译，也不受上述时间限制约束。有两项运行期要求：

- UVM 源码树通过 `XEZIM_UVM_DIR` 指定，取含 `src/` 的根目录；`-uvm` 选项依赖该变量。
- `_svuvm.so` 未链接 libpython，而 xezim 以 `RTLD_NOW` 加载它时 `--dpi-lib` 无法保证 libpython
  的符号全局可见，因此需在操作系统层面另行预加载。

```bash
git clone --depth 1 --branch uvm-2020-3.2 \
  https://github.com/chipsalliance/uvm-verilator.git

XEZIM_LIBPYTHON=$(python -c 'import sysconfig, os, glob; d = sysconfig.get_config_var("LIBDIR"); v = sysconfig.get_config_var("LDVERSION") or ""; print(next(p for f in ("*.so", "*.dylib") for p in glob.glob(os.path.join(d, "libpython" + v + f))))')
XEZIM_SVUVM=$(python -c 'import svuvm, os; print(os.path.dirname(svuvm.__file__))')
XEZIM_DPI_LIB=$(python -c 'import svuvm, os, glob; print(glob.glob(os.path.join(os.path.dirname(svuvm.__file__), "_svuvm*.so"))[0])')

PYTHONPATH=$PWD XEZIM_UVM_DIR=$PWD/uvm-verilator xezim --simulate -s top \
  --dpi-lib "$XEZIM_LIBPYTHON" \
  --dpi-lib "$PWD/build/uvm_dpi_xezim.so" \
  --dpi-lib "$XEZIM_DPI_LIB" \
  --max-time 10ms --error-exit -uvm \
  "$XEZIM_SVUVM/python_bridge_pkg.sv" "$PWD/top.sv" \
  +UVM_TESTNAME=example_test
```

`uvm_dpi_xezim.so` 由 UVM DPI 层的 xezim 变体 `uvm_dpi_xezim.cc` 编得，该文件随 xezim 发布包
位于 `include/` 下，以标准 IEEE 1800 VPI 实现 `uvm_hdl_*` 接口。编译命令见
`test/base_test/Makefile` 的 xezim 分支。此路径可直接使用上游 UVM 源码。

## VCS

VCS 在编译期纳入桥接层，与 Verilator 同类，但选项上有一处关键差异：**不要定义 `VERILATOR`**。
该宏只用于在 Verilator 下规避时间限制，定义后总线访问会一并被关闭。

**UVM 版本必须显式指定，且不低于 1.2。** `-ntb_opts uvm` 引入的是 VCS 内置的 UVM，版本随 VCS
发行版本而定，早于桥接层支持的 1.2，不可使用。应显式写出 1.2 及以上的版本，例如
`-ntb_opts uvm-1.2`；对应 2017 / 2020 版本另有专门选项，具体名称以所用 VCS 的文档为准。支持的
版本范围见 [uvm-version-compatibility.md](uvm-version-compatibility.md)。若已有独立的 UVM 编译
流程（自行指定源码树与 include 路径），则沿用原有参数，不再写 `-ntb_opts`。

`-timescale` 供 UVM 的时间单位使用，建议显式给出。

```bash
eval "SVUVM_ARGS=($(python -m svuvm.config))"

vcs -full64 -sverilog \
  -timescale=1ns/1ps \
  -ntb_opts uvm-1.2 \
  "${SVUVM_ARGS[@]}" \
  top.sv

PYTHONPATH=$PWD ./simv +UVM_TESTNAME=example_test
```

说明：

- `-timescale` 与 `-ntb_opts` 的取值应按所用 VCS 与 UVM 版本调整；UVM 低于 1.2 时桥接层不适用。
- `uvm_hdl_*` 依赖 VPI 访问信号，需要相应的调试访问选项（例如 `-debug_access+all`），否则信号
  级操作不可用。
- 运行时 `_svuvm.so` 需要找到 libpython。链接参数已由 `-LDFLAGS` 提供；若运行时报找不到
  `libpython`，将 Python 的 `LIBDIR` 加入 `LD_LIBRARY_PATH`。
- `uvm-verilator` fork 仅为 Verilator 提供后端，对其余仿真器不是必需项，VCS 下用上游 UVM 即可。

## 其他仿真器

Questa 与 Xcelium 暂无单独说明。桥接层未针对它们做任何条件编译，接入方式与 VCS 一致：同一段
`svuvm.config` 输出、不定义 `VERILATOR`、显式指定 UVM 1.2 及以上版本、按需给出 timescale。这两条
路径未经验证，建议先在最小环境中确认。
